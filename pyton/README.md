# AI-Powered Document Intelligence API

A production-ready FastAPI service that extracts text from PDF/DOCX files and performs intelligent analysis using OpenAI's structured output API with Pydantic validation.

## Architecture Overview

**Flow:**
```
POST /api/v1/documents/upload
      │
      ├── Validate extension + file size
      ├── Insert DB row (status=pending)
      ├── Return 202 immediately  ← fast response
      │
      └── BackgroundTask:
            ├── extract_text()   ← PyMuPDF / python-docx
            ├── analyze_document() ← OpenAI structured output
            │     └── Pydantic validates LLM JSON automatically
            └── Persist to PostgreSQL (status=completed)

GET /api/v1/documents/{id}   ← client polls for results
```

## Project Structure

```
docai/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app with rate limiting
│   ├── config.py                  # Pydantic settings
│   ├── database.py                # SQLAlchemy async setup
│   ├── models/
│   │   ├── db_models.py          # SQLAlchemy models
│   │   └── schemas.py            # Pydantic schemas + LLM output validation
│   ├── api/v1/
│   │   └── documents.py          # Upload, retrieve, list endpoints
│   └── services/
│       ├── extractor.py          # PDF/DOCX text extraction
│       └── llm_service.py        # OpenAI structured output analysis
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Key Features

- **Async Processing**: Background tasks keep upload latency <100ms
- **Structured LLM Output**: OpenAI's `response_format` enforces Pydantic schema
- **Auto Validation**: Pydantic validates LLM responses at the type level
- **Rate Limiting**: Per-IP throttling via SlowAPI
- **Production Ready**: PostgreSQL, Docker Compose, health checks

## Setup & Run

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Start Services

```bash
docker compose up --build
```

**Services:**
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

### 3. Test the API

**Upload a document:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.pdf"
```

**Poll for results:**
```bash
curl "http://localhost:8000/api/v1/documents/1"
```

**List all documents:**
```bash
curl "http://localhost:8000/api/v1/documents/?skip=0&limit=20"
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload PDF/DOCX (returns immediately) |
| GET | `/api/v1/documents/{id}` | Get processing status & results |
| GET | `/api/v1/documents/` | List all documents (paginated) |
| GET | `/health` | Health check |

## LLM Analysis Schema

The OpenAI API is constrained to return:

```python
{
  "summary": str,                    # 2-3 sentence summary
  "document_type": DocumentType,     # invoice | contract | resume | etc.
  "topics": list[str],               # 3-8 main topics
  "key_entities": [                  # Named entities
    {"name": str, "entity_type": str, "value": str}
  ],
  "extracted_fields": dict,          # Domain-specific structured data
  "language": str,                   # Detected language
  "confidence_score": float,         # 0.0 - 1.0
  "is_sensitive": bool              # Contains PII?
}
```

## Configuration

Environment variables (`.env`):

```env
DATABASE_URL=postgresql+asyncpg://docuser:docpass@db:5432/docai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
RATE_LIMIT=10/minute
MAX_FILE_SIZE_MB=10
```

## Tech Stack

- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - Async ORM
- **PostgreSQL** - Production database
- **OpenAI API** - Structured output with Pydantic validation
- **PyMuPDF** - PDF text extraction
- **python-docx** - DOCX text extraction
- **SlowAPI** - Rate limiting
- **Docker** - Containerization

## Development

For local development without Docker:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run PostgreSQL separately or use SQLite for testing
# Modify DATABASE_URL in .env accordingly

# Run the app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Notes

- **Schema Enforcement**: `client.beta.chat.completions.parse()` with `response_format=DocumentAnalysis` guarantees OpenAI returns valid JSON matching the Pydantic schema
- **Background Processing**: FastAPI's BackgroundTasks handles async processing without blocking the upload response
- **Rate Limiting**: Applied per-IP via SlowAPI with zero middleware configuration
- **Text Truncation**: Documents are truncated to 12,000 chars to stay within token limits

## License

MIT
