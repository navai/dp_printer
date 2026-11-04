# -*- coding: utf-8 -*-
"""dp_printer 配套：TSC 标签打印机纸张配置（换电脑部署用）

用法：
    python setup_tsc.py              # 配置名为 "TSC TE344" 的打印机为 4x4 英寸纸张
    python setup_tsc.py <打印机名>   # 指定其他打印机名
    python setup_tsc.py --list      # 仅列出本机打印机

只做一件事：把打印机默认纸张设为 "Photo 4x 4"（101.6mm x 101.6mm）。
不会修改/删除任何现有的默认纸张或首选项设置。

前置条件：打印机驱动已安装（未装时执行：
    pnputil -add-driver TSC.inf -install && pnputil -scan-devices ）
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

PAPER_FORM = "Photo 4x 4"     # 4x4 英寸 = 101.6mm x 101.6mm
PAPER_W = 1016                # 0.1mm 单位
PAPER_H = 1016


def list_printers():
    import win32print
    return [p[2] for p in win32print.EnumPrinters(2)]


def set_default_paper(name):
    import win32print
    import win32con
    h = win32print.OpenPrinter(name, {"DesiredAccess": win32print.PRINTER_ALL_ACCESS})
    try:
        info = win32print.GetPrinter(h, 2)
        dm = info["pDevMode"]
        dm.FormName = PAPER_FORM
        dm.PaperSize = 0
        dm.PaperWidth = PAPER_W
        dm.PaperLength = PAPER_H
        dm.Fields = (dm.Fields | win32con.DM_FORMNAME | win32con.DM_PAPERSIZE
                     | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH)
        info["pDevMode"] = dm
        win32print.SetPrinter(h, 2, info, 0)
    finally:
        win32print.ClosePrinter(h)


def verify(name):
    import time
    import win32print
    time.sleep(1)
    h = win32print.OpenPrinter(name)
    try:
        dm = win32print.GetPrinter(h, 2)["pDevMode"]
        ok = dm.FormName == PAPER_FORM and dm.PaperWidth == PAPER_W and dm.PaperLength == PAPER_H
        print(f"  当前默认: FormName={dm.FormName!r} | "
              f"纸张 {dm.PaperWidth/10:.1f} x {dm.PaperLength/10:.1f} mm | {'OK' if ok else '未生效!'}")
        return ok
    finally:
        win32print.ClosePrinter(h)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--list" in sys.argv:
        for p in list_printers():
            print(" -", p)
        return
    name = argv[0] if argv else "TSC TE344"
    printers = list_printers()
    if name not in printers:
        print(f"[X] 找不到打印机 {name!r}。本机现有：{printers}")
        print("    若未装驱动，请先执行：")
        print("    pnputil -add-driver TSC.inf -install && pnputil -scan-devices")
        sys.exit(1)
    print(f"[1/2] 设置 {name} 默认纸张为 {PAPER_FORM} ({PAPER_W/10:.1f}mm x {PAPER_H/10:.1f}mm) ...")
    set_default_paper(name)
    print("[2/2] 验证 ...")
    if not verify(name):
        print("  重新写入一次 ...")
        set_default_paper(name)
        verify(name)
    print("[完成] 纸张配置成功（未改动其他打印设置）。")


if __name__ == "__main__":
    main()
