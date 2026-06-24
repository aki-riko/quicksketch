@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 优先用本地 venv,没有则回退系统 python
if exist ".venv\Scripts\pythonw.exe" (
    ".venv\Scripts\pythonw.exe" main.py
) else (
    echo 未找到 .venv,尝试用系统 Python 运行...
    echo 若报缺少模块,请先执行: pip install -r requirements.txt
    python main.py
)
