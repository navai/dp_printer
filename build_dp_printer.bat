@echo off
rem dp_printer 打包脚本：重新生成 dist\dp_printer.exe（图形客户端版）
rem 前置：C:\Programs\Python\Python312 已安装
rem       pillow pywin32 python-barcode qrcode pdf417gen pyinstaller
cd /d "%~dp0"
set PY=C:\Programs\Python\Python312\python.exe
%PY% -m PyInstaller --noconfirm --clean --onefile --noconsole --name dp_printer ^
    --add-data "CLodopfuncs.js;." --add-data "demo.html;." gui.py
echo.
echo 打包完成: dist\dp_printer.exe
pause
