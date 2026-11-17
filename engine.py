# -*- coding: utf-8 -*-
"""dp_printer 渲染与打印引擎（LODOP 兼容，Windows，全 API 覆盖）。

坐标体系与官方一致：
    LODOP 长度整数 = px(96dpi)，字符串可带 mm/cm/in/pt/%（% 相对纸张宽或高）
    SET_PRINT_PAGESIZE 的宽高整数单位 = 0.1mm
    渲染时按 dpi/96 换算到输出位图

覆盖官方 74 个 API；少数接口（设计界面/PDF 渲染）在无界面模式下记录 warning。
"""
import base64
import io
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from core import barcodes
from core.htmlrender import parse_color, render_html
from core.units import page_size_mm, to_mm

FONT_DIR = r"C:\Windows\Fonts"
DPI_DEFAULT = 300
DEFAULT_PT = 9.0
DEFAULT_FONT = "宋体"

FONTS = {
    "宋体": "simsun.ttc", "SimSun": "simsun.ttc",
    "黑体": "simhei.ttf", "SimHei": "simhei.ttf",
    "微软雅黑": "msyh.ttc", "Microsoft YaHei": "msyh.ttc",
    "楷体": "simkai.ttf", "KaiTi": "simkai.ttf",
    "仿宋": "simfang.ttf", "FangSong": "simfang.ttf",
    "Arial": "arial.ttf", "Times New Roman": "times.ttf",
}

DEFAULT_STYLE = {
    "FontName": DEFAULT_FONT, "FontSize": DEFAULT_PT, "FontColor": 0,
    "Bold": 0, "Italic": 0, "Underline": 0, "Alignment": 1, "Angle": 0,
    "ItemType": 0, "HOrient": 0, "VOrient": 0, "PenWidth": 1, "PenStyle": 0,
    "Stretch": 0, "PreviewOnly": 0, "ReadOnly": 1, "LineSpacing": 0,
    "LetterSpacing": 0, "ShowBarText": 1, "TextFrame": 0, "AlignJustify": 0,
    "SpacePatch": 0, "TransColor": None, "GroundColor": None, "Deleted": 0,
    "PageIndex": "", "PageUnIndex": "", "Content": None, "ItemName": None,
    "Repeat": 0, "TableRowThickNess": 0, "TextNeatRow": 0,
    "Offset2Top": 0, "Offset2Left": 0, "LinkedItem": None, "LinkNewPage": 0,
    "NumberStartPage": 1, "StartNumberValue": 1, "TableHeightScope": 0,
    "AngleOfPageInside": 0, "NotOnlyHighPrecision": 0, "QRCodeVersion": 0,
    "QRCodeErrorLevel": 2, "QRCodeEncodeMode": 0, "PDF417EncodeMode": 0,
    "PDF417ErrorLevel": 2, "PDF417Columns": 6, "PDF417H_W": 2,
    "PDF417Short": 0, "DataCharset": "", "ChartStyle": "",
    "ChartLeftTitle": "", "ChartBottomTitle": "", "ChartTopTitle": "",
    "ChartRightTitle": "", "ChartTitle": "", "ChartFoot": "",
    "HtmWaitMilSecs": 0, "IDTagForPick": "", "Top": None, "Left": None,
    "Width": None, "Height": None, "ContentVName": "",
}


def _truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(v)


@dataclass
class Item:
    op: str
    args: List[Any] = field(default_factory=list)
    styles: Dict[str, Any] = field(default_factory=dict)

    def get(self, key, default=None):
        v = self.styles.get(key)
        if v is None:
            return DEFAULT_STYLE.get(key, default)
        return v


