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
                   with_barcode: bool = True, copies: int = 1,
                   font_pt: int | None = None) -> Job:
    """根据输入文本构造一个铺满当前纸张的打印任务

    font_pt: 指定正文字号(pt)；None 或 0 = 自动（随纸宽自适应）
    """
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
    # 首行加大加粗（字号随纸宽自适应，避免换行挤压；也可手动指定）
    tpt = (14 if not small else 10) if not font_pt else int(font_pt)
    idx = 0
    j.ADD_PRINT_TEXT(y, margin, bw, int(tpt * 1.9), lines[0])
    j.SET_PRINT_STYLEA(idx + 1, "FontSize", tpt)      # 引擎索引从 1 开始
    j.SET_PRINT_STYLEA(idx + 1, "Bold", 1)
    j.SET_PRINT_STYLEA(idx + 1, "Alignment", 2)
    y += int(tpt * 1.9) + 4
    bpt = (11 if not small else 8) if not font_pt else max(6, int(font_pt) - 3)
    for ln in lines[1:]:
        idx += 1
        j.ADD_PRINT_TEXT(y, margin, bw, int(bpt * 1.8), ln)
        j.SET_PRINT_STYLEA(idx + 1, "FontSize", bpt)
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
        j.SET_PRINT_STYLEA(0, "FontSize", 6 if small else 7)   # 0 = 最近一条
        j.SET_PRINT_STYLEA(0, "Color", "#666666")
    j.printer = printer
    return j


# ---------------- GUI ----------------

