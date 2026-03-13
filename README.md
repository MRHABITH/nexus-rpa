# ⚡ Nexus RPA System

## Quick Start

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Then open **http://localhost:8000**

**Login:** `admin@rpa.local` / `admin123`

---

## Structure

```
simple/
├── backend/
│   ├── main.py             ← FastAPI app (all API routes)
│   ├── groq_automation.py  ← AI engine (Groq/Llama 3.3)
│   ├── requirements.txt
│   └── .env                ← GROQ_API_KEY, SUPABASE_*
└── frontend/
    └── index.html          ← Full SPA (served by backend at /)
```

## API Docs

Visit **http://localhost:8000/api/docs** for Swagger UI.
