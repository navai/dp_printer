@echo off
rem dp_printer 打包脚本：重新生成 dist\dp_printer.exe
rem 前置：pip install pillow pywin32 pyinstaller
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --console --name dp_printer ^
    --add-data "CLodopfuncs.js;." --add-data "demo.html;." server.py
echo.
echo 打包完成: dist\dp_printer.exe
pause