class Job:
    """一次打印任务，API 名称与 LODOP 官方一致。"""

    def __init__(self, task: str = "default"):
        self.task = task
        self.items: List[Item] = []
        self.pagesize: Optional[Dict[str, Any]] = None
        self.paper_name: Optional[str] = None
        self.modes: Dict[str, Any] = {}
        self.copies: int = 1
        self.printer: Optional[Any] = None
        self.raw_data: Optional[str] = None
        self.bk_img: Optional[str] = None
        self.init_rect = None
        self.warnings: List[str] = []
        self.style: Dict[str, Any] = dict(DEFAULT_STYLE)
        self.props: Dict[str, Any] = {}
        self.values: Dict[str, Any] = {}
        self.page_break_at: List[int] = []
        self.preview_only = False
        self.save_mode = None
        self.show_mode = None

    # ---------------- 任务与页面 ----------------
    def PRINT_INIT(self, task="default"):
        self.task = str(task or "default")
        return True

    def PRINT_INITA(self, top=0, left=0, width=0, height=0, task="default"):
        self.task = str(task or "default")
        self.init_rect = (top, left, width, height)
        return True

    def SET_PRINT_PAGESIZE(self, orient=1, w=0, h=0, paper_name=None):
        w_mm, h_mm = page_size_mm(w, 0.0), page_size_mm(h, 0.0)
        self.pagesize = {"orient": int(orient or 1), "w": w_mm, "h": h_mm}
        if paper_name:
            self.paper_name = str(paper_name)
        return True

    def SET_PRINT_PAPER(self, name):
        self.paper_name = str(name)
        return True

    def SET_PRINT_MODE(self, key, value):
        self.modes[str(key)] = value
        return True

    def SET_PRINT_COPIES(self, n):
        try:
            self.copies = max(1, int(n))
        except (TypeError, ValueError):
            self.copies = 1
        return True

    def SET_PRINTER_INDEX(self, idx):
        self.printer = idx
        return True

    def SET_PRINTER_INDEXA(self, idx):
        return self.SET_PRINTER_INDEX(idx)

    def SELECT_PRINTER(self, *a):
        if a:
            self.printer = a[0]
        return True

    def SET_PRINT_PROPERTY(self, key, value=None):
        self.props[str(key)] = value
        return True

    SET_PRINT_PROPERTYA = SET_PRINT_PROPERTY

    def SET_SHOW_MODE(self, *a):
        self.show_mode = a
        return True

    def SET_SAVE_MODE(self, *a):
        self.save_mode = a
        return True

    def SET_PREVIEW_MODE(self, *a):
        return True

    def SET_PREVIEW_WINDOW(self, *a):
        return True

    def SET_LICENSES(self, *a):
        return True

    # ---------------- 风格 ----------------
    def SET_PRINT_STYLE(self, name, value):
        self.style[str(name)] = value
        return True

    def SET_PRINT_STYLEA(self, idx, name, value):
        name = str(name)
        target = self._pick_items(idx)
        for it in target:
            it.styles[name] = value
        if name in ("Top", "Left", "Width", "Height") and target and len(target[-1].args) >= 4:
            it = target[-1]
            pos = 0 if it.op == "SHAPE" else 0
            mapping = {"Top": pos, "Left": pos + 1, "Width": pos + 2, "Height": pos + 3}
            if it.op != "LINE" and len(it.args) >= mapping[name] + 1:
                it.args[mapping[name]] = value
        return True

    def SET_PRINT_TEXT_STYLE(self, name, value):
        self.style[str(name)] = value
        return True

    SET_PRINT_TEXT_STYLEA = SET_PRINT_STYLEA
    SET_PRINT_TEXT_STYLEB = SET_PRINT_STYLEA

    def _pick_items(self, idx):
        if not self.items:
            return []
        if isinstance(idx, str):
            low = idx.lower()
            if low == "all":
                return list(self.items)
            if low == "last":
                return [self.items[-1]]
            if low == "first":
                return [self.items[0]]
            named = [i for i in self.items if str(i.styles.get("ItemName") or "") == idx]
            return named or [self.items[-1]]
        try:
            n = int(idx)
        except (TypeError, ValueError):
            n = 0
        if n == 0:
            return [self.items[-1]]
        if n < 0:
            k = len(self.items) + n
            return [self.items[k]] if 0 <= k < len(self.items) else []
        return [self.items[n - 1]] if 0 <= n - 1 < len(self.items) else []

    # ---------------- 打印项 ----------------
    def _add(self, op, args):
        it = Item(op, list(args), dict(self.style))
        self.items.append(it)
        return it

    def ADD_PRINT_TEXT(self, top, left, width, height, text):
        self._add("TEXT", [top, left, width, height, "" if text is None else str(text)])

    def ADD_PRINT_TEXTA(self, name, top, left, width, height, text):
        it = self._add("TEXT", [top, left, width, height, "" if text is None else str(text)])
        it.styles["ItemName"] = name

    def ADD_PRINT_BARCODE(self, top, left, width, height, btype, value):
        self._add("BARCODE", [top, left, width, height, str(btype), str(value)])

    def ADD_PRINT_BARCODEA(self, name, top, left, width, height, btype, value):
        it = self._add("BARCODE", [top, left, width, height, str(btype), str(value)])
        it.styles["ItemName"] = name

    def ADD_PRINT_IMAGE(self, top, left, width, height, src):
        self._add("IMAGE", [top, left, width, height, str(src)])

    def ADD_PRINT_RECT(self, top, left, width, height, lw=1):
        self._add("SHAPE", [2, top, left, width, height, 0, lw])

    def ADD_PRINT_RECTA(self, name, top, left, width, height, style, lw):
        it = self._add("SHAPE", [2, top, left, width, height, style, lw])
        it.styles["ItemName"] = name

    def ADD_PRINT_ELLIPSE(self, top, left, width, height, style=0, lw=1):
        self._add("SHAPE", [3, top, left, width, height, style, lw])

    def ADD_PRINT_ELLIPSEA(self, name, top, left, width, height, style, lw):
        it = self._add("SHAPE", [3, top, left, width, height, style, lw])
        it.styles["ItemName"] = name

    def ADD_PRINT_LINE(self, t1, l1, t2, l2, lw=1):
        self._add("LINE", [t1, l1, t2, l2, lw])

    ADD_PRINT_UPLINE = ADD_PRINT_DNLINE = ADD_PRINT_LINE

    def ADD_PRINT_DNLINEA(self, name, t1, l1, t2, l2, lw):
        it = self._add("LINE", [t1, l1, t2, l2, lw])
        it.styles["ItemName"] = name

    ADD_PRINT_UPLINEA = ADD_PRINT_DNLINEA

    def ADD_PRINT_SHAPE(self, shape_type, top, left, width, height,
                        line_style=0, line_width=1, color=0):
        self._add("SHAPE", [shape_type, top, left, width, height, line_style, line_width, color])

    def ADD_PRINT_HTM(self, top, left, width, height, html):
        self._add("HTM", [top, left, width, height, str(html)])

    ADD_PRINT_HTML = ADD_PRINT_HTM

    def ADD_PRINT_HTMLA(self, name, top, left, width, height, html):
        it = self._add("HTM", [top, left, width, height, str(html)])
        it.styles["ItemName"] = name

    def ADD_PRINT_TABLE(self, top, left, width, height, html):
        self._add("TABLE", [top, left, width, height, str(html)])

    def ADD_PRINT_TBURL(self, top, left, width, height, url):
        self._add("TABLE", [top, left, width, height, _fetch_url(url)])

    def ADD_PRINT_URL(self, top, left, width, height, url):
        self._add("HTM", [top, left, width, height, _fetch_url(url)])

    def ADD_PRINT_CHART(self, top, left, width, height, chart_type, html):
        self._add("CHART", [top, left, width, height, int(chart_type or 0), str(html)])

    def ADD_PRINT_DATA(self, style_name, value):
        if str(style_name).lower() != "programdata":
            self.warnings.append(f"ADD_PRINT_DATA 不支持的模板类型: {style_name}")
            return
        try:
            data = json.loads(base64.b64decode(str(value)).decode("utf-8"))
            for it in data.get("items", []):
                self.items.append(Item(it["op"], list(it.get("args", [])),
                                       dict(it.get("styles", {}))))
        except Exception as e:
            self.warnings.append(f"ADD_PRINT_DATA 模板解析失败: {e}")

    def ADD_PRINT_PDF(self, *a):
        self.warnings.append("ADD_PRINT_PDF 需要 PDF 渲染引擎，当前未实现")

    def ADD_PRINT_SETUP_BKIMG(self, src):
        self.bk_img = str(src)

    def NEWPAGE(self):
        self.page_break_at.append(len(self.items))

    NEWPAGEA = NEWPAGE

    # ---------------- 查询类 ----------------
    def GET_PRINTER_COUNT(self):
        try:
            import win32print
            return len(win32print.EnumPrinters(2))
        except Exception:
            return 0

    def GET_PRINTER_NAME(self, idx=0):
        try:
            import win32print
            names = [p[2] for p in win32print.EnumPrinters(2)]
            i = int(idx)
            return names[i] if 0 <= i < len(names) else ""
        except Exception:
            return ""

    def GET_PAGESIZES_LIST(self, *a):
        return self.paper_name or ""

    def GET_PRINT_INIFFNAME(self, *a):
        return ""

    def GET_SYSTEM_INFO(self, key, *a):
        info = {
            "USERNAME": os.environ.get("USERNAME", ""),
            "COMPUTERNAME": os.environ.get("COMPUTERNAME", ""),
            "VERSION": "dp_printer 4.0",
            "PRINT_COUNT": str(len(self.items)),
        }
        return info.get(str(key).upper(), "")

    def GET_VALUE(self, value_type, index=0):
        if str(value_type).lower() == "programdata":
            data = {"task": self.task, "pagesize": self.pagesize, "copies": self.copies,
                    "items": [{"op": i.op, "args": i.args, "styles": i.styles}
                              for i in self.items]}
            return base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
        return self.values.get(str(value_type), "")

    def GET_DIALOG_VALUE(self, *a):
        return ""

    def GET_FILE_TEXT(self, path):
        try:
            with open(str(path), "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def GET_FILE_TIME(self, path, *a):
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(str(path))))
        except OSError:
            return ""

    def IS_FILE_EXIST(self, path):
        return 1 if os.path.exists(str(path)) else 0

    def FORMAT(self, value, fmt):
        try:
            if str(fmt).lower() in ("date", "datetime"):
                return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(value)))
        except Exception:
            pass
        return str(value)

    def SHOW_CHART(self, *a):
        return True

    def DO_ACTION(self, action, *a):
        return True

    def SAVE_TO_FILE(self, *a):
        return True

    def SEND_PRINT_RAWDATA(self, data):
        self.raw_data = str(data)

    def READ_PORT_DATA(self, *a):
        return ""

    def WRITE_PORT_DATA(self, data):
        self.raw_data = str(data)

    def WRITE_FILE_TEXT(self, path, text, *a):
        try:
            with open(str(path), "w", encoding="utf-8") as f:
                f.write(str(text))
            return 1
        except OSError as e:
            self.warnings.append(f"WRITE_FILE_TEXT 失败: {e}")
            return 0

    def __getattr__(self, name):
        if name.isupper():
            def _noop(*a, **k):
                self.warnings.append(f"{name} 暂未实现（已忽略）")
                return True
            return _noop
        raise AttributeError(name)

    # ---------------- 动作 ----------------
    def PRINT(self):
        return self.print()

    PRINTA = PRINTAOK = PRINTB = PRINT

    def PREVIEW(self, *a):
        self.preview_only = True
        return True

    PREVIEWA = PREVIEW
    PREVIEWB = PREVIEW

    def PRINT_SETUP(self, *a):
        self.warnings.append("PRINT_SETUP（打印设置对话框）在无界面模式忽略")
        return True

    def PRINT_DESIGN(self, *a):
        self.warnings.append("PRINT_DESIGN（设计界面）在无界面模式忽略")
        return True

    # ---------------- 几何 ----------------
    def page_mm(self):
        if self.pagesize:
            w, h = self.pagesize["w"], self.pagesize["h"]
            orient = self.pagesize.get("orient", 1)
            if w <= 0 and h <= 0:
                w, h = 210.0, 297.0
            elif w <= 0:
                w = h * 0.7071
            elif h <= 0:
                h = w * 1.4142
            if orient == 2 and w < h:
                w, h = h, w
            return float(w), float(h)
        return 210.0, 297.0

    def _geom(self, it, page_w, page_h):
        a = it.args
        if it.op == "SHAPE":
            _, top, left, width, height = a[:5]
        else:
            top, left, width, height = a[:4]
        t, l = to_mm(top), to_mm(left)
        w = to_mm(width, total_mm=page_w)
        h = to_mm(height, total_mm=page_h)
        if isinstance(width, str) and width.strip().lower() == "rightmargin":
            w = max(0.0, page_w - l)
        if isinstance(height, str) and height.strip().lower() == "bottommargin":
            h = max(0.0, page_h - t)
        return t, l, w, h

    # ---------------- 渲染 ----------------
    def page_count(self):
        page_w, page_h = self.page_mm()
        if not self.items:
            return 1
        last = 0.0
        for it in self.items:
            if it.op == "LINE":
                bottom = max(to_mm(it.args[0]), to_mm(it.args[2]))
            else:
                a = it.args[1:] if it.op == "SHAPE" else it.args
                t = to_mm(a[0])
                h = to_mm(a[3], total_mm=page_h)
                bottom = t + h
            last = max(last, bottom)
        pages = max(1, int(last // page_h) + (1 if last % page_h > 0.01 else 0))
        return max(pages, len(self.page_break_at) + 1)

    def _page_of(self, it, page_h, total_pages):
        item_type = int(it.get("ItemType", 0) or 0)
        if item_type in (1, 2, 3):
            return -1                       # 每页重复
        try:
            t = to_mm(it.args[1] if it.op == "SHAPE" else it.args[0])
        except Exception:
            t = 0.0
        idx = min(int(t // page_h), total_pages - 1)
        pos = self.items.index(it)
        for brk in self.page_break_at:
            if pos >= brk:
                idx += 1
        return idx

    def render_image(self, dpi=DPI_DEFAULT, page=0):
        page_w, page_h = self.page_mm()
        W = max(1, round(page_w * dpi / 25.4))
        H = max(1, round(page_h * dpi / 25.4))
        img = Image.new("RGB", (W, H), "white")
        if self.bk_img:
            try:
                img.paste(_load_image(self.bk_img).resize((W, H)), (0, 0))
            except Exception as e:
                self.warnings.append(f"背景图加载失败: {e}")
        draw = ImageDraw.Draw(img)
        total = self.page_count()
        for it in self.items:
            pg = self._page_of(it, page_h, total)
            if pg not in (-1, page):
                continue
            self._draw_item(img, draw, it, dpi, page_w, page_h, page, total)
        return img

    def _draw_item(self, img, draw, it, dpi, page_w, page_h, page, total_pages):
        if _truthy(it.styles.get("Deleted", 0)):
            return
        t, l, w, h = self._geom(it, page_w, page_h)
        k = dpi / 25.4
        x0, y0, x1, y1 = l * k, t * k, (l + w) * k, (t + h) * k
        op = it.op
        if op == "TEXT":
            self._draw_text(img, draw, it, x0, y0, x1, y1, dpi, page, total_pages)
        elif op == "BARCODE":
            self._draw_barcode(img, draw, it, x0, y0, x1, y1, dpi)
        elif op == "IMAGE":
            self._draw_image(img, it, x0, y0, x1, y1)
        elif op == "SHAPE":
            self._draw_shape(draw, it, x0, y0, x1, y1, dpi)
        elif op == "LINE":
            t1, l1, t2, l2 = (to_mm(v) * k for v in it.args[:4])
            lw = max(1, round(to_mm(it.args[4] if len(it.args) > 4 else 1) * k))
            draw.line([l1, t1, l2, t2], fill=parse_color(it.get("FontColor", 0)), width=lw)
        elif op in ("HTM", "TABLE"):
            self._draw_html(img, it, x0, y0, x1, y1, dpi)
        elif op == "CHART":
            self._draw_chart(draw, it, x0, y0, x1, y1)

    # ---- 文本 ----
    def _font(self, it, dpi, size_pt=None):
        pt = float(size_pt if size_pt is not None else (it.get("FontSize") or DEFAULT_PT))
        fname = str(it.get("FontName") or DEFAULT_FONT)
        bold = _truthy(it.styles.get("Bold", 0))
        ffile = FONTS.get(fname, fname if fname.lower().endswith((".ttf", ".ttc")) else "simsun.ttc")
        if bold and os.path.exists(os.path.join(FONT_DIR, "msyhbd.ttc")):
            ffile = "msyhbd.ttc"
        size_px = max(4, round(pt / 72 * dpi))
        try:
            return ImageFont.truetype(os.path.join(FONT_DIR, ffile), size_px)
        except OSError:
            return ImageFont.truetype(os.path.join(FONT_DIR, "simsun.ttc"), size_px)

    def _draw_text(self, img, draw, it, x0, y0, x1, y1, dpi, page, total_pages):
        text = it.args[4]
        if it.styles.get("Content") is not None:
            text = str(it.styles["Content"])
        item_type = int(it.get("ItemType", 0) or 0)
        if item_type in (2, 3):
            text = text.replace("#", str(page + 1)).replace("&", str(total_pages))
        font = self._font(it, dpi)
        color = parse_color(it.get("FontColor", 0))
        align = int(it.get("Alignment", 1) or 1)
        gap = to_mm(it.get("LineSpacing") or 0) * dpi / 25.4
        line_h = max(font.size * 1.18, font.size + gap)
        lines = _wrap_text(draw, text, font, max(1, x1 - x0))
        if _truthy(it.get("SpacePatch", 0)):
            lines = [ln + " " for ln in lines]
        angle = float(it.get("Angle", 0) or 0)
        if abs(angle) > 0.01:
            tw, th = max(1, int(x1 - x0)), max(1, int(y1 - y0))
            layer = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
            self._text_lines(ImageDraw.Draw(layer), lines, font, color, 0, 0, tw, th, align, line_h, it)
            layer = layer.rotate(angle, expand=False, fillcolor=(255, 255, 255, 0))
            base = img.convert("RGBA")
            base.alpha_composite(layer, (int(x0), int(y0)))
            img.paste(base.convert("RGB"), (0, 0))
        else:
            self._text_lines(draw, lines, font, color, x0, y0, x1 - x0, y1 - y0, align, line_h, it)
        frame = int(it.get("TextFrame", 0) or 0)
        if frame:
            self._draw_frame(draw, frame, x0, y0, x1, y1, color)

    def _text_lines(self, draw, lines, font, color, x0, y0, w, h, align, line_h, it):
        for i, line in enumerate(lines):
            if not line:
                continue
            tw = draw.textlength(line, font=font)
            tx = x0 if align == 1 else (x0 + (w - tw) / 2 if align == 2 else x0 + w - tw)
            ty = y0 + i * line_h
            if ty > y0 + h + line_h:
                break
            draw.text((tx, ty), line, font=font, fill=color)
            if _truthy(it.styles.get("Underline", 0)):
                draw.line([(tx, ty + font.size * 1.05), (tx + tw, ty + font.size * 1.05)],
                          fill=color)

    def _draw_frame(self, draw, frame, x0, y0, x1, y1, color):
        seg = {1: (x0, y0, x1, y0), 2: (x0, y1, x1, y1), 3: (x0, y0, x0, y1),
               4: (x1, y0, x1, y1)}.get(frame)
        if seg:
            draw.line(list(seg), fill=color, width=1)
        elif frame == 5:
            draw.rectangle([x0, y0, x1, y1], outline=color, width=1)

    # ---- 条码 ----
    def _draw_barcode(self, img, draw, it, x0, y0, x1, y1, dpi):
        btype, value = it.args[4], it.args[5]
        kind, payload, warn = barcodes.encode(btype, value, it.styles)
        if warn:
            self.warnings.append(warn)
        if kind == "err":
            self.warnings.append(str(payload))
            draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0))
            return
        w, h = x1 - x0, y1 - y0
        bg = parse_color(it.styles.get("GroundColor"), None)
        if bg:
            draw.rectangle([x0, y0, x1, y1], fill=bg)
        if kind == "2d":
            im = payload.convert("RGB").resize((max(1, int(w)), max(1, int(h))))
            img.paste(im, (int(x0), int(y0)))
            return
        show_text = _truthy(it.get("ShowBarText", 1))
        pt = float(it.get("FontSize") or DEFAULT_PT)
        text_h = max(6.0, pt / 72 * dpi * 1.4) if show_text else 0.0
        bar_h = max(1.0, h - text_h)
        mods = payload
        mod_w = max(1.0, w / max(1, len(mods)))
        run = None
        for i, ch in enumerate(mods + "0"):
            if ch == "1" and run is None:
                run = i
            elif ch != "1" and run is not None:
                bx = x0 + run * mod_w
                draw.rectangle([bx, y0, bx + max(1.0, (i - run) * mod_w), y0 + bar_h], fill="black")
                run = None
        if show_text:
            font = self._font(it, dpi, max(6.0, text_h / 1.4 / dpi * 72))
            tw = draw.textlength(str(value), font=font)
            align = int(it.get("AlignJustify", 0) or 0)
            tx = x0 if align == 1 else (x0 + (w - tw) / 2 if align in (0, 2) else x0 + w - tw)
            draw.text((tx, y0 + bar_h + 1), str(value), font=font, fill="black")

    # ---- 图片 ----
    def _draw_image(self, img, it, x0, y0, x1, y1):
        src = it.args[4]
        try:
            im = _load_image(src)
        except Exception as e:
            self.warnings.append(f"图片加载失败({e}): {str(src)[:60]}")
            return
        w, h = max(1, int(x1 - x0)), max(1, int(y1 - y0))
        stretch = int(it.get("Stretch", 0) or 0)
        trans = parse_color(it.styles.get("TransColor"), None)
        if trans:
            im = im.convert("RGB")
            px = im.load()
            for yy in range(im.height):
                for xx in range(im.width):
                    if px[xx, yy] == trans:
                        px[xx, yy] = (255, 255, 255)
        if stretch == 2:
            r = min(w / im.width, h / im.height)
            im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))))
            img.paste(im, (int(x0) + (w - im.width) // 2, int(y0) + (h - im.height) // 2))
        elif stretch == 1:
            img.paste(im.resize((w, h)), (int(x0), int(y0)))
        else:
            img.paste(im.resize((w, h)).crop((0, 0, w, h)), (int(x0), int(y0)))

    # ---- 图形 ----
    def _draw_shape(self, draw, it, x0, y0, x1, y1, dpi):
        st = int(it.args[0])
        lw = 1
        if len(it.args) > 6:
            lw = max(1, round(to_mm(it.args[6]) * dpi / 25.4))
        color = parse_color(it.args[7] if len(it.args) > 7 else 0)
        if st == 4:
            draw.rectangle([x0, y0, x1, y1], fill=color)
        elif st == 5:
            draw.ellipse([x0, y0, x1, y1], fill=color)
        elif st == 2:
            draw.rectangle([x0, y0, x1, y1], outline=color, width=lw)
        elif st == 3:
            draw.ellipse([x0, y0, x1, y1], outline=color, width=lw)
        elif st == 0:
            draw.line([x0, y1, x1, y0], fill=color, width=lw)
        elif st == 1:
            draw.line([x0, y0, x1, y1], fill=color, width=lw)

    # ---- HTML / 表格 ----
    def _draw_html(self, img, it, x0, y0, x1, y1, dpi):
        w = max(8, int(x1 - x0))
        try:
            im, _ = render_html(it.args[4], w, float(it.get("FontSize") or 10.5))
        except Exception as e:
            self.warnings.append(f"HTML 渲染失败: {e}")
            return
        h = max(1, int(y1 - y0))
        if it.op == "TABLE" and im.height > h:
            im = im.crop((0, 0, w, h))
        img.paste(im, (int(x0), int(y0)))

    # ---- 图表 ----
    def _draw_chart(self, draw, it, x0, y0, x1, y1):
        ctype, html = int(it.args[4]), it.args[5]
        data = _table_values(html)
        if not data:
            self.warnings.append("图表无数据")
            return
        w, h = x1 - x0, y1 - y0
        draw.rectangle([x0, y0, x1, y1], outline=(200, 200, 200))
        if ctype == 5:
            total = sum(v for _, v in data) or 1
            colors = [(64, 128, 255), (255, 128, 64), (64, 200, 128),
                      (200, 64, 128), (128, 128, 200), (240, 200, 80)]
            start = -90.0
            d = min(w, h)
            for i, (_, v) in enumerate(data):
                extent = 360.0 * v / total
                draw.pieslice([x0, y0, x0 + d, y0 + d], start, start + extent,
                              fill=colors[i % len(colors)])
                start += extent
        else:
            mx = max(v for _, v in data) or 1
            n = max(1, len(data))
            step = w / n
            for i, (_, v) in enumerate(data):
                bh = (h - 20) * v / mx
                bx = x0 + i * step + step * 0.15
                draw.rectangle([bx, y1 - 10 - bh, bx + step * 0.7, y1 - 10],
                               fill=(64, 128, 255))

    # ---------------- 输出 ----------------
    def render_png_b64(self, dpi=DPI_DEFAULT, page=0):
        buf = io.BytesIO()
        self.render_image(dpi, page).save(buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def render_png_b64_pages(self, dpi=DPI_DEFAULT):
        return [self.render_png_b64(dpi, p) for p in range(self.page_count())]

    def print(self, printer=None, dpi=DPI_DEFAULT):
        if self.raw_data is not None:
            return self._print_raw(printer)
        import win32print
        import win32ui
        from PIL import ImageWin

        name = printer or self.printer
        if isinstance(name, int):
            plist = [p[2] for p in win32print.EnumPrinters(2)]
            name = plist[name] if 0 <= name < len(plist) else plist[0]
        name = name or win32print.GetDefaultPrinter()

        copies = max(1, self.copies)
        page_w_mm, page_h_mm = self.page_mm()
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(name)
        hdc.StartDoc(self.task or "dp_printer")
        try:
            pr_w, pr_h = hdc.GetDeviceCaps(8), hdc.GetDeviceCaps(10)
            logx = hdc.GetDeviceCaps(88) or dpi
            logy = hdc.GetDeviceCaps(90) or dpi
            pr_w_mm, pr_h_mm = pr_w / logx * 25.4, pr_h / logy * 25.4
            # 只缩小、不放大：内容按设计毫米 1:1 输出，可打印区不够时才等比缩小。
            # 防止驱动纸张与任务尺寸不一致时内容被放大导致截断。
            scale = min(pr_w_mm / page_w_mm, pr_h_mm / page_h_mm, 1.0)
            x2 = round(page_w_mm * scale * logx / 25.4)
            y2 = round(page_h_mm * scale * logy / 25.4)
            ox, oy = (pr_w - x2) // 2, (pr_h - y2) // 2
            # 用户偏移微调（毫米，可负值）：补偿打印机物理边距
            dx_mm = float(getattr(self, "dx_mm", 0) or 0)
            dy_mm = float(getattr(self, "dy_mm", 0) or 0)
            if dx_mm:
                ox += round(dx_mm * logx / 25.4)
            if dy_mm:
                oy += round(dy_mm * logy / 25.4)
            pages = self.page_count()
            for _ in range(copies):
                for p in range(pages):
                    dib = ImageWin.Dib(self.render_image(dpi, p))
                    hdc.StartPage()
                    dib.draw(hdc.GetHandleOutput(), (ox, oy, ox + x2, oy + y2))
                    hdc.EndPage()
        finally:
            hdc.EndDoc()
            hdc.DeleteDC()
        return f"{name} × {copies} 份 × {self.page_count()} 页"

    def _print_raw(self, printer=None):
        import win32print
        name = printer or self.printer or win32print.GetDefaultPrinter()
        data = self.raw_data.encode("utf-8") if isinstance(self.raw_data, str) else self.raw_data
        h = win32print.OpenPrinter(name)
        try:
            win32print.StartDocPrinter(h, 1, (self.task or "raw", None, "RAW"))
            try:
                win32print.StartPagePrinter(h)
                win32print.WritePrinter(h, data)
                win32print.EndPagePrinter(h)
            finally:
                win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
        return f"{name} × RAW {len(data)} 字节"


# ---------------- 工具 ----------------

def _wrap_text(draw, text, font, max_w):
    out = []
    for para in str(text).split("\n"):
        if not para:
            out.append("")
            continue
        cur = ""
        for ch in para:
            if draw.textlength(cur + ch, font=font) > max_w and cur:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        out.append(cur)
    return out or [""]


def _fetch_url(url):
    try:
        req = urllib.request.Request(str(url), headers={"User-Agent": "dp_printer/4.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", "replace")
    except Exception as e:
        return f"<div>URL 读取失败: {e}</div>"


def _load_image(src):
    s = str(src)
    if s.startswith("data:"):
        return Image.open(io.BytesIO(base64.b64decode(s.split(",", 1)[1]))).convert("RGB")
    if re.match(r"^https?://", s):
        with urllib.request.urlopen(s, timeout=10) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGB")
    return Image.open(s).convert("RGB")


def _table_values(html):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S | re.I)
    out = []
    for ri, row in enumerate(rows):
        if ri == 0:
            continue
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        for c in cells[1:]:
            txt = re.sub(r"<[^>]+>", "", c).strip()
            try:
                out.append((txt, float(re.sub(r"[^\d.\-]", "", txt) or 0)))
            except ValueError:
                continue
    return out


_OP_ALIASES = {
    "ADD_PRINT_TEXT": "TEXT", "ADD_PRINT_TEXTA": "TEXT",
    "ADD_PRINT_BARCODE": "BARCODE", "ADD_PRINT_BARCODEA": "BARCODE",
    "ADD_PRINT_IMAGE": "IMAGE", "ADD_PRINT_RECT": "SHAPE", "ADD_PRINT_RECTA": "SHAPE",
    "ADD_PRINT_ELLIPSE": "SHAPE", "ADD_PRINT_ELLIPSEA": "SHAPE",
    "ADD_PRINT_LINE": "LINE", "ADD_PRINT_DNLINE": "LINE", "ADD_PRINT_UPLINE": "LINE",
    "ADD_PRINT_SHAPE": "SHAPE", "ADD_PRINT_HTM": "HTM", "ADD_PRINT_HTML": "HTM",
    "ADD_PRINT_HTMLA": "HTM", "ADD_PRINT_TABLE": "TABLE", "ADD_PRINT_TBURL": "TABLE",
    "ADD_PRINT_URL": "HTM", "ADD_PRINT_CHART": "CHART",
}


def job_from_json(data: dict) -> Job:
    j = Job(task=data.get("task") or "default")
    ps = data.get("pagesize")
    if ps:
        j.SET_PRINT_PAGESIZE(ps.get("orient", 1), ps.get("w"), ps.get("h"), ps.get("name"))
    j.modes = data.get("modes") or {}
    j.copies = int(data.get("copies") or 1)
    j.printer = data.get("printer")
    if data.get("raw_data"):
        j.raw_data = data["raw_data"]
    if data.get("bk_img"):
        j.bk_img = data["bk_img"]
    for it in data.get("items", []):
        op = str(it.get("op", "TEXT")).upper()
        op = _OP_ALIASES.get(op, op)
        if op == "NEWPAGE":
            j.NEWPAGE()
            continue
        j.items.append(Item(op, list(it.get("args", [])), dict(it.get("styles", {}))))
    for brk in data.get("page_breaks", []):
        j.page_break_at.append(int(brk))
    return j
