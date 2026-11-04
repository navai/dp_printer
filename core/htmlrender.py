# -*- coding: utf-8 -*-
"""轻量 HTML 子集渲染器（支撑 LODOP 的 ADD_PRINT_HTM / TABLE / URL / HTML）。

不追求浏览器级还原，覆盖打印场景常用的：
  文本块 div/p/span/br/font/b/i/u/strong/em/center/h1~h6/hr
  表格 table/tr/td/th（含 colspan、边框、对齐、背景色）
  图片 img（本地路径 / http / data:base64）
  内联样式 style="font-size;font-weight;color;text-align;background;line-height"
"""
import base64
import io
import os
import re
import urllib.request
from html.parser import HTMLParser

from PIL import Image, ImageDraw, ImageFont

from .units import MM_PER_PX

FONT_DIR = r"C:\Windows\Fonts"
_FONT_CACHE = {}

_TAG_ALIGN = {"center": "center", "h1": "left", "h2": "left", "h3": "left"}
_BOLD_TAGS = {"b", "strong", "h1", "h2", "h3", "h4", "h5", "h6", "th"}
_ITALIC_TAGS = {"i", "em"}
_UNDERLINE_TAGS = {"u"}

CSS_FONT_SIZE = re.compile(r"font-size\s*:\s*([\d.]+)\s*(px|pt|mm|em)?", re.I)
CSS_COLOR = re.compile(r"(?<!background-)color\s*:\s*([^;]+)", re.I)
CSS_WEIGHT = re.compile(r"font-weight\s*:\s*(\w+)", re.I)
CSS_ALIGN = re.compile(r"text-align\s*:\s*(\w+)", re.I)
CSS_BG = re.compile(r"background(?:-color)?\s*:\s*([^;]+)", re.I)


def _font_file(bold=False, italic=False):
    if bold and os.path.exists(os.path.join(FONT_DIR, "msyhbd.ttc")):
        return "msyhbd.ttc"
    if italic and os.path.exists(os.path.join(FONT_DIR, "simkai.ttf")):
        return "simkai.ttf"
    return "simsun.ttc"


def get_font(size_px, bold=False, italic=False, name=None):
    key = (round(size_px), bold, italic, name)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = os.path.join(FONT_DIR, _font_file(bold, italic))
    if name:
        cand = os.path.join(FONT_DIR, name if name.lower().endswith((".ttf", ".ttc")) else name + ".ttc")
        if os.path.exists(cand):
            path = cand
    try:
        f = ImageFont.truetype(path, max(4, round(size_px)))
    except OSError:
        f = ImageFont.truetype(os.path.join(FONT_DIR, "simsun.ttc"), max(4, round(size_px)))
    _FONT_CACHE[key] = f
    return f


def parse_color(value, default=(0, 0, 0)):
    if value is None:
        return default
    if isinstance(value, int):
        return ((value >> 16) & 255, (value >> 8) & 255, value & 255)
    s = str(value).strip()
    named = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
             "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
             "gray": (128, 128, 128), "grey": (128, 128, 128), "silver": (192, 192, 192),
             "navy": (0, 0, 128), "maroon": (128, 0, 0), "purple": (128, 0, 128),
             "olive": (128, 128, 0), "teal": (0, 128, 128), "orange": (255, 165, 0)}
    if s.lower() in named:
        return named[s.lower()]
    if s.lower().startswith("rgb"):
        nums = re.findall(r"\d+", s)
        if len(nums) >= 3:
            return tuple(int(n) for n in nums[:3])
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", s)
    if m:
        v = int(m.group(1), 16)
        return ((v >> 16) & 255, (v >> 8) & 255, v & 255)
    m = re.fullmatch(r"#?([0-9a-fA-F]{3})", s)
    if m:
        h = m.group(1)
        return tuple(int(c * 2, 16) for c in h)
    return default


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root
        self.void = {"br", "img", "hr", "meta", "link", "input"}

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in self.void:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if data:
            self.cur.children.append(data)


