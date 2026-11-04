# -*- coding: utf-8 -*-
"""条码编码器：覆盖 LODOP 手册列出的全部条码类型。

一维码统一输出模块串（'1' = 有墨，'0' = 空白），由渲染层按目标宽度缩放绘制；
二维码输出 PIL 图像（QRCode / PDF417）。

支持类型：
128A 128B 128C 128Auto EAN128A EAN128B EAN128C
EAN8 EAN13 UPC_A UPC_E0 UPC_E1 UPCsupp2 UPCsupp5
Code39 39Extended Code93 93Extended
2_5interleaved 2_5industrial 2_5matrix ITF14
MSI PostNet Codabar
QRCode PDF417
"""
import io

# python-barcode：经过验证的 128/39/EAN/UPC-A/ITF/Codabar 编码表
try:
    import barcode as _pybarcode
except Exception:                                   # pragma: no cover
    _pybarcode = None

# 39 扩展字符映射（ASCII 全表 → Code39 基本字符对）
_EXT39 = {
    "\0": "%U", "\x01": "$A", "\x02": "$B", "\x03": "$C", "\x04": "$D", "\x05": "$E",
    "\x06": "$F", "\x07": "$G", "\x08": "$H", "\x09": "$I", "\x0a": "$J", "\x0b": "$K",
    "\x0c": "$L", "\x0d": "$M", "\x0e": "$N", "\x0f": "$O", "\x10": "$P", "\x11": "$Q",
    "\x12": "$R", "\x13": "$S", "\x14": "$T", "\x15": "$U", "\x16": "$V", "\x17": "$W",
    "\x18": "$X", "\x19": "$Y", "\x1a": "$Z", "\x1b": "%A", "\x1c": "%B", "\x1d": "%C",
    "\x1e": "%D", "\x1f": "%E", " ": " ", "!": "/A", '"': "/B", "#": "/C", "$": "/D",
    "%": "/E", "&": "/F", "'": "/G", "(": "/H", ")": "/I", "*": "/J", "+": "/K",
    ",": "/L", "-": "-", ".": ".", "/": "/O", "0": "0", "1": "1", "2": "2", "3": "3",
    "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", ":": "/Z", ";": "%F",
    "<": "%G", "=": "%H", ">": "%I", "?": "%J", "@": "%V", "A": "A", "B": "B", "C": "C",
    "D": "D", "E": "E", "F": "F", "G": "G", "H": "H", "I": "I", "J": "J", "K": "K",
    "L": "L", "M": "M", "N": "N", "O": "O", "P": "P", "Q": "Q", "R": "R", "S": "S",
    "T": "T", "U": "U", "V": "V", "W": "W", "X": "X", "Y": "Y", "Z": "Z", "[": "%K",
    "\\": "%L", "]": "%M", "^": "%N", "_": "%O", "`": "%W", "a": "+A", "b": "+B",
    "c": "+C", "d": "+D", "e": "+E", "f": "+F", "g": "+G", "h": "+H", "i": "+I",
    "j": "+J", "k": "+K", "l": "+L", "m": "+M", "n": "+N", "o": "+O", "p": "+P",
    "q": "+Q", "r": "+R", "s": "+S", "t": "+T", "u": "+U", "v": "+V", "w": "+W",
    "x": "+X", "y": "+Y", "z": "+Z", "{": "%P", "|": "%Q", "}": "%R", "~": "%S",
    "\x7f": "%T",
}

