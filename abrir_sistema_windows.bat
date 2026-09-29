@echo off
REM Atalho para abrir o sistema Claquete CRM/ERP com um clique duplo.
REM Ativa o ambiente virtual e roda o Streamlit automaticamente.
cd /d "%~dp0"

if not exist venv (
    echo Ambiente virtual nao encontrado. Rode primeiro:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
streamlit run app.py
pause
