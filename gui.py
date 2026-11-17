# -*- coding: utf-8 -*-
"""
dp_printer 图形客户端

点开即显示：
  - 当前连接的打印机列表（下拉选择，可刷新）
  - 所选打印机的纸张尺寸（从驱动 DEVMODE 读取）
  - 输入框：输入打印内容，点【打印】即通过 Windows 驱动出纸
  - 后台同时运行 CLodop 兼容 HTTP 服务（网页零改动可用）
"""
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import server
from engine import Job


# ---------------- 与 GUI 无关的核心逻辑（可独立测试） ----------------

def get_paper_info(printer_name: str) -> dict:
    """读取打印机驱动里的纸张设置。返回 {form, w_mm, h_mm, error}"""
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        dm = win32print.GetPrinter(h, 2)["pDevMode"]
        w = getattr(dm, "PaperWidth", 0) or 0     # 0.1mm
        hgt = getattr(dm, "PaperLength", 0) or 0
        form = str(getattr(dm, "FormName", "") or "")
        return {"form": form, "w_mm": w / 10.0, "h_mm": hgt / 10.0}
    except Exception as e:
        return {"form": "?", "w_mm": 0, "h_mm": 0, "error": str(e)}
    finally:
        win32print.ClosePrinter(h)


def build_test_job(text: str, printer: str, paper_w_mm: float, paper_h_mm: float,
                   with_barcode: bool = True, copies: int = 1) -> Job:
    """根据输入文本构造一个铺满当前纸张的打印任务"""
    j = Job(task="dp_printer 手动打印")
    w = paper_w_mm if paper_w_mm > 5 else 100.0
    h = paper_h_mm if paper_h_mm > 5 else 100.0
    j.SET_PRINT_PAGESIZE(1, f"{w:g}mm", f"{h:g}mm")
    j.SET_PRINT_COPIES(copies)

    px_w = w * 96 / 25.4          # LODOP 像素(96dpi)
    px_h = h * 96 / 25.4
    margin = 6 if px_w < 220 else 8
    bw = px_w - margin * 2
    small = px_w < 220            # 小标签（<=约58mm）：用小字号、短落款
    y = margin

    lines = [l for l in text.replace("\r", "").split("\n") if l.strip()]
    if not lines:
        lines = ["(空内容)"]
    # 首行加大加粗（字号随纸宽自适应，避免换行挤压）
    tpt = 14 if not small else 10
    idx = 0
    j.ADD_PRINT_TEXT(y, margin, bw, int(tpt * 1.9), lines[0])
    j.SET_PRINT_STYLEA(idx, "FontSize", tpt)
    j.SET_PRINT_STYLEA(idx, "Bold", 1)
    j.SET_PRINT_STYLEA(idx, "Alignment", 2)
    y += int(tpt * 1.9) + 4
    bpt = 11 if not small else 8
    for ln in lines[1:]:
        idx += 1
        j.ADD_PRINT_TEXT(y, margin, bw, int(bpt * 1.8), ln)
        j.SET_PRINT_STYLEA(idx, "FontSize", bpt)
        y += int(bpt * 1.8) + 3

    # 条码（仅当内容适合时）
    if with_barcode and y < px_h * 0.85:
        code = "".join(c for c in text if 32 < ord(c) < 127)[:30] or "DP"
        bh = min(60, max(30, int(px_h * 0.25)))
        if y + bh + 6 < px_h - 18:
            j.ADD_PRINT_BARCODE(y + 4, margin, bw, bh, "128Auto", code)
            y += bh + 8

    # 底部落款（小标签只打时间，避免换行溢出）
    import time as _t
    foot = _t.strftime('%Y-%m-%d %H:%M:%S') if small else \
        f"{_t.strftime('%Y-%m-%d %H:%M:%S')} · {printer}"
    if y < px_h - 16:
        idx += 1
        j.ADD_PRINT_TEXT(px_h - 16, margin, bw, 14, foot)
        j.SET_PRINT_STYLEA(idx, "FontSize", 6 if small else 7)
        j.SET_PRINT_STYLEA(idx, "Color", "#666666")
    j.printer = printer
    return j


# ---------------- GUI ----------------

