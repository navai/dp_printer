# dp_printer

**A drop-in replacement for the CLodop cloud-print service — single exe, zero code changes for your web pages.**
LODOP 兼容打印中间件 —— 复现 CLodop（泰山办公 MountTaiSoftware 云打印）的浏览器打印能力，网页前端**一行代码都不用改**。

> 版本 v4（全 API 覆盖） · 2026-11 · 为单采血浆系统（阳信系统）打印中间件交接而做
>
> **最快上手：双击 `dist\dp_printer.exe` 即启动打印服务，无需安装 Python。**

---

## 一、它主要解决了什么问题

单采系统网页端打印标签，依赖泰山办公的闭源软件 **CLodop**（安装包 `CLodop_Setup_for_Win32NT.exe`）。这个软件带来几个实际问题：

| 原来的痛点 | dp_printer 的解法 |
|---|---|
| **闭源**，出问题无法排查、无法定制 | 全部源码可见（纯 Python），渲染引擎 / 条码 / 模板都是自己的代码 |
| **安装包无法自动化部署**（图形安装、UAC、静默参数不明） | **单文件 exe 直接运行**，免安装、免 Python 环境，可脚本化、可开机自启 |
| **打印行为是黑盒**：坐标怎么算、条码怎么生成，无人知晓 | 协议与坐标体系已逆向清楚（LODOP 坐标 = 96dpi 像素，字号 = pt），行为可预期、可复现 |
| **换打印机/换纸张要手动调驱动** | 渲染端按毫米等比缩放适配纸张；附 `setup_tsc.py` 一键把 TSC 打印机配成 4×4 英寸 |
| **老系统没有源码**，打印模板无法维护 | 原始模板已从前端 sourcemap 还原，并移植为 `templates.py`（服务端可直调） |
| 商业授权 / 版本升级不可控 | 无依赖、无授权，代码即资产，可长期维护 |

一句话：**把一个闭源的浏览器打印中间件，变成一个看得懂、改得动、装得上的单文件程序。**

## 二、功能特性

- **CLodop 兼容**：在 `8000/18000` 端口提供 `/CLodopfuncs.js`，原网页里的
  `getCLodop() → LODOP.PRINT_INITA/ADD_PRINT_TEXT/... → PRINTB()` 调用链原样工作。
- **API 覆盖 74 个（v4 全部实现）**：与官方 6.647 手册逐条对照，文本全样式
  （旋转/行距/页眉页脚/页号页数）、图形（矩形/椭圆/斜线/实心）、
  **条码 23 类**（Code128 全系、Code39/93、EAN8/13、UPC-A/E、ITF、MSI、PostNet、
  Codabar、**QRCode**、**PDF417** 等）、HTM/TABLE/URL 渲染、图表、多页分页、
  文档式模板（ADD_PRINT_DATA）、RAW 直发；未实现语义的命令 Proxy 兜底记录警告。
- **单文件 exe**：`dp_printer.exe`（约 16MB）内置 Python 运行时与全部资源，
  拷贝到任何 Windows 10/11 x64 机器上双击即可用；端口被占用时自动依次
  尝试 8000 → 18000 → 8010 → 18010 → 8020 → 18020。
- **原始指令直发**：`SEND_PRINT_RAWDATA` 支持 TSPL/ZPL 直发热敏打印机
  （不经渲染，速度快、纸张由指令精确控制）。
- **渲染引擎**：纯 Python —— LODOP 坐标(96dpi px) → 毫米 → Pillow 位图 →
  `win32print` GDI 送打；中文（宋体/黑体）、加粗、对齐、Code128(A/B/C)、Code39。
- **双模板内置**：单采系统两个真实标签模板已移植成 Python 函数
  （`templates.py`），可脱离浏览器由服务端/定时任务直接打印。
- **HTTP 任务接口**：`POST /clodop/render`（返回预览页）与
  `POST /clodop/print`（直接送打），方便其他系统按 JSON 调用。
- **预览能力**：每个渲染任务生成 `/preview/<id>` 网页，手机/电脑都能看。

## 三、使用方法

### 1. 直接运行（推荐，免安装）

**双击 `dp_printer.exe` 弹出图形打印客户端**：

- 顶部显示 **当前连接的打印机**（下拉可切换、可刷新），默认选中系统默认打印机
- 打印机下方实时显示 **纸张尺寸**（从驱动 DEVMODE 读取，如 `Photo 4x 4 · 101.6 × 101.6 mm`）
- 输入框输入打印内容（每行一条，首行自动加大加粗），可选自动附条码、份数
- 点 **【打 印】** 即通过 Windows 驱动真实出纸，底部日志显示送打结果
- 窗口后台同时运行 CLodop 兼容服务（标题栏显示端口），网页照常零改动可用

**纯服务模式**（无人值守/开机自启）：`dp_printer.exe -p 18000` 或 `python server.py`，
控制台输出 `dp_printer 打印服务已启动: http://localhost:8000/CLodopfuncs.js`
即成功；浏览器打开 `http://localhost:8000/demo` 可直接体验。