class Style:
    __slots__ = ("size_pt", "bold", "italic", "underline", "color", "align", "bg", "line_h")

    def __init__(self, size_pt=10.5, bold=False, italic=False, underline=False,
                 color=(0, 0, 0), align="left", bg=None, line_h=1.35):
        self.size_pt = size_pt
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.color = color
        self.align = align
        self.bg = bg
        self.line_h = line_h

    def derive(self, node):
        s = Style(self.size_pt, self.bold, self.italic, self.underline,
                  self.color, self.align, self.bg, self.line_h)
        if node.tag in _BOLD_TAGS:
            s.bold = True
        if node.tag in _ITALIC_TAGS:
            s.italic = True
        if node.tag in _UNDERLINE_TAGS:
            s.underline = True
        if node.tag in _TAG_ALIGN:
            s.align = _TAG_ALIGN[node.tag]
        if node.tag == "font":
            if node.attrs.get("color"):
                s.color = parse_color(node.attrs["color"])
            if node.attrs.get("size"):
                try:
                    s.size_pt = {1: 7.5, 2: 10, 3: 12, 4: 14, 5: 18, 6: 24, 7: 36}.get(int(node.attrs["size"]), 10.5)
                except ValueError:
                    pass
        if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            s.size_pt = {"h1": 22, "h2": 18, "h3": 16, "h4": 14, "h5": 12, "h6": 10.5}[node.tag]
        css = node.attrs.get("style", "")
        if css:
            m = CSS_FONT_SIZE.search(css)
            if m:
                val = float(m.group(1))
                unit = m.group(2) or "px"
                s.size_pt = {"px": val * 72 / 96, "pt": val, "mm": val * 72 / 25.4,
                             "em": val * s.size_pt}.get(unit, val * 72 / 96)
            m = CSS_COLOR.search(css)
            if m:
                s.color = parse_color(m.group(1))
            m = CSS_WEIGHT.search(css)
            if m:
                s.bold = m.group(1).lower() in ("bold", "bolder", "600", "700", "800", "900")
            m = CSS_ALIGN.search(css)
            if m:
                s.align = m.group(1).lower()
            m = CSS_BG.search(css)
            if m:
                s.bg = parse_color(m.group(1), None)
        if node.attrs.get("align"):
            s.align = node.attrs["align"].lower()
        if node.attrs.get("bgcolor"):
            s.bg = parse_color(node.attrs["bgcolor"], None)
        return s


def _load_image(src, timeout=8):
    if src.startswith("data:"):
        raw = base64.b64decode(src.split(",", 1)[1])
        return Image.open(io.BytesIO(raw)).convert("RGB")
    if re.match(r"^https?://", src):
        with urllib.request.urlopen(src, timeout=timeout) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGB")
    if os.path.exists(src):
        return Image.open(src).convert("RGB")
    raise FileNotFoundError(src)