# ---- Code 93：标准 9 模块模板 ----
_C93 = {
    "0": "100010100", "1": "101001000", "2": "101000100", "3": "101000010",
    "4": "100101000", "5": "100100100", "6": "100100010", "7": "101010000",
    "8": "100010010", "9": "100001010",
    "A": "110101000", "B": "110100100", "C": "110100010", "D": "110010100",
    "E": "110010010", "F": "110001010", "G": "101101000", "H": "101100100",
    "I": "101100010", "J": "100110100", "K": "100011010", "L": "101011000",
    "M": "101001100", "N": "101000110", "O": "100101100", "P": "100010110",
    "Q": "110110100", "R": "110110010", "S": "110101100", "T": "110100110",
    "U": "110010110", "V": "110011010", "W": "101101100", "X": "101100110",
    "Y": "100110110", "Z": "100111010",
    "-": "100101110", ".": "111010100", " ": "111010010", "$": "111001010",
    "/": "101101110", "+": "101110110", "%": "110101110",
    "($)": "100100110", "(%)": "111011010", "(/)": "111010110", "(+)": "100110010",
    "*": "101011110",                      # 起始/终止符
}
_C93_EXT = {                          # ASCII → Code93 扩展字符
    "\0": "($)U", "\x01": "($)A", "\x02": "($)B", "\x03": "($)C", "\x04": "($)D",
    "\x05": "($)E", "\x06": "($)F", "\x07": "($)G", "\x08": "($)H", "\x09": "($)I",
    "\x0a": "($)J", "\x0b": "($)K", "\x0c": "($)L", "\x0d": "($)M", "\x0e": "($)N",
    "\x0f": "($)O", "\x10": "($)P", "\x11": "($)Q", "\x12": "($)R", "\x13": "($)S",
    "\x14": "($)T", "\x15": "($)U", "\x16": "($)V", "\x17": "($)W", "\x18": "($)X",
    "\x19": "($)Y", "\x1a": "($)Z", "\x1b": "(%)A", "\x1c": "(%)B", "\x1d": "(%)C",
    "\x1e": "(%)D", "\x1f": "(%)E", "!": "(/)A", '"': "(/)B", "#": "(/)C",
    "$": "(/)D", "%": "(/)E", "&": "(/)F", "'": "(/)G", "(": "(/)H", ")": "(/)I",
    "*": "(/)J", "+": "(/)K", ",": "(/)L", "-": "-", ".": ".", "/": "(/)O",
    ":": "(/)Z", ";": "(%)F", "<": "(%)G", "=": "(%)H", ">": "(%)I", "?": "(%)J",
    "@": "(%)V", "[": "(%)K", "\\": "(%)L", "]": "(%)M", "^": "(%)N", "_": "(%)O",
    "`": "(%)W", "{": "(%)P", "|": "(%)Q", "}": "(%)R", "~": "(%)S", "\x7f": "(%)T",
    "a": "(+)A", "b": "(+)B", "c": "(+)C", "d": "(+)D", "e": "(+)E", "f": "(+)F",
    "g": "(+)G", "h": "(+)H", "i": "(+)I", "j": "(+)J", "k": "(+)K", "l": "(+)L",
    "m": "(+)M", "n": "(+)N", "o": "(+)O", "p": "(+)P", "q": "(+)Q", "r": "(+)R",
    "s": "(+)S", "t": "(+)T", "u": "(+)U", "v": "(+)V", "w": "(+)W", "x": "(+)X",
    "y": "(+)Y", "z": "(+)Z",
}

# ---- 2 of 5（工业/矩阵）：每位数字 5 个元素的宽窄 ----
_25 = {
    "0": "00110", "1": "10000", "2": "01000", "3": "11000", "4": "00100",
    "5": "10100", "6": "01100", "7": "00010", "8": "10010", "9": "01010",
}
# ---- MSI：每位数字 12 模块 ----
_MSI = {
    "0": "100100100100", "1": "100100100110", "2": "100100110100", "3": "100100110110",
    "4": "100110100100", "5": "100110100110", "6": "100110110100", "7": "100110110110",
    "8": "110100100100", "9": "110100100110",
}
# ---- PostNet：每位数字 5 条中 2 条长 ----
_POSTNET = {
    "0": "11000", "1": "00011", "2": "00101", "3": "00110", "4": "01001",
    "5": "01010", "6": "01100", "7": "10001", "8": "10010", "9": "10100",
}
# ---- Codabar（由 python-barcode 提供，这里保留映射名）----

_UPC_E_PARITY = {          # 校验位 → 6 位数据的奇偶模板（1=奇,0=偶）
    0: "111000", 1: "110100", 2: "110010", 3: "110001", 4: "101100",
    5: "100110", 6: "100011", 7: "101010", 8: "101001", 9: "100101",
}
_UPC_E_L = {"0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101",
            "4": "0100011", "5": "0110001", "6": "0101111", "7": "0111011",
            "8": "0110111", "9": "0001011"}
_UPC_E_G = {k: v[::-1].translate(str.maketrans("01", "10")) for k, v in _UPC_E_L.items()}


def _mod10(digits: str) -> int:
    s = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        s += d * (3 if i % 2 == 1 else 1)
    return (10 - s % 10) % 10


# ---------------- 各类型编码 ----------------

def _via_pybarcode(kind, value):
    if _pybarcode is None:
        raise RuntimeError("python-barcode 未安装")
    cls = _pybarcode.get_barcode_class(kind)
    return "".join(cls(value).build())


def _code39(value, extended=False):
    if extended:
        value = "".join(_EXT39.get(c, c) for c in value)
    return _via_pybarcode("code39", value)