class App:
    def __init__(self, root: tk.Tk, port: int):
        self.root = root
        self.port = port
        root.title(f"dp_printer 打印客户端  (服务端口 {port})")
        root.geometry("620x560")
        root.minsize(560, 480)

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
        ttk.Spinbox(row2, from_=15, to=500, increment=5, width=5,
                    textvariable=self.w_var).pack(side="left")
        ttk.Label(row2, text="mm × 高").pack(side="left", padx=(4, 2))
        ttk.Spinbox(row2, from_=15, to=500, increment=5, width=5,
                    textvariable=self.h_var).pack(side="left")
        ttk.Label(row2, text="mm").pack(side="left", padx=(2, 0))
        ttk.Button(row2, text="读取驱动纸张", width=11,
                   command=self.load_driver_paper).pack(side="left", padx=(8, 0))
        ttk.Label(row2, text="（打印前自动同步到驱动，防拉伸）",
                  foreground="#999").pack(side="left", padx=(10, 0))

        # 字号（打印与预览共用；0 = 自动）
        row2b = ttk.Frame(frm); row2b.pack(fill="x", pady=(6, 0))
        ttk.Label(row2b, text="字号:").pack(side="left")
        self.font_var = tk.StringVar(value="0")
        ttk.Spinbox(row2b, from_=0, to=72, increment=1, width=5,
                    textvariable=self.font_var).pack(side="left", padx=(4, 2))
        ttk.Label(row2b, text="pt（0=自动；首行自动加粗并比正文大 3pt）",
                  foreground="#999").pack(side="left", padx=(4, 0))

        # 预览区：输入框与纸张同比例（所见即所得）
        ttk.Label(frm, text="打印内容预览（与纸张同比例，白框即标签纸；每行一条，首行加大加粗）:",
                  ).pack(anchor="w", pady=(10, 2))
        self.preview_holder = ttk.Frame(frm)
        self.preview_holder.pack(fill="both", expand=True)
        self.text = tk.Text(self.preview_holder, font=("Microsoft YaHei", 11),
                            wrap="word", background="white", relief="solid",
                            borderwidth=1, highlightthickness=0, undo=True)
        self.text.pack_forget()
        self.text.place(x=4, y=4)          # 尺寸由 update_preview 按纸张比例设置
        self.text.insert("1.0", "dp_printer 打印测试\n第二行内容")
        self.barcode_strip = tk.Canvas(self.preview_holder, highlightthickness=0,
                                       background="#ffffff")

        # 选项 + 偏移微调 + 打印按钮
        row3 = ttk.Frame(frm); row3.pack(fill="x", pady=10)
        self.barcode_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="自动附条码（取内容中的 ASCII 部分）",
                        variable=self.barcode_var,
                        command=self.update_preview).pack(side="left")
        self.copies_var = tk.StringVar(value="1")
        ttk.Label(row3, text="份数:").pack(side="left", padx=(16, 2))
        ttk.Spinbox(row3, from_=1, to=99, width=4, textvariable=self.copies_var).pack(side="left")
        self.dx_var = tk.StringVar(value="0")
        self.dy_var = tk.StringVar(value="0")
        ttk.Label(row3, text="偏移微调 横:").pack(side="left", padx=(16, 2))
        ttk.Spinbox(row3, from_=-20, to=20, increment=0.5, width=5,
                    textvariable=self.dx_var).pack(side="left")
        ttk.Label(row3, text="纵:").pack(side="left", padx=(6, 2))
        ttk.Spinbox(row3, from_=-20, to=20, increment=0.5, width=5,
                    textvariable=self.dy_var).pack(side="left")
        ttk.Label(row3, text="mm").pack(side="left", padx=(2, 0))
        self.btn = ttk.Button(row3, text="打 印", command=self.do_print)
        self.btn.pack(side="right")

        # 日志
        self.log = tk.Text(frm, height=4, font=("Consolas", 9),
                           background="#f4f4f4", state="disabled")
        self.log.pack(fill="x", side="bottom")

        self.refresh_printers()
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.show_paper())

        # 预览联动：纸张宽高 / 字号 / 窗口尺寸变化 → 重算预览
        for var in (self.w_var, self.h_var, self.font_var):
            var.trace_add("write", self.update_preview)
        self.text.bind("<KeyRelease>", lambda e: self.retag_preview())
        self.preview_holder.bind("<Configure>", self.update_preview)
        root.after(100, self.update_preview)

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

    def load_driver_paper(self):
        """把当前打印机驱动里的纸张尺寸读入宽/高输入框"""
        name = self.printer_var.get()
        if not name:
            messagebox.showwarning("提示", "请先选择打印机")
            return
        info = get_paper_info(name)
        if info.get("error") or info["w_mm"] <= 5 or info["h_mm"] <= 5:
            messagebox.showwarning("提示", f"读取失败：{info.get('error') or '纸张尺寸无效'}")
            return
        self.w_var.set(f"{info['w_mm']:g}")
        self.h_var.set(f"{info['h_mm']:g}")
        self.logln(f"已读取驱动纸张 {info['form'] or '(未命名)'}: "
                   f"{info['w_mm']:g} × {info['h_mm']:g} mm")

    # ---- 预览（与纸张同比例） ----
    PREVIEW_MAX_W = 380
    PREVIEW_MAX_H = 230

    def update_preview(self, *_):
        """按纸张宽高比设置预览框像素尺寸，并按同比例缩放字号"""
        try:
            w_mm = min(500.0, max(15.0, float(self.w_var.get() or 40)))
            h_mm = min(500.0, max(15.0, float(self.h_var.get() or 40)))
        except ValueError:
            w_mm = h_mm = 40.0
        px_w = w_mm * 96 / 25.4          # 打印时用的 LODOP 像素
        px_h = h_mm * 96 / 25.4
        aw = self.preview_holder.winfo_width() - 12
        ah = self.preview_holder.winfo_height() - 12
        if aw < 60: aw = self.PREVIEW_MAX_W
        if ah < 60: ah = self.PREVIEW_MAX_H
        scale = min(aw / px_w, ah / px_h)
        try:
            self.text.place(x=4, y=4, width=int(px_w * scale), height=int(px_h * scale))
        except tk.TclError:
            return
        self._apply_preview_fonts(px_w, scale)
        self._update_barcode_strip(px_w, px_h, scale)

    def _update_barcode_strip(self, px_w: float, px_h: float, scale: float):
        """在预览底部画一个条码占位条（与打印布局一致）"""
        strip = self.barcode_strip
        if not self.barcode_var.get():
            strip.place_forget()
            return
        bh = min(60, max(30, int(px_h * 0.25)))       # 与 build_test_job 相同
        sh = max(8, int(bh * scale))
        bottom_gap = max(4, int(18 * scale))
        sw = int(px_w * scale) - max(2, int(12 * scale))
        strip.place(x=4, y=4 + int(px_h * scale) - bottom_gap - sh,
                    width=max(20, sw), height=sh)
        strip.delete("all")
        code = "".join(c for c in self.text.get("1.0", "end")
                       if 32 < ord(c) < 127)[:30] or "DP"
        x = 2.0
        i = 0
        while x < sw - 3:
            c = ord(code[i % len(code)]) + i
            bw = 1 + (c % 3)
            gap = 1 + (c % 2)
            strip.create_rectangle(x, 0, x + bw, sh, fill="#111111", width=0)
            x += bw + gap
            i += 1
        strip.tk.call("raise", strip._w)              # 置顶显示（该区域不参与编辑）

    def _apply_preview_fonts(self, px_w: float, scale: float):
        try:
            font_pt = int(float(self.font_var.get() or 0))
        except ValueError:
            font_pt = 0
        small = px_w < 220               # 与 build_test_job 的自适应规则一致
        if font_pt > 0:
            base, body = font_pt, max(6, font_pt - 3)
        else:
            base, body = (10 if small else 14), (8 if small else 11)
        f_first = ("Microsoft YaHei", max(5, round(base * scale)), "bold")
        f_body = ("Microsoft YaHei", max(5, round(body * scale)))
        self.text.tag_configure("first", font=f_first, spacing1=2,
                                spacing3=2, justify="center")
        self.text.tag_configure("body", font=f_body, spacing1=2)
        self.retag_preview()

    def retag_preview(self):
        """按行套用 first/body 标签（不移动光标）"""
        self.text.tag_remove("first", "1.0", "end")
        self.text.tag_remove("body", "1.0", "end")
        lines = self.text.get("1.0", "end").split("\n")
        for i, ln in enumerate(lines):
            if ln:
                self.text.tag_add("first" if i == 0 else "body",
                                  f"{i + 1}.0", f"{i + 1}.{len(ln)}")

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
        w_mm = min(500.0, max(15.0, w_mm))     # 驱动最小纸张限制，防止放大截断
        h_mm = min(500.0, max(15.0, h_mm))
        try:
            font_pt = int(float(self.font_var.get() or 0))
        except ValueError:
            font_pt = 0
        try:
            dx_mm = min(20.0, max(-20.0, float(self.dx_var.get() or 0)))
        except ValueError:
            dx_mm = 0.0
        try:
            dy_mm = min(20.0, max(-20.0, float(self.dy_var.get() or 0)))
        except ValueError:
            dy_mm = 0.0
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
                                   self.barcode_var.get(), copies,
                                   font_pt=font_pt or None)
                j.dx_mm, j.dy_mm = dx_mm, dy_mm
                msg = j.print(name)
                self.root.after(0, lambda: self._done(
                    f"已送打印驱动：{msg}（纸张 {w_mm:g}×{h_mm:g}mm，"
                    f"偏移 {dx_mm:g}/{dy_mm:g}mm）", ok=True))
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