class HTMLRenderer:
    """把一个 HTML 片段渲染成 PIL 图像，并按表格行返回分页切点。"""

    def __init__(self, html, width_px, base_size_pt=10.5, dpi=96):
        self.width = max(8, int(width_px))
        self.dpi = dpi
        self.base = Style(size_pt=base_size_pt)
        self.px_per_pt = dpi / 72.0
        b = _Builder()
        b.feed(html or "")
        self.root = b.root
        self.row_marks = []          # 表格行渲染后的 y 坐标（供分页）

    # ---- 排版主流程 ----
    def render(self):
        # 先测量总高
        blocks = self._layout(self.root, self.base)
        total = sum(b[1] for b in blocks) if blocks else 1
        total = max(4, int(total) + 2)
        img = Image.new("RGB", (self.width, total), "white")
        d = ImageDraw.Draw(img)
        y = 0
        for kind, h, payload in blocks:
            if kind == "text":
                self._draw_lines(d, payload, y)
            elif kind == "image":
                im, w, _ = payload
                img.paste(im, (int((self.width - w) / 2), int(y)))
                im.close() if False else None
            elif kind == "rule":
                d.line([(0, y), (self.width, y)], fill=(0, 0, 0), width=1)
            y += h
        return img.crop((0, 0, self.width, max(1, int(y))))

    def _layout(self, node, style, width=None):
        width = width or self.width
        blocks = []
        for child in node.children:
            if isinstance(child, str):
                txt = re.sub(r"\s+", " ", child)
                if txt.strip():
                    lines = self._wrap(txt, style, width)
                    blocks.append(("text", self._lines_height(lines, style), (lines, style, 0, width)))
                continue
            if child.tag == "br":
                blocks.append(("text", self._line_height(style), ([], style, 0, width)))
            elif child.tag in ("p", "div", "center", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
                s = style.derive(child)
                inner = self._layout(child, s, width)
                if not inner and child.text().strip():
                    inner = [("text", self._lines_height(self._wrap(child.text(), s, width), s),
                              (self._wrap(child.text(), s, width), s, 0, width))]
                blocks.extend(inner)
            elif child.tag in ("b", "i", "u", "strong", "em", "span", "font", "a"):
                s = style.derive(child)
                txt = child.text()
                if txt.strip():
                    lines = self._wrap(txt, s, width)
                    blocks.append(("text", self._lines_height(lines, s), (lines, s, 0, width)))
            elif child.tag == "hr":
                blocks.append(("rule", 6, None))
            elif child.tag == "img":
                src = child.attrs.get("src", "")
                try:
                    im = _load_image(src)
                    w = int(child.attrs.get("width") or im.width)
                    h = int(float(child.attrs.get("height") or im.height * w / max(1, im.width)))
                    im = im.resize((w, max(1, h)))
                    blocks.append(("image", h, (im, w, h)))
                except Exception:
                    pass
            elif child.tag == "table":
                blocks.extend(self._layout_table(child, style, width))
            else:
                blocks.extend(self._layout(child, style.derive(child), width))
        return blocks

    # ---- 文本 ----
    def _font(self, style):
        return get_font(style.size_pt * self.px_per_pt, style.bold, style.italic)

    def _line_height(self, style):
        return style.size_pt * self.px_per_pt * style.line_h

    def _lines_height(self, lines, style):
        return max(self._line_height(style), len(lines) * self._line_height(style))

    def _wrap(self, text, style, width):
        font = self._font(style)
        out, cur = [], ""
        for ch in text:
            if ch == "\n":
                out.append(cur)
                cur = ""
                continue
            trial = cur + ch
            if font.getlength(trial) > width and cur:
                out.append(cur)
                cur = ch
            else:
                cur = trial
        out.append(cur)
        return out

    def _draw_lines(self, d, payload, y0):
        lines, style, _, width = payload
        font = self._font(style)
        lh = self._line_height(style)
        for i, line in enumerate(lines):
            if not line:
                continue
            w = font.getlength(line)
            x = 0 if style.align == "left" else (width - w if style.align == "right" else (width - w) / 2)
            y = y0 + i * lh + (lh - style.size_pt * self.px_per_pt) / 2
            if style.underline:
                d.line([(x, y + style.size_pt * self.px_per_pt * 1.05),
                        (x + w, y + style.size_pt * self.px_per_pt * 1.05)], fill=style.color)
            d.text((x, y), line, font=font, fill=style.color)

    # ---- 表格 ----
    def _layout_table(self, table, style, width):
        rows = [r for r in table.children if not isinstance(r, str) and r.tag == "tr"]
        if not rows:
            return []
        cols = max(sum(int(c.attrs.get("colspan", 1)) if not isinstance(c, str) else 1
                       for c in r.children if not isinstance(c, str)) or 1 for r in rows)
        col_w = width / cols
        border = int(table.attrs.get("border", 1) or 0)
        blocks = []
        cell_imgs = []
        for r in rows:
            cells = [c for c in r.children if not isinstance(c, str) and c.tag in ("td", "th")]
            row_h = 0
            parts = []
            x = 0
            for c in cells:
                s = style.derive(c)
                span = int(c.attrs.get("colspan", 1) or 1)
                cw = col_w * span
                lines = self._wrap(c.text().strip(), s, cw - 6)
                h = max(self._line_height(s) * max(1, len(lines)) + 4, 18)
                pad = int(c.attrs.get("padding", 2) or 2)
                h += pad
                cell = Image.new("RGB", (int(cw), int(h)), s.bg or (255, 255, 255))
                cd = ImageDraw.Draw(cell)
                font = self._font(s)
                lh = self._line_height(s)
                for i, line in enumerate(lines):
                    lw = font.getlength(line)
                    tx = 3 if s.align == "left" else (cw - lw - 3 if s.align == "right" else (cw - lw) / 2)
                    cd.text((tx, 2 + i * lh), line, font=font, fill=s.color)
                if border:
                    cd.rectangle([0, 0, cw - 1, h - 1], outline=(0, 0, 0), width=1)
                parts.append((cell, x, h))
                x += cw
                row_h = max(row_h, h)
            line_img = Image.new("RGB", (self.width, int(row_h)), "white")
            for cell, cx, h in parts:
                line_img.paste(cell, (int(cx), 0))
            self.row_marks.append((len(blocks), int(row_h)))
            blocks.append(("image", row_h, (line_img, self.width, row_h)))
        return blocks


def render_html(html, width_px, base_size_pt=10.5):
    r = HTMLRenderer(html, width_px, base_size_pt)
    img = r.render()
    return img, r.row_marks