def _c93_symbols(text, extended):
    """把待编码文本转成 Code93 符号序列（扩展模式用 ($)/(%)/(/)/(+) 前缀）"""
    out = []
    for c in text:
        if c in _C93 and c != "*":
            out.append(c)
            continue
        if not extended:
            out.append(" ")                       # 不可编码字符按空格处理
            continue
        o = ord(c)
        if 0 <= o <= 25:                          # NUL..SUB → ($)A..($)Z
            out += ["($)", chr(ord("A") + o)]
        elif 27 <= o <= 31:                       # ESC..US → (%)A..(%)E
            out += ["(%)", chr(ord("A") + o - 27)]
        elif 33 <= o <= 44:                       # !.., → (/)A..(/)L
            out += ["(/)", chr(ord("A") + o - 33)]
        elif o == 47:                             # / → (/)O
            out += ["(/)", "O"]
        elif o == 58:                             # : → (/)Z
            out += ["(/)", "Z"]
        elif 59 <= o <= 63:                       # ; < = > ? → (%)F..(%)J
            out += ["(%)", chr(ord("F") + o - 59)]
        elif o == 64:                             # @ → (%)V
            out += ["(%)", "V"]
        elif 91 <= o <= 95:                       # [ \ ] ^ _ → (%)K..(%)O
            out += ["(%)", chr(ord("K") + o - 91)]
        elif o == 96:                             # ` → (%)W
            out += ["(%)", "W"]
        elif 97 <= o <= 122:                      # a..z → (+)A..(+)Z
            out += ["(+)", chr(ord("A") + o - 97)]
        elif 123 <= o <= 127:                     # { | } ~ DEL → (%)P..(%)T
            out += ["(%)", chr(ord("P") + o - 123)]
        else:
            out.append(" ")
    return out


def _code93(value, extended=False):
    syms = _c93_symbols(str(value), extended)

    def checksum(seq, max_weight):
        total = 0
        for i, ch in enumerate(reversed(seq)):
            total += _C93_KEYS[ch] * ((i % max_weight) + 1)
        return _C93_LIST[total % 47]

    c = checksum(syms, 20)
    k = checksum(syms + [c], 15)
    seq = ["*"] + syms + [c, k, "*"]
    return "".join(_C93[ch] for ch in seq) + "1"     # 终止条


_C93_LIST = list(_C93.keys())
_C93_LIST = [k for k in _C93_LIST if k != "*"]
_C93_KEYS = {k: i for i, k in enumerate(_C93_LIST)}


def _itf(value):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) % 2:
        digits = "0" + digits
    return _via_pybarcode("itf", digits)


def _2of5(value, matrix=False):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    out = ["1010" if not matrix else "11011010"]      # 起始符
    for ch in digits:
        pat = _25[ch]
        if matrix:
            # 矩阵二五码：5 个位置各由"窄条+窄空/宽条+窄空"组成
            out.append("".join("110" if p == "1" else "10" for p in pat))
        else:
            # 工业二五码：宽窄元素，条之间用窄空分隔
            out.append("".join("1111" if p == "1" else "11" for p in pat[:5]))
    out.append("1101011" if matrix else "1101")
    return "".join(out)


def _msi(value, mod11=False):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if mod11:
        w = [2, 3, 4, 5, 6, 7]
        s = sum(int(d) * w[i % len(w)] for i, d in enumerate(reversed(digits)))
        digits += str((11 - s % 11) % 11 if (11 - s % 11) % 11 < 10 else 0)
    body = "".join(_MSI[d] for d in digits)
    return "110" + body + "1001"


def _postnet(value):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    total = sum(int(d) for d in digits)
    digits += str((10 - total % 10) % 10)
    out = ["1"]                                       # 起始长条
    for d in digits:
        out.append(_POSTNET[d])
    out.append("1")                                   # 终止长条
    return "".join(out)


def _upce(value, number_system="0"):
    d = "".join(ch for ch in str(value) if ch.isdigit())
    if len(d) == 8:                                   # 已是完整 UPC-E（含校验位）
        number_system, body, given = d[0], d[1:7], d[7]
    else:
        body = d[:6].ljust(6, "0")
        given = None
    upca_body = number_system + body
    chk = _mod10(upca_body) if given is None else int(given)
    parity = _UPC_E_PARITY[chk]
    out = "101"                                       # 起始
    for ch, p in zip(body, parity):
        out += _UPC_E_L[ch] if p == "1" else _UPC_E_G[ch]
    out += "010101"                                   # 终止
    return out


