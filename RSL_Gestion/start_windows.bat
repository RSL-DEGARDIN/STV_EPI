@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if not exist data\rsl_gestion.db python import_data.py "..\sources\Clients.xlsx" "..\sources\produits euro.xlsx"
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
