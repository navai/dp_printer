# -*- coding: utf-8 -*-
"""LODOP 长度单位换算。

规则（来自官方技术手册）：
- 整数/浮点 = px，1px = 1/96 英寸
- 字符串可带单位：in / cm / mm / pt / px / %
- 关键字 RightMargin / BottomMargin：宽度/高度按"右边距/下边距"计算
- SET_PRINT_PAGESIZE 的宽高整数单位是 0.1mm
"""
import re

MM_PER_INCH = 25.4
PX_PER_INCH = 96.0
MM_PER_PX = MM_PER_INCH / PX_PER_INCH      # 0.264583 mm

_UNIT_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "in": MM_PER_INCH,
    "inch": MM_PER_INCH,
    "pt": MM_PER_INCH / 72.0,
    "px": MM_PER_PX,
    "": MM_PER_PX,                          # 无单位按 px
}

_NUM = re.compile(r"^\s*(-?[\d.]+)\s*([a-zA-Z%]*)\s*$")


def to_mm(value, total_mm=None, ref_mm=None):
    """LODOP 长度 → 毫米。

    total_mm: 百分比的基准长度（页面宽或高）
    ref_mm:   右/下边距换算时的基准长度（页面宽或高）
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) * MM_PER_PX
    s = str(value).strip()
    if not s:
        return 0.0
    low = s.lower()
    if low in ("rightmargin", "bottommargin"):
        # 表示"边距"语义，由调用方用 ref_mm 处理；这里返回标记值
        return -1.0 if low == "rightmargin" else -2.0
    m = _NUM.match(s)
    if not m:
        try:
            return float(s) * MM_PER_PX
        except ValueError:
            return 0.0
    num, unit = float(m.group(1)), m.group(2).lower()
    if unit == "%":
        base = total_mm if total_mm else 0.0
        return base * num / 100.0
    return num * _UNIT_MM.get(unit, MM_PER_PX)


def to_mm_dim(value, total_mm=None, page_mm=None, is_width=True):
    """宽/高专用：支持 RightMargin / BottomMargin 关键字"""
    mm = to_mm(value, total_mm=total_mm, ref_mm=page_mm)
    if mm == -1.0:                      # RightMargin：右边界到纸边
        return max(0.0, (page_mm or 0.0) - to_mm(_first_of_pair(value), total_mm=total_mm))
    if mm == -2.0:
        return max(0.0, (page_mm or 0.0) - 0.0)
    return mm


def _first_of_pair(v):
    return v


def page_size_mm(value, default=0.0):
    """SET_PRINT_PAGESIZE 的宽/高：整数单位 0.1mm，字符串可带单位"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value) / 10.0
    s = str(value).strip()
    if not s:
        return default
    try:
        return float(s) / 10.0
    except ValueError:
        return to_mm(s)


def mm_to_px(mm):
    return mm / MM_PER_PX
