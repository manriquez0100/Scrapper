@echo off
cd C:\Users\DATA-MESACNTL3\scrapper\Scrapper
call .venv\Scripts\activate
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000