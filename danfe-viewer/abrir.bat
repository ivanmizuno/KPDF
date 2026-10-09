@echo off
rem Abre o DANFE Viewer. Voce tambem pode arrastar um XML para cima deste arquivo.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m danfe_viewer %*