### 2. 服务端直接打印（不走浏览器，需源码方式运行）

```python
from templates import print_donor_label, SAMPLE_DONOR

job = print_donor_label(SAMPLE_DONOR)   # 浆员登记标签 50x50mm
job.print()                             # 送系统默认打印机
job.print("TSC TE344")                  # 指定打印机
job.print("Microsoft Print to PDF")     # 输出 PDF 验证版面
```

### 3. HTTP 调用（其他系统对接）

```bash
curl -X POST -H "Content-Type: application/json" \
     --data-binary @job.json http://localhost:8000/clodop/print
# job.json 结构见 test_job.json 示例；/clodop/render 返回预览页 id
```

### 4. 部署到现场机器（替换官方 CLodop，网页零改动）

```bash
# ① 装 TSC 打印机驱动（驱动包在交接材料 TSC_WHQL_2023.3.1/）
pnputil -add-driver TSC.inf -install
pnputil -scan-devices

# ② 一键把打印机默认纸张配成 4x4 英寸（不会改动其他打印设置）
python setup_tsc.py          # 或 python setup_tsc.py --list 查看打印机名

# ③ 运行 dp_printer.exe；开机自启用任务计划程序注册该 exe 即可
```

> 原系统网页的 `LodopFuncs.js` 会自动加载 `http://localhost:8000/CLodopfuncs.js`，
> 本服务在同一端口提供自研桩，浏览器感知不到替换。

## 四、项目结构

```
dp_printer/
├── dist/
│   └── dp_printer.exe   ★ 单文件成品（双击即用）
├── server.py            HTTP 服务：/CLodopfuncs.js、/clodop/render、/clodop/print、
│                        /clodop/printers、/preview/<id>、/demo
├── gui.py               图形打印客户端（exe 打包入口）：打印机列表/纸张尺寸/输入即打
├── CLodopfuncs.js       前端兼容桩：getCLodop()/CLODOP，74 个 API + Proxy 兜底
├── engine.py            渲染引擎：坐标换算、文本/条码/图片/多页、GDI 送打、RAW 直发
├── barcode_legacy.py    早期独立条码模块（现由 core/barcodes.py 接管）
├── templates.py         单采两个真实标签模板（与原 donor.js 逐行对应）
├── demo.html            浏览器演示页
├── setup_tsc.py         TSC 打印机纸张配置（装驱动后跑一次）
├── core/                单位换算 / 条码编码 / HTML 子集渲染器
├── tests/api_coverage.py  全 API 覆盖测试（75/75）
├── build_dp_printer.bat 打包命令（重新生成 exe 用）
└── out/                 预览 PNG 输出目录
```

## 五、从源码重新打包 exe

```bash
# 前置：Python 3.12+（需带 tkinter）并安装依赖
pip install pillow pywin32 python-barcode qrcode pdf417gen pyinstaller
# 双击 build_dp_printer.bat，或手动：
python -m PyInstaller --onefile --noconsole --name dp_printer ^
    --add-data "CLodopfuncs.js;." --add-data "demo.html;." gui.py
# 产物: dist\dp_printer.exe（图形客户端，双击即用）
```

## 六、实测记录（TSC TE344 真机）

- 驱动：`pnputil -add-driver TSC.inf -install` 非交互安装成功（设备 `VID_1203&PID_0273`）。
- 位图通路：浆员登记标签 → 驱动打印，队列正常清空。
- RAW 通路：TSPL 直发（SIZE/CLS/TEXT/BARCODE/PRINT）成功。
- exe 版：本机 8000 被占时自动落到 18000，全部接口 200，真实出票成功。
- **注意**：TSC 驱动默认纸张是 104×152mm(4×6")，必须先跑 `setup_tsc.py` 改成
  4×4 英寸，否则标签内容会被拉伸放大。

## 七、已知限制

- `ADD_PRINT_HTM / ADD_PRINT_TABLE` 未实现（单采标签未用到）。
- 条码支持 128A/B/C、Code39；EAN13/PDF417 未做。
- 位图打印按毫米等比缩放适配驱动纸张；如需 1:1 毫米定位可在
  `engine.Job.print()` 中关闭缩放。
- exe 仅支持 Windows 10/11 x64；如需其他平台需另行打包。

## 八、逆向与合规说明

- 官方 `CLodop_Setup_for_Win32NT.exe` 已成功**静态**解包（未运行安装程序）：
  overlay 为 `zlb\x1a` 魔数 + 裸 LZMA1 流 → 16.4MB Delphi 主程序 →
  内嵌分块资源重组出官方 CLodopfuncs.js 的 **74 个 API** 与 WebSocket `/c_webskt/`
  传输方式。过程与产物见 `../re/逆向报告-CLodop安装包.md`。
- 本项目为 **clean-room 实现**：官方提取物仅用于协议对照，未复制任何官方代码。
  官方资源属商业软件，提取物仅限本地对照分析，**请勿分发**。
