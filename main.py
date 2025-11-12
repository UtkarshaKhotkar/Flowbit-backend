from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from groq import Groq
import json

load_dotenv()

app = FastAPI(title="Vanna AI Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+psycopg2://")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Groq client
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY environment variable is required")

groq_client = Groq(api_key=groq_api_key)

# Request/Response models
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    results: list
    error: str = None

# Database schema context for LLM
SCHEMA_CONTEXT = """
Database Schema:
- vendors (id, vendor_id, name, category, created_at, updated_at)
- customers (id, customer_id, name, email, created_at, updated_at)
- invoices (id, invoice_id, vendor_id, customer_id, invoice_date, due_date, total_amount, status, created_at, updated_at)
- line_items (id, item_id, invoice_id, description, quantity, unit_price, total, created_at, updated_at)
- payments (id, payment_id, invoice_id, payment_date, amount, method, created_at, updated_at)

Relationships:
- invoices.vendor_id -> vendors.vendor_id
- invoices.customer_id -> customers.customer_id
- line_items.invoice_id -> invoices.id
- payments.invoice_id -> invoices.id
"""

def generate_sql(natural_language_query: str) -> str:
    """Generate SQL query from natural language using Groq."""
    
    prompt = f"""
You are a SQL expert. Given the following database schema and a natural language query, generate a valid PostgreSQL SQL query.

{SCHEMA_CONTEXT}

Natural Language Query: {natural_language_query}

Generate ONLY the SQL query without any explanation. The query should:
1. Be valid PostgreSQL syntax
2. Use proper table and column names from the schema
3. Be safe (no DROP, DELETE, UPDATE, INSERT, ALTER statements)
4. Return meaningful results

SQL Query:
"""
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a SQL expert. Generate only valid PostgreSQL queries based on the schema and user query."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama3-8b-8192",  # Fast and efficient model
            temperature=0.1,
            max_tokens=500
        )
        
        sql_query = chat_completion.choices[0].message.content.strip()
        
        # Clean up SQL query (remove markdown code blocks if present)
        if sql_query.startswith("```"):
            sql_query = sql_query.split("```")[1]
            if sql_query.startswith("sql"):
                sql_query = sql_query[3:].strip()
        
        return sql_query
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating SQL: {str(e)}")

def execute_sql(sql_query: str) -> list:
    """Execute SQL query and return results."""
    db = SessionLocal()
    try:
        # Validate query (prevent dangerous operations)
        sql_lower = sql_query.lower().strip()
        dangerous_keywords = ['drop', 'delete', 'update', 'insert', 'alter', 'truncate', 'create', 'grant', 'revoke']
        
        for keyword in dangerous_keywords:
            if keyword in sql_lower:
                raise HTTPException(
                    status_code=400,
                    detail=f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed."
                )
        
        result = db.execute(text(sql_query))
        
        # Convert result to list of dictionaries
        columns = result.keys()
        rows = result.fetchall()
        
        results = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convert non-serializable types
                if hasattr(value, 'isoformat'):  # datetime objects
                    value = value.isoformat()
                elif hasattr(value, '__float__'):  # Decimal types
                    value = float(value)
                row_dict[col] = value
            results.append(row_dict)
        
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing SQL: {str(e)}")
    finally:
        db.close()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "vanna-ai"}

@app.post("/query", response_model=QueryResponse)
async def query_data(request: QueryRequest):
    """
    Process natural language query and return SQL + results.
    
    Example queries:
    - "Show me total spend by vendor"
    - "What are the top 5 customers by invoice amount?"
    - "How many invoices were paid in January?"
    """
    try:
        # Generate SQL from natural language
        sql_query = generate_sql(request.query)
        
        # Execute SQL
        results = execute_sql(sql_query)
        
        return QueryResponse(
            query=sql_query,
            results=results
        )
    except HTTPException:
        raise
    except Exception as e:
        return QueryResponse(
            query="",
            results=[],
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)




