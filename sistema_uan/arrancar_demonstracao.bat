@echo off
rem Arranca o Sistema UAN no modo de demonstracao (dados ficticios, sem Internet).
rem Uso: duplo clique neste ficheiro, ou na linha de comandos: arrancar_demonstracao.bat
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Sistema UAN - modo de demonstracao ===
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERRO] O Python nao foi encontrado. Instale o Python 3.11 ou superior.
  pause
  exit /b 1
)
python -c "import fastapi, uvicorn, jinja2, multipart" >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Faltam bibliotecas. Execute: python -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo O navegador abre dentro de 15 segundos; espere pela mensagem PRONTO.
start "" /min cmd /c "timeout /t 15 /nobreak >nul & start http://127.0.0.1:8000"
python uan.py servir --demonstracao
pause
