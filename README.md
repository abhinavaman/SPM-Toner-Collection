# SPM Toner Collection Data-Collection Project

Purpose: replace the paper toner-collection form with a simple digital record system.

## Stack
Python + Flask + SQLite + HTML/CSS

## Run
1. Install Python.
2. Open Command Prompt in this folder.
3. Run:
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
4. Open http://127.0.0.1:5000

The first run creates `toner.db`.

## Current scope
- Collect employee/toner details
- Store records
- View records
- Count total records and unique employees
- Export CSV

No inventory, approval workflow, notifications, or authentication are included yet.

For use on the SPM LAN, host it only on a company-approved machine/server and follow SPM IT security procedures.
