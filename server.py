# -*- coding: utf-8 -*-
"""
dp_printer 打印服务（CLodop 兼容）

模拟 CLodop 的对外形态：
  GET  http://localhost:8000/CLodopfuncs.js   前端兼容桩（网页不用改）
  GET  http://localhost:18000/CLodopfuncs.js  备用端口
  POST /clodop/render   任务 JSON → 渲染 PNG（预览）
  POST /clodop/print    任务 JSON → 送 Windows 打印驱动
  GET  /clodop/printers 打印机列表
  GET  /preview/<id>    预览页

用法：
  dp_printer.exe              # 默认 8000（被占用时自动试 18000）
  dp_printer.exe -p 18000
  python server.py -p 18000   # 源码方式运行
"""
import base64
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_NAME = "dp_printer"


def res_path(name):
    """兼容 PyInstaller 打包：资源文件优先从 _MEIPASS 解包目录取"""
    base = getattr(sys, "_MEIPASS", None)
    if base and os.path.exists(os.path.join(base, name)):
        return os.path.join(base, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import job_from_json                    # noqa: E402

JS_FILE = res_path("CLodopfuncs.js")
DEMO_FILE = res_path("demo.html")

PREVIEWS = {}          # id -> (png_bytes, timestamp, task)
PREVIEW_MAX = 30


def list_printers():
    try:
        import win32print
        names = [p[2] for p in win32print.EnumPrinters(2)]
        return names, win32print.GetDefaultPrinter()
    except Exception as e:
        return [], f"枚举打印机失败: {e}"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---------------- 基础输出 ----------------
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---------------- 路由 ----------------
    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/CLodopfuncs.js"):
            with open(JS_FILE, "rb") as f:
                self._send(200, f.read(), "application/javascript; charset=utf-8")
        elif path == "/demo" or path == "/demo.html":
            with open(DEMO_FILE, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif path == "/" or path == "/clodop/health":
            printers, default = list_printers()
            self._json(200, {"service": APP_NAME, "status": "ok",
                             "printers": printers, "default": default})
        elif path == "/clodop/printers":
            printers, default = list_printers()
            self._json(200, {"printers": printers, "default": default})
        elif path.startswith("/preview/"):
            pid = path.split("/")[-1]
            rec = PREVIEWS.get(pid)
            if not rec:
                self._send(404, b"preview not found", "text/plain; charset=utf-8")
                return
            pages, ts, task = rec
            imgs = "".join(
                f'<img src="data:image/png;base64,{p}">' for p in pages)
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>打印预览 - {task}</title>
<style>body{{background:#555;margin:0;padding:16px;text-align:center}}
img{{background:#fff;box-shadow:0 2px 12px rgba(0,0,0,.5);max-width:100%;margin-bottom:12px}}</style></head>
<body>{imgs}<p style="color:#eee">{task} · {len(pages)} 页 · 渲染于 {time.strftime('%H:%M:%S', time.localtime(ts))}</p></body></html>"""
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json(404, {"error": f"unknown path {path}"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception as e:
            self._json(400, {"error": f"JSON 解析失败: {e}"})
            return

        j = job_from_json(data)
        if path == "/clodop/render":
            pages = j.render_png_b64_pages()
            pid = uuid.uuid4().hex[:12]
            PREVIEWS[pid] = (pages, time.time(), j.task)
            if len(PREVIEWS) > PREVIEW_MAX:      # 只保留最近 N 个预览
                for k in sorted(PREVIEWS, key=lambda k: PREVIEWS[k][1])[:-PREVIEW_MAX]:
                    PREVIEWS.pop(k, None)
            self._json(200, {"ok": True, "id": pid, "pages": len(pages),
                             "warnings": j.warnings})
        elif path == "/clodop/print":
            try:
                msg = j.print()
                self._json(200, {"ok": True, "message": msg, "warnings": j.warnings})
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e), "warnings": j.warnings})
        else:
            self._json(404, {"error": f"unknown path {path}"})


class Server(ThreadingHTTPServer):
    # Windows 下 SO_REUSEADDR 会允许重复绑定已占用端口（请求被旧服务抢走），
    # 必须关闭，让绑定冲突真实抛错，端口探测逻辑才能生效
    allow_reuse_address = False


def serve(port=8000):
    httpd = Server(("0.0.0.0", port), Handler)
    printers, default = list_printers()
    print(f"{APP_NAME} 打印服务已启动: http://localhost:{port}/CLodopfuncs.js")
    print(f"默认打印机: {default} | 全部: {printers}")
    print("按 Ctrl+C 退出。")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


DEFAULT_PORTS = (8000, 18000, 8010, 18010, 8020, 18020)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--port", type=int, default=8000)
    args = ap.parse_args()
    httpd = None
    ports = [args.port] + [p for p in DEFAULT_PORTS if p != args.port]
    for p in ports:
        try:
            httpd = serve(p)
            break
        except OSError:
            print(f"端口 {p} 被占用，尝试下一个 ...")
    if httpd is None:
        print("所有候选端口都被占用，退出。")
        sys.exit(1)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("已退出")
