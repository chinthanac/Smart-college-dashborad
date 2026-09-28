# Smart College System Backend

This backend provides the initial authentication foundation for the Smart College System.

## Quick start

1. Create a virtual environment:
   python3 -m venv venv
2. Activate it:
   source venv/bin/activate
3. Install dependencies:
   pip install -r requirements.txt
4. Start the API:
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## Environment

A PostgreSQL instance is expected at:
- Host: localhost
- Port: 5432
- Database: smart_college
- User: postgres
- Password: postgres
