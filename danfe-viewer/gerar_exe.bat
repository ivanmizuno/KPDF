@echo off
rem Gera dist\DANFE-Viewer\DANFE-Viewer.exe (programa que roda sem instalar Python).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name DANFE-Viewer --paths . danfe_viewer\__main__.py
echo.
echo Pronto: pasta dist\DANFE-Viewer
pause
