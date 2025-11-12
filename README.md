# Vanna AI Service

Python FastAPI service for natural language to SQL conversion using Groq.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create `.env`):
```env
DATABASE_URL=postgresql://user:password@localhost:5432/flowbit_db
GROQ_API_KEY=your_groq_api_key_here
PORT=8000
```

3. Start development server:
```bash
python main.py
# or
uvicorn main:app --reload
```

The service will run on http://localhost:8000

## Endpoints

- `GET /health` - Health check
- `POST /query` - Process natural language query and return SQL + results

## Getting Groq API Key

1. Go to https://console.groq.com
2. Sign up or log in
3. Create an API key
4. Add it to your `.env` file