class App:
    def __init__(self, root: tk.Tk, port: int):
        self.root = root
        self.port = port
        root.title(f"dp_printer 打印客户端  (服务端口 {port})")
        root.geometry("560x420")
        root.minsize(480, 360)

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)

        # 服务状态
        svc = ttk.Label(frm, text=f"● CLodop 兼容服务运行中：http://localhost:{port}/CLodopfuncs.js",
                        foreground="#187a2f")
        svc.pack(anchor="w", pady=(0, 10))

        # 打印机选择
        row1 = ttk.Frame(frm); row1.pack(fill="x")
        ttk.Label(row1, text="打印机:").pack(side="left")
        self.printer_var = tk.StringVar()
        self.cb = ttk.Combobox(row1, textvariable=self.printer_var, state="readonly", width=36)
        self.cb.pack(side="left", padx=6)
        ttk.Button(row1, text="刷新", command=self.refresh_printers).pack(side="left")
        self.paper_var = tk.StringVar(value="纸张：-")
        ttk.Label(frm, textvariable=self.paper_var, foreground="#555").pack(anchor="w", pady=4)

        # 打印纸张尺寸（可修改，打印时自动同步到打印机驱动）
        row2 = ttk.Frame(frm); row2.pack(fill="x", pady=(2, 0))
        ttk.Label(row2, text="打印纸张:").pack(side="left")
        self.w_var = tk.StringVar(value="40")
        self.h_var = tk.StringVar(value="40")
        ttk.Label(row2, text="宽").pack(side="left", padx=(6, 2))
        ttk.Spinbox(row2, from_=10, to=500, increment=5, width=5,
                    textvariable=self.w_var).pack(side="left")
        ttk.Label(row2, text="mm × 高").pack(side="left", padx=(4, 2))
        ttk.Spinbox(row2, from_=10, to=500, increment=5, width=5,
                    textvariable=self.h_var).pack(side="left")
        ttk.Label(row2, text="mm").pack(side="left", padx=(2, 0))
        ttk.Label(row2, text="（打印前自动同步到驱动，防拉伸）",
                  foreground="#999").pack(side="left", padx=(10, 0))

        # 输入区
        ttk.Label(frm, text="打印内容（每行一条，首行自动加大加粗）:").pack(anchor="w", pady=(12, 2))
        self.text = tk.Text(frm, height=7, font=("Microsoft YaHei", 11))
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", "dp_printer 打印测试\n第二行内容")

        # 选项 + 打印按钮
        row3 = ttk.Frame(frm); row3.pack(fill="x", pady=10)
        self.barcode_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="自动附条码（取内容中的 ASCII 部分）",
                        variable=self.barcode_var).pack(side="left")
        self.copies_var = tk.StringVar(value="1")
        ttk.Label(row3, text="份数:").pack(side="left", padx=(16, 2))
        ttk.Spinbox(row3, from_=1, to=99, width=4, textvariable=self.copies_var).pack(side="left")
        self.btn = ttk.Button(row3, text="打 印", command=self.do_print)
        self.btn.pack(side="right")

        # 日志
        self.log = tk.Text(frm, height=5, font=("Consolas", 9),
                           background="#f4f4f4", state="disabled")
        self.log.pack(fill="x", side="bottom")

        self.refresh_printers()
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.show_paper())

    # ---- 行为 ----
    def logln(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def refresh_printers(self):
        printers, default = server.list_printers()
        self.printers = printers
        self.cb["values"] = printers
        if printers:
            self.printer_var.set(default if default in printers else printers[0])
            self.show_paper()
            self.logln(f"已连接 {len(printers)} 台打印机: {', '.join(printers)}")
        else:
            self.paper_var.set("纸张：未发现打印机")
            self.logln("未发现任何打印机，请检查驱动安装")

    def show_paper(self):
        name = self.printer_var.get()
        if not name:
            return
        info = get_paper_info(name)
        if info.get("error"):
            self.paper_var.set(f"纸张：读取失败 ({info['error']})")
        else:
            self.paper_var.set(
                f"纸张：{info['form'] or '(未命名)'} · "
                f"{info['w_mm']:g} × {info['h_mm']:g} mm")

    def do_print(self):
        name = self.printer_var.get()
        if not name:
            messagebox.showwarning("提示", "请先选择打印机")
            return
        text = self.text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "请输入打印内容")
            return
        try:
            copies = max(1, int(self.copies_var.get() or 1))
        except ValueError:
            copies = 1
        try:
            w_mm = float(self.w_var.get() or 40)
            h_mm = float(self.h_var.get() or 40)
        except ValueError:
            w_mm = h_mm = 40.0
        w_mm = min(500.0, max(10.0, w_mm))
        h_mm = min(500.0, max(10.0, h_mm))
        self.btn.configure(state="disabled", text="打印中…")
        self.root.update_idletasks()

        def worker():
            try:
                # 先把驱动纸张同步为输入尺寸（防内容拉伸到错误纸张上）
                try:
                    from setup_tsc import set_default_paper
                    set_default_paper(name, w_mm, h_mm)
                    time.sleep(0.5)
                    self.root.after(0, lambda: self.show_paper())
                except Exception as pe:
                    self.root.after(0, lambda: self.logln(f"纸张同步失败(仍按 {w_mm:g}x{h_mm:g}mm 排版): {pe}"))
                j = build_test_job(text, name, w_mm, h_mm,
                                   self.barcode_var.get(), copies)
                msg = j.print(name)
                self.root.after(0, lambda: self._done(f"已送打印驱动：{msg}（纸张 {w_mm:g}×{h_mm:g}mm）", ok=True))
            except Exception as e:
                self.root.after(0, lambda: self._done(f"打印失败：{e}", ok=False))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, msg: str, ok: bool):
        self.btn.configure(state="normal", text="打 印")
        self.logln(msg)
        if not ok:
            messagebox.showerror("打印失败", msg)


def run_gui(port: int):
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    App(root, port)
    root.mainloop()


if __name__ == "__main__":
    # 独立运行：先起服务再开窗口
    httpd = None
    for p in server.DEFAULT_PORTS:
        try:
            httpd = server.serve(p)
            break
        except OSError:
            pass
    run_gui(getattr(httpd, "server_port", 0) if httpd else 0)