def _upc_supplement(value, count=5):
    d = "".join(ch for ch in str(value) if ch.isdigit())[:count].ljust(count, "0")
    out = "1011"                                      # 补充码起始
    for ch in d:
        out += _UPC_E_L[ch] + ("01" if ch != d[-1] else "")
    return out


def _gs1_128(value, subset="C"):
    try:
        return _via_pybarcode("gs1_128", f"(01){value}" if len(str(value)) == 14 else str(value))
    except Exception:
        return _via_pybarcode("code128", str(value))


# ---------------- 二维码 ----------------

def _qr_image(value, styles, px_size):
    import qrcode
    ver = int(styles.get("QRCodeVersion", 0) or 0)
    lvl_map = {0: qrcode.constants.ERROR_CORRECT_M, 1: qrcode.constants.ERROR_CORRECT_L,
               2: qrcode.constants.ERROR_CORRECT_M, 3: qrcode.constants.ERROR_CORRECT_Q,
               4: qrcode.constants.ERROR_CORRECT_H}
    lvl = lvl_map.get(int(styles.get("QRCodeErrorLevel", 2) or 2), qrcode.constants.ERROR_CORRECT_M)
    q = qrcode.QRCode(version=ver or None, error_correction=lvl, box_size=1, border=2)
    q.add_data(str(value))
    q.make(fit=True)
    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
    return img


def _pdf417_image(value, styles, px_size):
    import pdf417gen
    cols = int(styles.get("PDF417Columns", 0) or 6)
    sec = int(styles.get("PDF417ErrorLevel", 0) or 2)
    codes = pdf417gen.encode(str(value), columns=max(1, cols), security_level=max(0, min(sec, 8)))
    return pdf417gen.render_image(codes, scale=1, ratio=3, padding=0).convert("RGB")


# ---------------- 统一入口 ----------------

def encode(btype, value, styles=None):
    """返回 (kind, payload, warning)

    kind = '1d'  → payload 为模块串
    kind = '2d'  → payload 为 PIL.Image
    kind = 'err' → payload 为错误说明
    """
    styles = styles or {}
    t = str(btype or "").strip()
    low = t.lower().replace("-", "_").replace(" ", "")
    v = "" if value is None else str(value)
    warn = None
    try:
        if low in ("128a", "128b", "128c", "128auto", "code128"):
            return "1d", _via_pybarcode("code128", v), warn
        if low in ("ean128a", "ean128b", "ean128c", "gs1_128", "gs1128"):
            return "1d", _gs1_128(v), warn
        if low == "ean8":
            return "1d", _via_pybarcode("ean8", v), warn
        if low in ("ean13", "jan13"):
            return "1d", _via_pybarcode("ean13", v), warn
        if low in ("upc_a", "upca", "upc"):
            return "1d", _via_pybarcode("upca", v), warn
        if low in ("upc_e0", "upc_e1", "upce"):
            return "1d", _upce(v, "0" if low != "upc_e1" else "1"), warn
        if low in ("upcsupp2", "upcsupp5"):
            return "1d", _upc_supplement(v, 2 if low.endswith("2") else 5), warn
        if low in ("code39", "39"):
            return "1d", _code39(v, False), warn
        if low in ("39extended", "code39extended"):
            return "1d", _code39(v, True), warn
        if low in ("code93", "93"):
            return "1d", _code93(v, False), warn
        if low in ("93extended", "code93extended"):
            return "1d", _code93(v, True), warn
        if low in ("2_5interleaved", "25interleaved", "itf", "itf14"):
            return "1d", _itf(v), warn
        if low in ("2_5industrial", "25industrial"):
            return "1d", _2of5(v, False), warn
        if low in ("2_5matrix", "25matrix"):
            return "1d", _2of5(v, True), warn
        if low == "msi":
            return "1d", _msi(v), warn
        if low == "postnet":
            return "1d", _postnet(v), warn
        if low in ("codabar", "nw7"):
            return "1d", _via_pybarcode("codabar", v), warn
        if low in ("qrcode", "qr"):
            return "2d", _qr_image(v, styles, None), warn
        if low == "pdf417":
            return "2d", _pdf417_image(v, styles, None), warn
    except Exception as e:                             # 类型/长度不合法时降级
        warn = f"条码 {btype} 编码失败({e})，已降级为 Code128"
        try:
            return "1d", _via_pybarcode("code128", v or "0"), warn
        except Exception as e2:
            return "err", f"{btype} 无法编码: {e2}", warn
    return "err", f"不支持的条码类型: {btype}", warn
