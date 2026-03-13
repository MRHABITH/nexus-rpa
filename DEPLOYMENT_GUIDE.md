# 🚀 Vercel Deployment Guide — Nexus RPA

This guide helps you deploy the **Nexus RPA** platform to Vercel. Because Vercel uses **Serverless Functions**, we need to adjust how data is stored and how tasks are triggered.

---

## 1. Setup persistence (Supabase)
By default, this project uses an in-memory database. **This will reset every few minutes on Vercel.**

1.  Create a free project at [Supabase.com](https://supabase.com).
2.  Go to **Project Settings → API** and get your **Project URL** and **Service Role API Key**.
3.  In your Vercel Dashboard, add these **Environment Variables**:
    - `SUPABASE_URL`: (Your Project URL)
    - `SUPABASE_KEY`: (Your Service Role Key)
    - `GROQ_API_KEY`: (Your Groq API Key)

---

## 2. Setup Vercel Cron (To replace Background Loops)
Vercel serverless functions cannot run background threads (`cron_scheduler_loop`) indefinitely.

1.  Enable **Vercel Cron Jobs** in your project.
2.  Add a `vercel.json` cron entry (or use the UI) to ping the internal trigger endpoint:
    ```json
    {
      "crons": [
        {
          "path": "/api/automation/trigger-all",
          "schedule": "*/10 * * * *"
        }
      ]
    }
    ```
    *(Note: You may need to create a dedicated `/api/automation/trigger-all` endpoint if you want real-time accuracy without the background thread.)*

---

## 3. How to Deploy

### Option A: Vercel CLI
```bash
npm install -g vercel
vercel
```

### Option B: GitHub Integration (Recommended)
1.  Push this code to a GitHub repository.
2.  Import the repository into Vercel.
3.  Vercel will automatically detect the `vercel.json` and `api/index.py` and deploy the FastAPI backend and HTML frontend together.

---

## 💡 Technical Details
- **Frontend Source**: `/frontend` (Mapped to root `/`)
- **Backend API**: `/api` (Proxied to `api/index.py`)
- **Python Runtime**: `vercel-python`
