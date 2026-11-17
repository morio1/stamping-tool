@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
if errorlevel 1 (pause & exit /b 1)
.venv\Scripts\python.exe -c "import pymupdf; import PIL; import tkinter" >nul 2>&1
if not errorlevel 1 goto launch
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
:launch
.venv\Scripts\python.exe app.py
if errorlevel 1 pause
