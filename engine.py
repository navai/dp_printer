# -*- coding: utf-8 -*-
"""
LODOP 命令渲染引擎（clean-room Python 实现）

坐标系约定（与 LODOP 一致）：
- ADD_PRINT_TEXT 等的 Top/Left/Width/Height 单位是“像素”，LODOP 取 1px = 1/96 英寸
- SET_PRINT_PAGESIZE(方向, 宽, 高) 里字符串带 mm/cm/in 单位，纯数字则按像素
- FontSize 单位是磅(pt)，1pt = 1/72 英寸
"""
import base64
import io
import re
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from barcode import bars_to_x, code128_bars, code39_bars

# ---------------------------------------------------------------- 常量
PX_PER_MM = 96 / 25.4          # LODOP 像素 → 毫米
DPI_DEFAULT = 300              # 预览/打印渲染精度
FONT_DIR = r"C:\Windows\Fonts"
DEFAULT_FONT = "宋体"          # LODOP 缺省字体
DEFAULT_PT = 12                # LODOP 缺省字号
FONTS = {
    "宋体": "simsun.ttc",
    "黑体": "simhei.ttf",
    "微软雅黑": "msyh.ttc",
    "楷体": "simkai.ttf",
    "Arial": "arial.ttf",
    "Courier New": "cour.ttf",
}

_UNIT_RE = re.compile(r"^\s*([\d.]+)\s*(mm|cm|in|pt|px)?\s*$", re.I)


