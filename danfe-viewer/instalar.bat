@echo off
rem Cria o ambiente do programa (so precisa rodar UMA vez).
cd /d "%~dp0"
py -3 -m venv .venv || (echo Python nao encontrado. Instale em python.org e marque "Add python.exe to PATH". & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Pronto! Agora de dois cliques em abrir.bat
pause
