#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
if [ ! -f data/rsl_gestion.db ]; then
  python import_data.py "../sources/Clients.xlsx" "../sources/produits euro.xlsx"
fi
exec uvicorn app:app --host 127.0.0.1 --port 8000