def _to_mm(v, unit_hint=None) -> float:
    """LODOP 尺寸值 → 毫米"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        # 纯数字按 LODOP 像素处理
        return float(v) / PX_PER_MM
    m = _UNIT_RE.match(str(v))
    if not m:
        raise ValueError(f"无法解析尺寸: {v!r}")
    val, unit = float(m.group(1)), (m.group(2) or unit_hint or "px").lower()
    if unit == "mm":
        return val
    if unit == "cm":
        return val * 10
    if unit == "in":
        return val * 25.4
    if unit == "pt":
        return val * 25.4 / 72
    return val / PX_PER_MM


@dataclass
class Item:
    op: str
    args: list
    styles: dict = field(default_factory=dict)


@dataclass
class Job:
    """一次打印任务，API 名与 LODOP 保持一致，方便把网页里的代码近乎原样搬过来"""
    task: str = "default"
    items: List[Item] = field(default_factory=list)
    pagesize: Optional[dict] = None      # {"orient":1,"w":"50mm","h":"50mm"}
    modes: dict = field(default_factory=dict)
    copies: int = 1
    printer: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    raw_data: Optional[object] = None    # SEND_PRINT_RAWDATA 的原始指令

    # ---------------- 任务级 API ----------------
    def PRINT_INIT(self, task="default"):
        self.task = str(task)

    def PRINT_INITA(self, top, left, width, height, task="default"):
        self.task = str(task)

    def SET_PRINT_PAGESIZE(self, orient, w, h, paper_name=None):
        self.pagesize = {"orient": orient, "w": w, "h": h, "name": paper_name}

    def SET_PRINT_MODE(self, k, v):
        self.modes[str(k)] = v

    def SET_PRINT_COPIES(self, n):
        self.copies = int(n)

    def SET_PRINTER_INDEXA(self, idx):
        self.printer = idx

    def SELECT_PRINTER(self, *a):
        self.warnings.append("SELECT_PRINTER 忽略（网页端弹窗选择）")

    # ---------------- 对象级 API ----------------
    def ADD_PRINT_TEXT(self, top, left, width, height, text):
        self.items.append(Item("ADD_PRINT_TEXT",
                               [top, left, width, height, "" if text is None else str(text)]))

    def ADD_PRINT_BARCODE(self, top, left, width, height, btype, value):
        self.items.append(Item("ADD_PRINT_BARCODE",
                               [top, left, width, height, str(btype), str(value)]))

    def ADD_PRINT_IMAGE(self, top, left, width, height, url_or_b64):
        self.items.append(Item("ADD_PRINT_IMAGE",
                               [top, left, width, height, str(url_or_b64)]))

    def ADD_PRINT_RECT(self, top, left, width, height, lw=1):
        self.items.append(Item("ADD_PRINT_RECT", [top, left, width, height, lw]))

    def ADD_PRINT_ELLIPSE(self, top, left, width, height, style=0, lw=1):
        self.items.append(Item("ADD_PRINT_ELLIPSE", [top, left, width, height, style, lw]))

    def ADD_PRINT_LINE(self, t1, l1, t2, l2, lw=1):
        self.items.append(Item("ADD_PRINT_LINE", [t1, l1, t2, l2, lw]))

    # ---- LODOP 的 A 系列变体：第一个参数是对象序号，本实现忽略它 ----
    def ADD_PRINT_TEXTA(self, *a):        self.ADD_PRINT_TEXT(*a[-5:])
    def ADD_PRINT_BARCODEA(self, *a):     self.ADD_PRINT_BARCODE(*a[-6:])
    def ADD_PRINT_RECTA(self, *a):        self.ADD_PRINT_RECT(*a[-5:])
    def ADD_PRINT_ELLIPSEA(self, *a):     self.ADD_PRINT_ELLIPSE(*a[-6:])
    def ADD_PRINT_DNLINE(self, *a):       self.ADD_PRINT_LINE(*a[-5:])
    def ADD_PRINT_UPLINE(self, *a):       self.ADD_PRINT_LINE(*a[-5:])
    def NEWPAGEA(self):                   self.NEWPAGE()
    def SET_PRINT_PROPERTY(self, *a):     self.SET_PRINT_STYLE(*a)
    def SET_PRINT_PROPERTYA(self, *a):    self.SET_PRINT_STYLEA(*a)

    def ADD_PRINT_HTM(self, *a):
        self.warnings.append(f"ADD_PRINT_HTM 暂不支持，已跳过: {a[:4]}")

    def ADD_PRINT_TABLE(self, *a):
        self.warnings.append(f"ADD_PRINT_TABLE 暂不支持，已跳过")

    def NEWPAGE(self):
        self.items.append(Item("NEWPAGE", []))

    def SET_LICENSES(self, *a):
        pass  # 本实现不校验许可证

    def SEND_PRINT_RAWDATA(self, data):
        """原始指令直发（TSPL/ZPL/ESC-POS），绕过渲染引擎"""
        self.raw_data = data

    def WRITE_PORT_DATA(self, data):
        self.SEND_PRINT_RAWDATA(data)

    def SET_PRINT_STYLE(self, k, v):
        if self.items:
            self.items[-1].styles[str(k)] = v

    def SET_PRINT_STYLEA(self, idx, k, v):
        if idx in (0, -1) and self.items:          # 0 = 最后加入的对象（LODOP 语义）
            self.items[-1].styles[str(k)] = v
        elif 1 <= idx <= len(self.items):
            self.items[idx - 1].styles[str(k)] = v

    # 便捷：PRINT / PRINTB / PREVIEW 在引擎里只是占位，实际动作由调用方触发
    def PRINT(self):   pass
    def PRINTB(self):  pass

    # ---------------- 渲染 ----------------
    def page_mm(self):
        """页面尺寸（毫米），SET_PRINT_PAGESIZE 优先，否则按 A4"""
        if self.pagesize:
            return _to_mm(self.pagesize["w"], "mm"), _to_mm(self.pagesize["h"], "mm")
        return 210.0, 297.0

    def split_pages(self):
        """按 NEWPAGE 标记拆成多页"""
        pages, cur = [], []
        for it in self.items:
            if it.op == "NEWPAGE":
                pages.append(cur)
                cur = []
            else:
                cur.append(it)
        pages.append(cur)
        return pages

    def render_image(self, dpi=DPI_DEFAULT, page=0) -> Image.Image:
        w_mm, h_mm = self.page_mm()
        W, H = round(w_mm * dpi / 25.4), round(h_mm * dpi / 25.4)
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)

        def r(px_lodop):
            """LODOP 像素(96dpi) → 渲染像素，一次换算"""
            return px_lodop * dpi / 96.0

        pages = self.split_pages()
        items = pages[min(page, len(pages) - 1)]
        for it in items:
            st = it.styles
            a = it.args
            if it.op == "ADD_PRINT_TEXT":
                top, left, width, height, text = a
                x0, y0 = r(left), r(top)
                x1, y1 = r(left + width), r(top + height)
                pt = float(st.get("FontSize", DEFAULT_PT))
                fname = str(st.get("FontName", DEFAULT_FONT))
                ffile = FONTS.get(fname, "simsun.ttc")
                fpx = max(4, round(pt / 72 * dpi))
                try:
                    font = ImageFont.truetype(f"{FONT_DIR}\\{ffile}", fpx)
                except OSError:
                    font = ImageFont.truetype(f"{FONT_DIR}\\simsun.ttc", fpx)
                color = str(st.get("Color", "#000000"))
                align = int(st.get("Alignment", 1))     # 1左 2中 3右
                tw = d.textlength(text, font=font)
                if align == 2:
                    tx = (x0 + x1 - tw) / 2
                elif align == 3:
                    tx = x1 - tw
                else:
                    tx = x0
                ty = y0
                bold = int(st.get("Bold", 0))
                for dx in (0, 0.9) if bold else (0,):
                    d.text((tx + dx, ty), text, font=font, fill=color)

            elif it.op == "ADD_PRINT_BARCODE":
                top, left, width, height, btype, value = a
                x0, y0 = r(left), r(top)
                x1, y1 = r(left + width), r(top + height)
                bt = btype.upper().replace("CODE", "").strip()
                if bt.startswith("128"):
                    subset = "A" if "A" in bt else ("C" if "C" in bt else "auto")
                    bars, text, bar_h = code128_bars(value, subset), value, 0.82
                elif bt.startswith("39"):
                    bars, text, bar_h = code39_bars(value), value, 0.82
                else:
                    self.warnings.append(f"条码类型 {btype} 暂不支持，按 128A 处理")
                    bars, text, bar_h = code128_bars(value, "auto"), value, 0.82
                total_modules = sum(bars)
                bar_bottom = y0 + (y1 - y0) * bar_h
                for sx, sw in bars_to_x(bars, total_modules, x0, x1):
                    d.rectangle([sx, y0, sx + sw - 0.5, bar_bottom], fill="black")
                # 条码下方文字
                fpx = max(6, round((y1 - bar_bottom) * 0.72))
                font = ImageFont.truetype(f"{FONT_DIR}\\simsun.ttc", fpx)
                tw = d.textlength(text, font=font)
                d.text(((x0 + x1 - tw) / 2, bar_bottom + 1), text, font=font, fill="black")

            elif it.op == "ADD_PRINT_IMAGE":
                top, left, width, height, src = a
                try:
                    if src.startswith("data:"):     # data:image/png;base64,....
                        raw = base64.b64decode(src.split(",", 1)[1])
                        im = Image.open(io.BytesIO(raw)).convert("RGB")
                    elif re.match(r"^https?://", src):
                        import urllib.request
                        im = Image.open(io.BytesIO(urllib.request.urlopen(src, timeout=10).read())).convert("RGB")
                    else:
                        im = Image.open(src).convert("RGB")
                    box = [r(left), r(top), r(left + width), r(top + height)]
                    im = im.resize((max(1, round(box[2] - box[0])), max(1, round(box[3] - box[1]))))
                    img.paste(im, (round(box[0]), round(box[1])))
                except Exception as e:
                    self.warnings.append(f"图片加载失败({e}): {src[:60]}")

            elif it.op == "ADD_PRINT_ELLIPSE":
                top, left, width, height = a[:4]
                box = [r(left), r(top), r(left + width), r(top + height)]
                d.ellipse(box, outline="black", width=max(1, round(r(1))))

            elif it.op == "ADD_PRINT_RECT":
                top, left, width, height, lw = (a + [1])[:5]
                box = [r(left), r(top), r(left + width), r(top + height)]
                d.rectangle(box, outline="black", width=max(1, round(r(lw))))

            elif it.op == "ADD_PRINT_LINE":
                t1, l1, t2, l2, lw = (a + [1])[:5]
                d.line([r(l1), r(t1), r(l2), r(t2)], fill="black", width=max(1, round(r(lw))))
        return img

    def render_png_b64(self, dpi=DPI_DEFAULT, page=0) -> str:
        buf = io.BytesIO()
        self.render_image(dpi, page).save(buf, "PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def render_png_b64_pages(self, dpi=DPI_DEFAULT) -> List[str]:
        return [self.render_png_b64(dpi, p) for p in range(len(self.split_pages()))]

    # ---------------- 打印 ----------------
    def print(self, printer: Optional[str] = None, dpi=DPI_DEFAULT) -> str:
        """通过 Windows 打印驱动输出；printer=None 用系统默认打印机"""
        import win32print
        import win32ui
        from PIL import ImageWin

        name = printer or self.printer or win32print.GetDefaultPrinter()
        if isinstance(name, int):                    # SET_PRINTER_INDEXA(序号)
            plist = [p[2] for p in win32print.EnumPrinters(2)]
            name = plist[name] if 0 <= name < len(plist) else plist[0]

        hprinter = win32print.OpenPrinter(name)
        try:
            if self.raw_data is not None:            # 原始指令直发通道
                data = self.raw_data
                if isinstance(data, str):
                    data = data.encode("gbk", "replace")
                win32print.StartDocPrinter(hprinter, 1, (self.task or "clodop-raw", None, "RAW"))
                win32print.WritePrinter(hprinter, data)
                win32print.EndDocPrinter(hprinter)
                return f"{name} ← RAW {len(data)} 字节"
        finally:
            pass

        try:
            pages = [self.render_image(dpi, p) for p in range(len(self.split_pages()))]
            copies = max(1, self.copies)
            if "PRINT_NOCOLLATE" in self.modes:
                copies = self.copies if self.copies > 0 else 1

            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(name)
            hdc.StartDoc(self.task or "clodop-python")
            try:
                # 打印机可打印区（像素）与分辨率
                pr_w = hdc.GetDeviceCaps(8)      # HORZRES
                pr_h = hdc.GetDeviceCaps(10)     # VERTRES
                logx = hdc.GetDeviceCaps(88) or dpi   # LOGPIXELSX
                logy = hdc.GetDeviceCaps(90) or dpi   # LOGPIXELSY
                # 页面 mm → 打印机像素，等比缩放并居中
                page_w_mm, page_h_mm = self.page_mm()
                pr_w_mm, pr_h_mm = pr_w / logx * 25.4, pr_h / logy * 25.4
                scale = min(pr_w_mm / page_w_mm, pr_h_mm / page_h_mm)
                x2 = round(page_w_mm * scale * logx / 25.4)
                y2 = round(page_h_mm * scale * logy / 25.4)
                ox = (pr_w - x2) // 2
                oy = (pr_h - y2) // 2
                for _ in range(copies):
                    for img in pages:
                        dib = ImageWin.Dib(img)
                        hdc.StartPage()
                        dib.draw(hdc.GetHandleOutput(), (ox, oy, ox + x2, oy + y2))
                        hdc.EndPage()
            finally:
                hdc.EndDoc()
                hdc.DeleteDC()
        finally:
            win32print.ClosePrinter(hprinter)
        return f"{name} × {copies} 页 × {len(pages)} 页/份"


def job_from_json(data: dict) -> Job:
    """服务端收到的 JSON → Job（网页 JS 桩打包的格式）"""
    j = Job(task=data.get("task") or "default")
    ps = data.get("pagesize")
    if ps:
        j.SET_PRINT_PAGESIZE(ps.get("orient", 1), ps.get("w"), ps.get("h"), ps.get("name"))
    j.modes = data.get("modes") or {}
    j.copies = int(data.get("copies") or 1)
    j.printer = data.get("printer")
    j.raw_data = data.get("raw_data")
    for it in data.get("items", []):
        j.items.append(Item(it.get("op"), it.get("args", []), it.get("styles", {})))
    return j
