@echo off
setlocal
cd /d "%~dp0"

set PYTHONIOENCODING=utf-8
set PYTHONDONTWRITEBYTECODE=1

if not exist ".venv_win\pyvenv.cfg" (
    echo Recreating Python virtual environment...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath '.venv_win') { Remove-Item -LiteralPath '.venv_win' -Recurse -Force }"
    python -m venv .venv_win
)

if not exist ".env" (
    > .env echo DATABASE_URL=postgresql+pg8000://postgres:your_password@localhost:5432/kiryana
    >> .env echo SECRET_KEY=dev-secret-key
    >> .env echo JWT_SECRET_KEY=kiryana-jwt-key-2025
    >> .env echo FLASK_ENV=development
    >> .env echo FLASK_APP=run.py
)

".venv_win\Scripts\python.exe" -m pip install -r requirements.txt

set FLASK_ENV=development
set FLASK_APP=run.py

".venv_win\Scripts\python.exe" -c "from app import create_app; from app.models import db; app=create_app(); app.app_context().push(); db.create_all(); print('Database ready')"

echo.
echo Kiryana is starting at http://127.0.0.1:5000
echo Login:
echo   Admin:  admin@kiryana.pk / admin123
echo.
".venv_win\Scripts\python.exe" run.py
pause
