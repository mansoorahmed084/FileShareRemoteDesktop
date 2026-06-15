@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe native_host.py
) else (
    python native_host.py
)
