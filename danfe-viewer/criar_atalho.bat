@echo off
rem Cria o atalho "DANFE Viewer" na Area de Trabalho (abre sem janela preta).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Rode primeiro o instalar.bat.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\DANFE Viewer.lnk'); $s.TargetPath='%~dp0.venv\Scripts\pythonw.exe'; $s.Arguments='-m danfe_viewer'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0danfe_viewer\assets\icon.ico'; $s.Description='Visualizar e imprimir DANFE'; $s.Save()"
if errorlevel 1 (echo Nao foi possivel criar o atalho. & pause & exit /b 1)
echo.
echo Atalho "DANFE Viewer" criado na Area de Trabalho.
pause
