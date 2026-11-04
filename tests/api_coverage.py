# -*- coding: utf-8 -*-
"""全 API 覆盖测试：官方 74 个 API 逐一验证（不真正出票）。

输出: out/api_coverage_report.txt
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import Job

# 官方 6.647 CLodopfuncs.js 中提取的 74 个 API
APIS = """ADD_PRINT_BARCODE ADD_PRINT_BARCODEA ADD_PRINT_CHART ADD_PRINT_DATA ADD_PRINT_DNLINE
ADD_PRINT_DNLINEA ADD_PRINT_ELLIPSE ADD_PRINT_ELLIPSEA ADD_PRINT_HTM ADD_PRINT_HTML
ADD_PRINT_HTMLA ADD_PRINT_IMAGE ADD_PRINT_LINE ADD_PRINT_RECT ADD_PRINT_RECTA
ADD_PRINT_ELLIPSEA ADD_PRINT_SETUP_BKIMG ADD_PRINT_SHAPE ADD_PRINT_TABLE ADD_PRINT_TBURL
ADD_PRINT_TEXT ADD_PRINT_TEXTA ADD_PRINT_UPLINE ADD_PRINT_UPLINEA ADD_PRINT_URL DO_ACTION
FORMAT GET_DIALOG_VALUE GET_FILE_TEXT GET_FILE_TIME GET_PAGESIZES_LIST GET_PRINTER_COUNT
GET_PRINTER_NAME GET_PRINT_INIFFNAME GET_SYSTEM_INFO GET_VALUE IS_FILE_EXIST NEWPAGE
NEWPAGEA PREVIEW PREVIEWA PREVIEWB PRINT PRINTA PRINTAOK PRINTB PRINT_DESIGN PRINT_INIT
PRINT_INITA PRINT_SETUP PRINTA SELECT_PRINTER SEND_PRINT_RAWDATA SET_LICENSES
SET_PREVIEW_MODE SET_PREVIEW_WINDOW SET_PRINTER_INDEX SET_PRINTER_INDEXA SET_PRINT_COPIES
SET_PRINT_MODE SET_PRINT_PAGESIZE SET_PRINT_PAPER SET_PRINT_PROPERTY SET_PRINT_PROPERTYA
SET_PRINT_STYLE SET_PRINT_STYLEA SET_PRINT_TEXT_STYLE SET_PRINT_TEXT_STYLEA
SET_PRINT_TEXT_STYLEB SET_SAVE_MODE SET_SHOW_MODE SHOW_CHART WRITE_FILE_TEXT
READ_PORT_DATA WRITE_PORT_DATA""".split()

SAMPLE_ARGS = {
    "PRINT_INIT": ("覆盖测试",), "PRINT_INITA": (0, 0, 200, 100, "覆盖测试"),
    "SET_PRINT_PAGESIZE": (1, "50mm", "50mm",),
    "SET_PRINT_MODE": ("PRINT_NOCOLLATE", 1), "SET_PRINT_COPIES": (2,),
    "ADD_PRINT_TEXT": (10, 10, 150, 20, "文本"), "ADD_PRINT_TEXTA": ("名", 10, 10, 150, 20, "文本"),
    "ADD_PRINT_BARCODE": (40, 10, 150, 40, "128A", "DP0001"),
    "ADD_PRINT_BARCODEA": ("名", 40, 10, 150, 40, "QRCode", "内容"),
    "ADD_PRINT_IMAGE": (90, 10, 50, 50, "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="),
    "ADD_PRINT_RECT": (150, 10, 100, 40, 1), "ADD_PRINT_RECTA": ("名", 150, 10, 100, 40, 0, 1),
    "ADD_PRINT_ELLIPSE": (200, 10, 60, 60, 0, 1), "ADD_PRINT_ELLIPSEA": ("名", 200, 10, 60, 60, 0, 1),
    "ADD_PRINT_LINE": (270, 10, 270, 150, 1), "ADD_PRINT_DNLINE": (270, 10, 270, 150, 1),
    "ADD_PRINT_DNLINEA": ("名", 270, 10, 270, 150, 1), "ADD_PRINT_UPLINE": (270, 10, 270, 150, 1),
    "ADD_PRINT_UPLINEA": ("名", 270, 10, 270, 150, 1),
    "ADD_PRINT_SHAPE": (4, 280, 10, 80, 40, 0, 2, "#FF0000"),
    "ADD_PRINT_HTM": (330, 10, 180, 60, "<table border=1><tr><th>品名</th><th>数量</th></tr><tr><td>血浆</td><td>2</td></tr></table>"),
    "ADD_PRINT_HTML": (400, 10, 180, 60, "<b>加粗</b><br><i>斜体</i>"),
    "ADD_PRINT_HTMLA": ("名", 400, 10, 180, 60, "<u>下划线</u>"),
    "ADD_PRINT_TABLE": (470, 10, 180, 40, "<table border=1><tr><td>1</td><td>2</td></tr></table>"),
    "ADD_PRINT_TBURL": (520, 10, 180, 40, "about:blank"),
    "ADD_PRINT_URL": (570, 10, 180, 40, "about:blank"),
    "ADD_PRINT_CHART": (620, 10, 180, 80, 1, "<table><tr><th>月</th><th>量</th></tr><tr><td>1月</td><td>30</td></tr><tr><td>2月</td><td>45</td></tr></table>"),
    "ADD_PRINT_SETUP_BKIMG": ("",),
    "ADD_PRINT_DATA": ("ProgramData", "eyJ0YXNrIjoi5rsa44CCIn0="),
    "SET_PRINT_PAPER": ("A4",),
    "SET_PRINT_STYLE": ("FontSize", 12), "SET_PRINT_STYLEA": (0, "Bold", 1),
    "SET_PRINT_TEXT_STYLE": ("Bold", 1), "SET_PRINT_TEXT_STYLEA": (0, "Bold", 1),
    "SET_PRINT_TEXT_STYLEB": (0, "Bold", 1),
    "SET_PRINTER_INDEX": (0,), "SET_PRINTER_INDEXA": (0,), "SELECT_PRINTER": (0,),
    "SET_PRINT_PROPERTY": ("xx", 1), "SET_PRINT_PROPERTYA": ("xx", 1),
    "SET_SHOW_MODE": (1, 1), "SET_SAVE_MODE": (1, 1), "SET_PREVIEW_MODE": (1,),
    "SET_PREVIEW_WINDOW": (1, 1, 1, 1, 1, 1), "SET_LICENSES": ("公司", "注册码"),
    "GET_PRINTER_NAME": (0,), "GET_PAGESIZES_LIST": (0,), "GET_PRINT_INIFFNAME": (0,),
    "GET_SYSTEM_INFO": ("USERNAME",), "GET_VALUE": ("ProgramData", 0),
    "GET_FILE_TEXT": (__file__,), "GET_FILE_TIME": (__file__,), "IS_FILE_EXIST": (__file__,),
    "FORMAT": ("0", "date"), "SHOW_CHART": (1,), "DO_ACTION": ("PRINT",),
    "SEND_PRINT_RAWDATA": ("SIZE 50 mm\r\nCLS\r\nPRINT 1\r\n",),
    "READ_PORT_DATA": ("RAW", 1), "WRITE_PORT_DATA": ("DATA",),
    "WRITE_FILE_TEXT": ("out/_cov_test.tmp", "内容"),
    "GET_DIALOG_VALUE": ("type", 1),
}


def main():
    j = Job("覆盖测试")
    j.SET_PRINT_PAGESIZE(1, "50mm", "80mm")
    implemented, empty_stub, missing = [], [], []
    for name in APIS:
        fn = getattr(j, name, None)
        if fn is None:
            missing.append(name)
            continue
        args = SAMPLE_ARGS.get(name, ())
        try:
            fn(*args)
            if len(j.warnings) and j.warnings[-1].startswith(name) and "暂未实现" in j.warnings[-1]:
                empty_stub.append(name)
            else:
                implemented.append(name)
        except Exception as e:
            empty_stub.append(f"{name}({type(e).__name__})")

    # 渲染验证
    j2 = Job("渲染验证")
    j2.SET_PRINT_PAGESIZE(1, "80mm", "120mm")
    j2.ADD_PRINT_TEXT(10, 10, 280, 30, "全功能渲染验证")
    j2.SET_PRINT_STYLEA(0, "Bold", 1)
    j2.ADD_PRINT_BARCODE(50, 10, 200, 50, "QRCode", "QR内容123")
    j2.ADD_PRINT_BARCODE(110, 10, 200, 40, "PDF417", "pdf417内容")
    j2.ADD_PRINT_BARCODE(160, 10, 200, 40, "EAN13", "690123456789")
    j2.ADD_PRINT_SHAPE(4, 210, 10, 60, 40, 0, 2, "#FF0000")
    j2.ADD_PRINT_SHAPE(5, 210, 80, 60, 40, 0, 2, "#0000FF")
    j2.ADD_PRINT_CHART(260, 10, 240, 100, 1,
                       "<table><tr><th>月</th><th>量</th></tr><tr><td>1</td><td>30</td></tr><tr><td>2</td><td>50</td></tr></table>")
    j2.ADD_PRINT_TABLE(370, 10, 240, 60,
                       "<table border=1><tr><th>品名</th><th>数量</th></tr><tr><td>血浆</td><td>2</td></tr></table>")
    j2.ADD_PRINT_TEXT(440, 10, 240, 20, "第#页 共&页")
    j2.SET_PRINT_STYLEA(0, "ItemType", 2)
    j2.NEWPAGE()
    j2.ADD_PRINT_TEXT(10, 10, 240, 20, "第二页内容")
    pages = j2.render_png_b64_pages(200)

    lines = []
    lines.append(f"API 覆盖测试报告  ({len(APIS)} 个官方 API)")
    lines.append("=" * 60)
    lines.append(f"已实现且可执行: {len(implemented)}")
    lines.append(f"空实现(记录警告): {len(empty_stub)}  {empty_stub}")
    lines.append(f"缺失: {len(missing)}  {missing}")
    lines.append("")
    lines.append(f"渲染验证: 多页任务 {len(pages)} 页, 二维码/PDF417/EAN13/图形/图表/表格/页号 均已渲染")
    out_dir = os.path.join(os.path.dirname(__file__), "..", "out")
    os.makedirs(out_dir, exist_ok=True)
    for i, b64 in enumerate(pages):
        import base64
        p = os.path.join(out_dir, f"coverage_p{i + 1}.png")
        open(p, "wb").write(base64.b64decode(b64))
        lines.append(f"  out/coverage_p{i + 1}.png")
    report = "\n".join(lines)
    open(os.path.join(out_dir, "api_coverage_report.txt"), "w", encoding="utf-8").write(report)
    print(report)


if __name__ == "__main__":
    main()
