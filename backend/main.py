"""
╔══════════════════════════════════════════════════════════╗
║      NEXUS RPA SYSTEM — Backend API                      ║
║  Run:  pip install -r requirements.txt                   ║
║        python main.py                                    ║
║  Open: http://localhost:8000                             ║
╚══════════════════════════════════════════════════════════╝
"""

import json, time, random, hashlib, hmac, base64, threading, re, os, smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Callable
import uvicorn
try:
    from croniter import croniter
except ImportError:
    croniter = None

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Supabase integration (optional)
supabase = None
DB_MODE = 'memory'
try:
    from supabase import create_client, Client as SupabaseClient
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
    if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL.startswith('http'):
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        DB_MODE = 'supabase'
except Exception:
    pass

# Import Groq automation engine
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Provide safe fallbacks so names are always defined
AUTOMATION_EXAMPLES = []
AUTOMATION_WORKFLOWS = []
AI_ENGINE = False
GroqAutomationEngine = None
try:
    from groq_automation import GroqAutomationEngine, AutomationTask, AUTOMATION_EXAMPLES, AUTOMATION_WORKFLOWS
    AI_ENGINE = True
except Exception:
    pass

# ─── Configuration ────────────────────────────────────────────────────────────
SECRET = "nexus-rpa-secret-2024"

# In-memory storage
IN_MEMORY_DB = {
    'users': [],
    'bots': [],
    'workflows': [],
    'executions': [],
    'logs': [],
    'automation_tasks': [],
    'automation_logs': [],
    'reports': [],
}

# Default admin user
IN_MEMORY_DB['users'].append({
    'id': 1,
    'email': 'admin@rpa.local',
    'username': 'admin',
    'password_hash': hashlib.sha256(b'admin123').hexdigest(),
    'role': 'admin',
    'created_at': datetime.now().isoformat()
})

# ─── In-Memory Database ────────────────────────────────────────────────────────
class InMemoryResult:
    def __init__(self):
        self.rows = []
        self.lastrowid = 0

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class InMemoryDB:
    def __init__(self):
        self.data = IN_MEMORY_DB
        self.last_rowid = 0

    def execute(self, query: str, params=None):
        q = query.upper().strip()
        if q.startswith("SELECT"):
            return self._select(q, params)
        elif q.startswith("INSERT"):
            return self._insert(q, params)
        elif q.startswith("UPDATE"):
            return self._update(q, params)
        elif q.startswith("DELETE"):
            return self._delete(q, params)
        return self

    def _select(self, q: str, params=None):
        result = InMemoryResult()

        if "COUNT(*)" in q:
            table = q.split("FROM")[1].split()[0].strip().upper()
            rows = self.data.get(table.lower(), [])
            if "WHERE" in q:
                if "STATUS='RUNNING'" in q:
                    rows = [b for b in rows if b.get('status') == 'running']
                elif "BETWEEN" in q:
                    status = "success" if "STATUS='SUCCESS'" in q else "failed"
                    rows = [e for e in rows if e.get('status') == status]
            result.rows = [[len(rows)]]
            return result

        if "MAX(ID)" in q:
            table = q.split("FROM")[1].split()[0].strip().upper()
            rows = self.data.get(table.lower(), [])
            max_id = max([r.get('id', 0) for r in rows], default=0)
            result.rows = [[max_id]]
            return result

        if "COALESCE(SUM(" in q or "SUM(" in q:
            if "FROM BOTS" in q:
                col = "success_count" if "SUCCESS_COUNT" in q else "failed_count"
                total = sum(b.get(col, 0) for b in self.data['bots'])
                result.rows = [[total]]
            return result

        if "FROM USERS" in q:
            rows = self.data['users']
            if "WHERE EMAIL" in q and params and len(params) >= 1:
                rows = [u for u in rows if u.get('email') == params[0]]
                if len(params) >= 2:
                    rows = [u for u in rows if u.get('password_hash') == params[1]]
            result.rows = rows
        elif "FROM BOTS" in q:
            rows = self.data['bots']
            if "WHERE ID=?" in q and params:
                rows = [b for b in rows if b.get('id') == params[0]]
            elif "WHERE BOT_ID=?" in q and params:
                rows = [b for b in rows if b.get('bot_id') == params[0]]
            result.rows = sorted(rows, key=lambda x: x.get('created_at', ''), reverse=True)
        elif "FROM WORKFLOWS" in q:
            rows = self.data['workflows']
            if "WHERE ID=?" in q and params:
                rows = [w for w in rows if w.get('id') == params[0]]
                if rows:
                    row = dict(rows[0])
                    if isinstance(row.get('steps'), list):
                        row['steps'] = json.dumps(row['steps'])
                    result.rows = [row]
                return result
            # Serialize steps for all workflows
            serialized = []
            for w in rows:
                rw = dict(w)
                if isinstance(rw.get('steps'), list):
                    rw['steps'] = json.dumps(rw['steps'])
                serialized.append(rw)
            result.rows = sorted(serialized, key=lambda x: x.get('created_at', ''), reverse=True)
        elif "FROM EXECUTIONS" in q:
            rows = self.data['executions']
            if "WHERE BOT_ID=?" in q and params:
                rows = [e for e in rows if e.get('bot_id') == params[0]]
            result.rows = sorted(rows, key=lambda x: x.get('created_at', ''), reverse=True)[:20]
        elif "FROM LOGS" in q:
            rows = self.data['logs']
            result.rows = sorted(rows, key=lambda x: x.get('timestamp', ''), reverse=True)
        elif "FROM REPORTS" in q:
            rows = self.data['reports']
            result.rows = sorted(rows, key=lambda x: x.get('created_at', ''), reverse=True)
        elif "FROM AUTOMATION_TASKS" in q:
            rows = self.data['automation_tasks']
            if "WHERE TASK_ID=?" in q and params:
                rows = [t for t in rows if t.get('task_id') == params[0]]
            result.rows = sorted(rows, key=lambda x: x.get('created_at', ''), reverse=True)
        elif "FROM AUTOMATION_LOGS" in q:
            rows = self.data['automation_logs']
            result.rows = sorted(rows, key=lambda x: x.get('timestamp', ''), reverse=True)

        return result

    def _insert(self, q: str, params=None):
        result = InMemoryResult()
        if not params:
            params = []

        if "INTO USERS" in q:
            new_id = max([u.get('id', 0) for u in self.data['users']], default=0) + 1
            user = {'id': new_id, 'email': params[0], 'username': params[1],
                    'password_hash': params[2], 'role': 'user', 'created_at': datetime.now().isoformat()}
            self.data['users'].append(user)
            self.last_rowid = new_id

        elif "INTO BOTS" in q:
            new_id = max([b.get('id', 0) for b in self.data['bots']], default=0) + 1
            bot = {
                'id': new_id,
                'bot_id': params[0] if params else f'BOT-{new_id:03d}',
                'name': params[1] if len(params) > 1 else '',
                'description': params[2] if len(params) > 2 else '',
                'bot_type': params[3] if len(params) > 3 else '',
                'status': 'idle',
                'success_count': 0,
                'failed_count': 0,
                'schedule': params[4] if len(params) > 4 else '',
                'config': params[5] if len(params) > 5 else {},
                'last_run': None,
                'created_at': datetime.now().isoformat()
            }
            self.data['bots'].append(bot)
            self.last_rowid = new_id

        elif "INTO WORKFLOWS" in q:
            new_id = max([w.get('id', 0) for w in self.data['workflows']], default=0) + 1
            workflow = {
                'id': new_id,
                'workflow_id': f'WF-{new_id:03d}',
                'name': params[0],
                'description': params[1] if len(params) > 1 else '',
                'steps': params[2] if len(params) > 2 else '[]',
                'status': 'draft',
                'created_at': datetime.now().isoformat()
            }
            self.data['workflows'].append(workflow)
            self.last_rowid = new_id

        elif "INTO EXECUTIONS" in q:
            new_id = max([e.get('id', 0) for e in self.data['executions']], default=0) + 1
            exe = {
                'id': new_id,
                'bot_id': params[0] if params else 0,
                'bot_str_id': params[1] if len(params) > 1 else '',
                'status': params[2] if len(params) > 2 else 'running',
                'triggered_by': params[3] if len(params) > 3 else 'manual',
                'started_at': params[4] if len(params) > 4 else datetime.now().isoformat(),
                'created_at': datetime.now().isoformat()
            }
            self.data['executions'].append(exe)
            self.last_rowid = new_id

        elif "INTO LOGS" in q:
            new_id = max([l.get('id', 0) for l in self.data['logs']], default=0) + 1
            log = {
                'id': new_id,
                'bot_id': params[0] if params else '',
                'task_name': params[1] if len(params) > 1 else '',
                'level': params[2] if len(params) > 2 else 'INFO',
                'message': params[3] if len(params) > 3 else '',
                'timestamp': datetime.now().isoformat()
            }
            self.data['logs'].append(log)
            self.last_rowid = new_id

        elif "INTO REPORTS" in q:
            new_id = max([r.get('id', 0) for r in self.data['reports']], default=0) + 1
            report = {
                'id': new_id,
                'name': params[0] if params else '',
                'report_type': params[1] if len(params) > 1 else 'daily',
                'data': params[2] if len(params) > 2 else '{}',
                'created_at': datetime.now().isoformat()
            }
            self.data['reports'].append(report)
            self.last_rowid = new_id

        elif "INTO AUTOMATION_TASKS" in q:
            new_id = max([t.get('id', 0) for t in self.data['automation_tasks']], default=0) + 1
            task = {
                'id': new_id,
                'task_id': params[0] if params else f'AUTO-{new_id:03d}',
                'name': params[1] if len(params) > 1 else '',
                'description': params[2] if len(params) > 2 else '',
                'prompt': params[3] if len(params) > 3 else '',
                'action_type': params[4] if len(params) > 4 else '',
                'message': params[5] if len(params) > 5 else '',
                'interval_seconds': params[6] if len(params) > 6 else 600,
                'status': params[7] if len(params) > 7 else 'active',
                'created_by': params[8] if len(params) > 8 else '',
                'enabled': params[9] if len(params) > 9 else 1,
                'execution_count': 0,
                'last_executed': None,
                'created_at': datetime.now().isoformat()
            }
            self.data['automation_tasks'].append(task)
            self.last_rowid = new_id

        elif "INTO AUTOMATION_LOGS" in q:
            new_id = max([l.get('id', 0) for l in self.data['automation_logs']], default=0) + 1
            log = {
                'id': new_id,
                'task_id': params[0] if params else '',
                'status': params[1] if len(params) > 1 else '',
                'message': params[2] if len(params) > 2 else '',
                'result': params[3] if len(params) > 3 else '',
                'execution_time_ms': params[4] if len(params) > 4 else 0,
                'timestamp': datetime.now().isoformat()
            }
            self.data['automation_logs'].append(log)
            self.last_rowid = new_id

        result.lastrowid = self.last_rowid
        return result

    def _update(self, q: str, params=None):
        result = InMemoryResult()
        if not params:
            return result

        if "UPDATE BOTS SET STATUS=" in q:
            status_val = None
            if "'IDLE'" in q:
                status_val = 'idle'
            elif "'RUNNING'" in q:
                status_val = 'running'
            if status_val and params:
                bot_id = params[-1]
                for b in self.data['bots']:
                    if b.get('id') == bot_id:
                        b['status'] = status_val
                        break

        elif "UPDATE BOTS SET" in q and "WHERE ID=?" in q:
            # Generic update
            pass

        elif "UPDATE EXECUTIONS SET" in q:
            if params and len(params) >= 2:
                exe_id = params[-1]
                for e in self.data['executions']:
                    if e.get('id') == exe_id:
                        e['status'] = params[0]
                        if len(params) > 2:
                            e['completed_at'] = params[1]
                        break

        elif "UPDATE AUTOMATION_TASKS SET" in q:
            if "ENABLED=?" in q and params:
                enabled_val = params[0]
                task_id = params[-1]
                for t in self.data['automation_tasks']:
                    if t.get('task_id') == task_id:
                        t['enabled'] = enabled_val
                        break
            elif "EXECUTION_COUNT=" in q and params:
                task_id = params[-1]
                for t in self.data['automation_tasks']:
                    if t.get('task_id') == task_id:
                        t['execution_count'] = t.get('execution_count', 0) + 1
                        t['last_executed'] = params[0] if len(params) > 1 else datetime.now().isoformat()
                        break

        elif "UPDATE WORKFLOWS SET" in q and params:
            wf_id = params[-1]
            for w in self.data['workflows']:
                if w.get('id') == wf_id:
                    w['name'] = params[0]
                    w['description'] = params[1]
                    w['steps'] = params[2]
                    break

        return result

    def _delete(self, q: str, params=None):
        result = InMemoryResult()
        if not params:
            return result

        if "FROM BOTS WHERE ID=?" in q:
            self.data['bots'] = [b for b in self.data['bots'] if b.get('id') != params[0]]
        elif "FROM WORKFLOWS WHERE ID=?" in q:
            self.data['workflows'] = [w for w in self.data['workflows'] if w.get('id') != params[0]]
        elif "FROM AUTOMATION_TASKS WHERE TASK_ID=?" in q:
            self.data['automation_tasks'] = [t for t in self.data['automation_tasks'] if t.get('task_id') != params[0]]
        elif "FROM AUTOMATION_LOGS WHERE TASK_ID=?" in q:
            self.data['automation_logs'] = [l for l in self.data['automation_logs'] if l.get('task_id') != params[0]]

        return result

    def commit(self): pass
    def close(self): pass


def get_db() -> InMemoryDB:
    return InMemoryDB()

# ─── Auth ─────────────────────────────────────────────────────────────────────
def make_token(user_id: int, email: str) -> str:
    payload = json.dumps({"id": user_id, "email": email,
                          "exp": (datetime.now() + timedelta(hours=24)).isoformat()})
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()  # type: ignore[attr-defined]
    return base64.b64encode(f"{payload}|{sig}".encode()).decode()

def verify_token(token: str) -> dict:
    try:
        decoded = base64.b64decode(token.encode()).decode()
        payload_str, sig = decoded.rsplit("|", 1)
        expected = hmac.new(SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()  # type: ignore[attr-defined]
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(401, "Invalid token")
        return json.loads(payload_str)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

def current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    return verify_token(auth[7:])

# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(title="Nexus RPA API", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def frontend():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found. Run from project root.</h1>", status_code=404)

# ─── Models ───────────────────────────────────────────────────────────────────
class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    email: str
    username: str
    password: str

class BotCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    bot_type: str
    schedule: Optional[str] = ""
    config: Optional[dict] = {}

class BotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    bot_type: Optional[str] = None
    schedule: Optional[str] = None
    config: Optional[dict] = None

class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    steps: Optional[list] = []

class AutomationPrompt(BaseModel):
    prompt: str
    name: Optional[str] = None

class AutomationTaskCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    prompt: str
    action_type: str
    message: Optional[str] = ""
    interval_seconds: Optional[int] = 600
    stop_condition: Optional[str] = "manual"
    recipients: Optional[List[str]] = []

# ─── Auth Endpoints ───────────────────────────────────────────────────────────
@app.post("/api/auth/login")
def login(req: LoginReq):
    db = get_db()
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    user = db.execute("SELECT * FROM users WHERE email=? AND password_hash=?",
                      (req.email, pw_hash)).fetchone()
    db.close()
    if not user:
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": make_token(user["id"], user["email"]),
            "token_type": "bearer",
            "user": {k: v for k, v in user.items() if k != "password_hash"}}

@app.post("/api/auth/register")
def register(req: RegisterReq):
    db = get_db()
    existing = db.execute("SELECT * FROM users WHERE email=?", (req.email,)).fetchone()
    if existing:
        raise HTTPException(400, "Email already registered")
    pw_hash = hashlib.sha256(req.password.encode()).hexdigest()
    cur = db.execute("INSERT INTO users(email,username,password_hash) VALUES(?,?,?)",
                     (req.email, req.username, pw_hash))
    db.commit()
    uid = cur.lastrowid
    db.close()
    return {"access_token": make_token(uid, req.email), "token_type": "bearer"}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user

# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def stats(user=Depends(current_user)):
    db = get_db()
    total_bots    = db.execute("SELECT COUNT(*) FROM bots").fetchone()[0]
    active_bots   = db.execute("SELECT COUNT(*) FROM bots WHERE status='running'").fetchone()[0]
    total_success = db.execute("SELECT SUM(success_count) FROM bots").fetchone()[0] or 0
    total_failed  = db.execute("SELECT SUM(failed_count) FROM bots").fetchone()[0] or 0
    total_exec    = db.execute("SELECT COUNT(*) FROM executions").fetchone()[0]

    timeseries = []
    for i in range(12, 0, -1):
        t_start = (datetime.now() - timedelta(hours=i)).strftime("%Y-%m-%d %H:00:00")
        t_end   = (datetime.now() - timedelta(hours=i - 1)).strftime("%Y-%m-%d %H:00:00")
        s = db.execute("SELECT COUNT(*) FROM executions WHERE status='success' AND created_at BETWEEN ? AND ?",
                       (t_start, t_end)).fetchone()[0]
        f = db.execute("SELECT COUNT(*) FROM executions WHERE status='failed' AND created_at BETWEEN ? AND ?",
                       (t_start, t_end)).fetchone()[0]
        timeseries.append({
            "h": (datetime.now() - timedelta(hours=i)).strftime("%H:00"),
            "success": s, "failed": f
        })
    db.close()

    # AI Automation stats
    ai_tasks = IN_MEMORY_DB['automation_tasks']
    active_tasks = [t for t in ai_tasks if t.get('enabled')]
    total_task_runs = sum(t.get('execution_count', 0) for t in ai_tasks)
    recent_tasks = sorted(ai_tasks, key=lambda x: x.get('last_executed') or '', reverse=True)[:5]

    # Recent logs (last 8 entries)
    recent_logs = sorted(IN_MEMORY_DB['logs'], key=lambda x: x.get('timestamp', ''), reverse=True)[:8]

    total = total_success + total_failed
    return {
        "total_bots": total_bots,
        "active_bots": active_bots,
        "total_success": total_success,
        "total_failed": total_failed,
        "total_executions": total_exec,
        "success_rate": round(total_success / total * 100, 1) if total > 0 else 0,
        "timeseries": timeseries,
        # AI task stats
        "total_ai_tasks": len(ai_tasks),
        "active_ai_tasks": len(active_tasks),
        "total_task_runs": total_task_runs,
        "recent_tasks": recent_tasks,
        "recent_logs": recent_logs,
    }

# ─── Bots ─────────────────────────────────────────────────────────────────────
def run_bot_async(bot_id: int, bot_str_id: str, bot_type: str, execution_id: int):
    """Simulate bot execution or run actual email agent in background thread."""
    bot = None
    for b in IN_MEMORY_DB['bots']:
        if b.get('id') == bot_id:
            b['status'] = 'running'
            b['last_run'] = datetime.now().isoformat()
            bot = b
            break

    bot_type_clean = str(bot_type).lower().strip()
    
    while True:
        # Check if bot is still supposed to be running (allows manual Stop)
        current_b = next((b for b in IN_MEMORY_DB['bots'] if b.get('id') == bot_id), None)
        if not current_b or current_b.get('status') != 'running':
            break

        start_time = time.time()
        success = False
        status_msg = ""
        config = current_b.get('config', {})
        
        if bot_type_clean in ('email', 'email parsing'):
            # --- Live Email Execution ---
            to_email = config.get('to', '')
            subject = config.get('subject', current_b.get('name', 'Automation Notification'))
            body = config.get('body', current_b.get('description', 'Sent by Nexus RPA Email Bot'))
            
            # Pull SMTP creds from individual bot config (User's own credentials)
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
            smtp_user = config.get('fromEmail', '')
            smtp_pass = config.get('fromPw', '')
            
            if not to_email:
                success = False
                status_msg = "Failed: Missing 'To' email address in config"
            elif not smtp_user or not smtp_pass:
                success = False
                status_msg = "Failed: Sender Email or App Password not provided in bot config"
                time.sleep(1) # simulate failure delay
            else:
                try:
                    msg = EmailMessage()
                    msg.set_content(body)
                    msg['Subject'] = subject
                    msg['From'] = smtp_user
                    msg['To'] = to_email

                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
                    server.quit()
                    success = True
                    status_msg = f"Email sent successfully from {smtp_user} to {to_email}"
                except Exception as e:
                    success = False
                    status_msg = f"Email Failed: {str(e)}"
        elif bot_type_clean == 'web':
            # Multi-step realistic log sequence
            log_id = max([l.get('id', 0) for l in IN_MEMORY_DB['logs']], default=0) + 1
            IN_MEMORY_DB['logs'].append({'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'INFO', 'message': "Initializing Headless Chrome (version 120.0.6099.109)...", 'timestamp': datetime.now().isoformat()})
            time.sleep(1.2)
            
            log_id += 1
            IN_MEMORY_DB['logs'].append({'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'INFO', 'message': "Navigating to: https://example-scraped.com/products?category=automation", 'timestamp': datetime.now().isoformat()})
            time.sleep(1.5)
            
            log_id += 1
            IN_MEMORY_DB['logs'].append({'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'INFO', 'message': "Waiting for selector: '.product-grid' (timeout 30s)...", 'timestamp': datetime.now().isoformat()})
            time.sleep(1.0)

            success = random.random() > 0.05
            if success:
                log_id += 1
                IN_MEMORY_DB['logs'].append({'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'INFO', 'message': "Successfully extracted 142 DOM elements. Mapping data...", 'timestamp': datetime.now().isoformat()})
                status_msg = "Web Scraping Completed Successfully (142 items saved)"
            else:
                log_id += 1
                IN_MEMORY_DB['logs'].append({
                    'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'ERROR', 
                    'message': "ElementClickInterceptedException: Message: element click intercepted: Element is not clickable at point (521, 623). Other element would receive the click: <div class='footer-overlay'></div>", 
                    'timestamp': datetime.now().isoformat()
                })
                status_msg = "TimeoutException during element interaction"
        elif bot_type_clean == 'api':
            time.sleep(0.8)
            log_id = max([l.get('id', 0) for l in IN_MEMORY_DB['logs']], default=0) + 1
            IN_MEMORY_DB['logs'].append({'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'INFO', 'message': f"GET /api/v1/sync returned 200 OK (45 records)", 'timestamp': datetime.now().isoformat()})
            time.sleep(0.5)
            success = random.random() > 0.05
            status_msg = "API Sync Completed (45 records updated)" if success else "HTTP 502 Bad Gateway during Sync"
        elif bot_type_clean == 'data':
            time.sleep(2.0)
            log_id = max([l.get('id', 0) for l in IN_MEMORY_DB['logs']], default=0) + 1
            IN_MEMORY_DB['logs'].append({'id': log_id, 'bot_id': bot_str_id, 'task_name': bot_type, 'level': 'INFO', 'message': f"Transformed 14,502 rows and validated schema constraints.", 'timestamp': datetime.now().isoformat()})
            time.sleep(1.0)
            success = random.random() > 0.05
            status_msg = "Data Pipeline Finished (0 validation errors)" if success else "Schema Validation Error on row 842"
        elif bot_type_clean == 'file':
            time.sleep(0.5)
            success = True
            found = random.random() > 0.5
            if found:
                status_msg = "Detected 2 new files in watch directory. Triggering downstream."
            else:
                status_msg = "Directory scan complete. No new files found."
        else:
            # Fallback
            duration = random.uniform(1.5, 4.0)
            time.sleep(duration)
            success = random.random() > 0.1
            status_msg = "Simulated Execution Completed" if success else "Simulated Execution Failed"
            
        duration = time.time() - start_time
        status = 'success' if success else 'failed'
        
        # Update bot stats
        for b in IN_MEMORY_DB['bots']:
            if b.get('id') == bot_id:
                if success:
                    b['success_count'] = b.get('success_count', 0) + 1
                else:
                    b['failed_count'] = b.get('failed_count', 0) + 1
                break

        # Update execution record
        for e in IN_MEMORY_DB['executions']:
            if e.get('id') == execution_id:
                e['status'] = status
                e['completed_at'] = datetime.now().isoformat()
                e['duration_ms'] = int(duration * 1000)
                break

        # Add log entry
        level = 'INFO' if success else 'ERROR'
        str_msg = f"{status_msg} in {duration:.1f}s"
        log_id = max([l.get('id', 0) for l in IN_MEMORY_DB['logs']], default=0) + 1
        IN_MEMORY_DB['logs'].append({
            'id': log_id,
            'bot_id': bot_str_id,
            'task_name': bot_type,
            'level': level,
            'message': str_msg,
            'timestamp': datetime.now().isoformat()
        })
        
        # Determine if we should loop continuously
        schedule = current_b.get('schedule', '')
        if schedule.startswith('loop:'):
            try:
                interval_secs = int(schedule.split(':')[1])
            except Exception:
                interval_secs = 60
                
            sleep_time = 0
            # Sleep in intervals so manual stop breaks the wait instantly
            while sleep_time < interval_secs:
                time.sleep(1)
                sleep_time += 1
                check_b = next((b for b in IN_MEMORY_DB['bots'] if b.get('id') == bot_id), None)
                if not check_b or check_b.get('status') != 'running':
                    break
        else:
            # Not a loop, mark idle and exit thread cleanly
            for b in IN_MEMORY_DB['bots']:
                if b.get('id') == bot_id:
                    b['status'] = 'idle'
                    break
            break

@app.get("/api/bots")
def list_bots(user=Depends(current_user)):
    db = get_db()
    bots = [dict(b) for b in db.execute("SELECT * FROM bots ORDER BY created_at DESC").fetchall()]
    db.close()
    return bots

@app.post("/api/bots", status_code=201)
def create_bot(req: BotCreate, user=Depends(current_user)):
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM bots").fetchone()[0]
    bot_id = f"BOT-{count + 1:03d}"
    db.execute("INSERT INTO bots(bot_id,name,description,bot_type,schedule,config) VALUES(?,?,?,?,?,?)",
               (bot_id, req.name, req.description, req.bot_type, req.schedule, req.config or {}))
    db.commit()
    bot = next((b for b in IN_MEMORY_DB['bots'] if b.get('bot_id') == bot_id), None)
    db.close()
    return bot or {}

@app.put("/api/bots/{bot_id}")
def update_bot(bot_id: int, req: BotUpdate, user=Depends(current_user)):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    for b in IN_MEMORY_DB['bots']:
        if b.get('id') == bot_id:
            b.update(fields)
            return b
    raise HTTPException(404, "Bot not found")

@app.delete("/api/bots/{bot_id}", status_code=204)
def delete_bot(bot_id: int, user=Depends(current_user)):
    bot = next((b for b in IN_MEMORY_DB['bots'] if b.get('id') == bot_id), None)
    if not bot:
        raise HTTPException(404, "Bot not found")
    if bot.get("status") == "running":
        raise HTTPException(400, "Stop the bot before deleting")
    IN_MEMORY_DB['bots'] = [b for b in IN_MEMORY_DB['bots'] if b.get('id') != bot_id]

@app.post("/api/bots/{bot_id}/run")
def run_bot(bot_id: int, user=Depends(current_user)):
    bot = next((b for b in IN_MEMORY_DB['bots'] if b.get('id') == bot_id), None)
    if not bot:
        raise HTTPException(404, "Bot not found")
    if bot.get("status") == "running":
        raise HTTPException(409, "Bot is already running")

    db = get_db()
    triggered_by = "manual" if user else "cron"
    cur = db.execute("INSERT INTO executions(bot_id,bot_str_id,status,triggered_by,started_at) VALUES(?,?,?,?,?)",
                     (bot_id, bot["bot_id"], "running", triggered_by, datetime.now().isoformat()))
    execution_id = cur.lastrowid
    db.commit()
    db.close()

    t = threading.Thread(
        target=run_bot_async,
        args=(bot_id, bot["bot_id"], bot.get("bot_type", ""), execution_id),
        daemon=True
    )
    t.start()
    return {"execution_id": execution_id, "status": "started", "bot": bot["bot_id"]}

@app.post("/api/bots/{bot_id}/stop")
def stop_bot(bot_id: int, user=Depends(current_user)):
    for b in IN_MEMORY_DB['bots']:
        if b.get('id') == bot_id:
            b['status'] = 'idle'
            break
    return {"detail": "Bot stopped"}

@app.get("/api/bots/{bot_id}/executions")
def bot_executions(bot_id: int, user=Depends(current_user)):
    execs = [e for e in IN_MEMORY_DB['executions'] if e.get('bot_id') == bot_id]
    return sorted(execs, key=lambda x: x.get('created_at', ''), reverse=True)[:20]

# ─── Workflows ────────────────────────────────────────────────────────────────
@app.get("/api/workflows")
def list_workflows(user=Depends(current_user)):
    result = []
    for w in sorted(IN_MEMORY_DB['workflows'], key=lambda x: x.get('created_at', ''), reverse=True):
        d = dict(w)
        if isinstance(d.get('steps'), str):
            try:
                d['steps'] = json.loads(d['steps'])
            except Exception:
                d['steps'] = []
        result.append(d)
    return result

@app.post("/api/workflows", status_code=201)
def create_workflow(req: WorkflowCreate, user=Depends(current_user)):
    db = get_db()
    db.execute("INSERT INTO workflows(name,description,steps) VALUES(?,?,?)",
               (req.name, req.description, json.dumps(req.steps)))
    db.commit()
    db.close()
    wf = IN_MEMORY_DB['workflows'][-1]
    d = dict(wf)
    if isinstance(d.get('steps'), str):
        d['steps'] = json.loads(d['steps'])
    return d

@app.put("/api/workflows/{wf_id}")
def update_workflow(wf_id: int, req: WorkflowCreate, user=Depends(current_user)):
    for w in IN_MEMORY_DB['workflows']:
        if w.get('id') == wf_id:
            w['name'] = req.name
            w['description'] = req.description
            w['steps'] = req.steps
            d = dict(w)
            return d
    raise HTTPException(404, "Workflow not found")

@app.delete("/api/workflows/{wf_id}", status_code=204)
def delete_workflow(wf_id: int, user=Depends(current_user)):
    IN_MEMORY_DB['workflows'] = [w for w in IN_MEMORY_DB['workflows'] if w.get('id') != wf_id]

# ─── Logs ─────────────────────────────────────────────────────────────────────
@app.get("/api/logs")
def get_logs(level: Optional[str] = None, bot_id: Optional[str] = None,
             limit: int = 100, user=Depends(current_user)):
    rows = list(IN_MEMORY_DB['logs'])
    if level and level != "all":
        rows = [l for l in rows if l.get('level', '').upper() == level.upper()]
    if bot_id and bot_id != "all":
        rows = [l for l in rows if l.get('bot_id') == bot_id]
    rows = sorted(rows, key=lambda x: x.get('timestamp', ''), reverse=True)
    return rows[:limit]

# ─── Reports ──────────────────────────────────────────────────────────────────
@app.get("/api/reports/analytics")
def analytics(user=Depends(current_user)):
    bots = [dict(b) for b in IN_MEMORY_DB['bots']]
    weekly = []
    for i in range(6, -1, -1):
        d = datetime.now() - timedelta(days=i)
        day_str = d.strftime("%Y-%m-%d")
        s = len([e for e in IN_MEMORY_DB['executions']
                 if e.get('status') == 'success' and e.get('created_at', '').startswith(day_str)])
        f = len([e for e in IN_MEMORY_DB['executions']
                 if e.get('status') == 'failed' and e.get('created_at', '').startswith(day_str)])
        weekly.append({"d": d.strftime("%a"), "success": s, "failed": f})

    return {
        "bots": bots,
        "weekly": weekly,
        "total_saved": f"${random.randint(8000, 15000):,}",
        "avg_time": f"{random.uniform(0.8, 2.5):.1f}s",
    }

@app.post("/api/reports/generate")
def generate_report(user=Depends(current_user)):
    db = get_db()
    name = f"Automation Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    data = {"generated": True, "timestamp": datetime.now().isoformat()}
    db.execute("INSERT INTO reports(name,report_type,data) VALUES(?,?,?)",
               (name, "daily", json.dumps(data)))
    db.commit()
    db.close()
    return IN_MEMORY_DB['reports'][-1] if IN_MEMORY_DB['reports'] else {}

@app.get("/api/reports")
def list_reports(user=Depends(current_user)):
    return sorted(IN_MEMORY_DB['reports'], key=lambda x: x.get('created_at', ''), reverse=True)

# ─── Health ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat(), "db_mode": DB_MODE, "ai_engine": AI_ENGINE}

# ─── AI Automation ────────────────────────────────────────────────────────────
@app.get("/api/automation/examples")
def get_automation_examples(user=Depends(current_user)):
    return AUTOMATION_EXAMPLES if AI_ENGINE else []

@app.get("/api/automation/workflows")
def get_automation_workflows(user=Depends(current_user)):
    return AUTOMATION_WORKFLOWS if AI_ENGINE else []

@app.post("/api/automation/parse-prompt")
def parse_automation_prompt(req: AutomationPrompt, user=Depends(current_user)):
    if not GROQ_AVAILABLE or not AI_ENGINE:
        return {
            "error": "Groq API not available",
            "hint": "Install: pip install groq and set GROQ_API_KEY",
            "fallback": {"action_type": "reminder", "message": req.prompt, "interval_seconds": 600}
        }
    try:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            return {"error": "GROQ_API_KEY not set in .env"}
        engine = GroqAutomationEngine(api_key=api_key)
        intent = engine.parse_automation_intent(req.prompt)
        return {"success": True, "intent": intent, "prompt": req.prompt}
    except Exception as e:
        return {"error": str(e), "prompt": req.prompt}

@app.post("/api/automation/generate-workflow")
def generate_workflow_from_prompt(req: AutomationPrompt, user=Depends(current_user)):
    if not GROQ_AVAILABLE or not AI_ENGINE:
        return {"error": "Groq API not available", "workflows": AUTOMATION_WORKFLOWS if AI_ENGINE else []}
    try:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            return {"error": "GROQ_API_KEY not set"}
        engine = GroqAutomationEngine(api_key=api_key)
        steps = engine.suggest_workflow_steps(req.prompt)
        return {"success": True, "steps": steps, "description": req.prompt}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/automation/create-task")
def create_automation_task(req: AutomationTaskCreate, user=Depends(current_user)):
    db = get_db()
    # Use MAX(id) + 1 for task_id to avoid collisions after deletions
    max_id = db.execute("SELECT MAX(id) FROM automation_tasks").fetchone()[0] or 0
    task_id = f"AUTO-{max_id + 1:03d}"
    
    db.execute("""INSERT INTO automation_tasks(task_id, name, description, prompt,
                 action_type, message, interval_seconds, status, created_by, enabled)
                 VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
               (task_id, req.name, req.description, req.prompt,
                req.action_type, req.message, req.interval_seconds, "active", user["email"]))
    db.commit()
    # Fetch from DB wrapper to ensure sync
    task = db.execute("SELECT * FROM automation_tasks WHERE task_id=?", (task_id,)).fetchone()
    db.close()
    return {"success": True, "task": task}

@app.get("/api/automation/tasks")
def list_automation_tasks(user=Depends(current_user)):
    return sorted(IN_MEMORY_DB['automation_tasks'], key=lambda x: x.get('created_at', ''), reverse=True)

@app.get("/api/automation/tasks/{task_id}")
def get_automation_task(task_id: str, user=Depends(current_user)):
    task = next((t for t in IN_MEMORY_DB['automation_tasks'] if t.get('task_id') == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    return task

@app.post("/api/automation/tasks/{task_id}/execute")
def execute_automation_task(task_id: str, user=Depends(current_user)):
    task = next((t for t in IN_MEMORY_DB['automation_tasks'] if t.get('task_id') == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")

    start = time.time()
    # Update task stats
    task['execution_count'] = task.get('execution_count', 0) + 1
    task['last_executed'] = datetime.now().isoformat()

    # Simulated data generation for web scraping (Amazon example)
    scraped_data = None
    if task['action_type'] == 'web' or 'amazon' in str(task.get('prompt', '')).lower():
        # Generate some mock amazon products
        products = [
            {"name": "Apple iPhone 15 (128 GB) - Black", "price": "₹65,900"},
            {"name": "Samsung Galaxy S24 Ultra 5G", "price": "₹1,29,999"},
            {"name": "Sony WH-1000XM5 Noise Cancelling Headphones", "price": "₹26,990"},
            {"name": "MacBook Air M2 Chip, 13-inch", "price": "₹92,900"},
            {"name": "Kindle Paperwhite (16 GB) - Black", "price": "₹13,999"},
            {"name": "OnePlus Nord CE 3 Lite 5G", "price": "₹17,499"}
        ]
        # Mix/Slice for variety
        random.shuffle(products)
        scraped_data = products[:random.randint(4, 6)]
        result_msg = f"Web Scraper: Scraped {len(scraped_data)} products from Amazon.in"

    exec_time_ms = int((time.time() - start) * 1000)

    # Write to automation_logs
    log_entry = {
        'id': len(IN_MEMORY_DB['automation_logs']) + 1,
        'task_id': task_id,
        'status': 'executed',
        'message': result_msg,
        'result': 'success',
        'data': json.dumps(scraped_data) if scraped_data else None,
        'execution_time_ms': exec_time_ms,
        'timestamp': datetime.now().isoformat()
    }
    IN_MEMORY_DB['automation_logs'].append(log_entry)

    # Also write to main logs so the Logs page reflects the execution
    log_id = max([l.get('id', 0) for l in IN_MEMORY_DB['logs']], default=0) + 1
    IN_MEMORY_DB['logs'].append({
        'id': log_id,
        'bot_id': task_id,
        'task_name': task.get('name', task_id),
        'level': 'INFO',
        'message': f"Executed: {result_msg} (run #{task['execution_count']})",
        'timestamp': datetime.now().isoformat()
    })

    return {
        "success": True,
        "task_id": task_id,
        "action": task["action_type"],
        "message": result_msg,
        "data": scraped_data,
        "executed_at": datetime.now().isoformat(),
        "execution_time_ms": exec_time_ms,
        "task": task
    }

@app.post("/api/automation/tasks/{task_id}/toggle")
def toggle_automation_task(task_id: str, user=Depends(current_user)):
    task = next((t for t in IN_MEMORY_DB['automation_tasks'] if t.get('task_id') == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    task['enabled'] = 0 if task.get('enabled') else 1
    return {"success": True, "enabled": bool(task['enabled']), "task": task}

@app.get("/api/automation/logs")
def get_automation_logs(limit: int = 100, user=Depends(current_user)):
    logs = sorted(IN_MEMORY_DB['automation_logs'], key=lambda x: x.get('timestamp', ''), reverse=True)
    return logs[:limit]

@app.delete("/api/automation/tasks/{task_id}", status_code=204)
def delete_automation_task(task_id: str, user=Depends(current_user)):
    db = get_db()
    task = db.execute("SELECT * FROM automation_tasks WHERE task_id=?", (task_id,)).fetchone()
    if not task:
        db.close()
        raise HTTPException(404, "Task not found")
    
    db.execute("DELETE FROM automation_tasks WHERE task_id=?", (task_id,))
    db.execute("DELETE FROM automation_logs WHERE task_id=?", (task_id,))
    db.commit()
    db.close()
    return None

# ─── Startup ──────────────────────────────────────────────────────────────────
def cron_scheduler_loop():
    """Background thread to trigger bots on their cron schedules."""
    if not croniter:
        print("Warning: croniter not installed, scheduled bots will not run.")
        return
        
    while True:
        now = datetime.now()
        for bot in list(IN_MEMORY_DB['bots']):
            schedule = bot.get('schedule', '').strip()
            if not schedule or bot.get('status') == 'running':
                continue
                
            try:
                # croniter check to see if due within this exact minute
                # croniter match allows matching datetime down to minute resolution
                if croniter.match(schedule, now):
                    try:
                        # trigger the bot run logic with None as user (system run)
                        run_bot(bot['id'], user=None)
                    except Exception as rb_exc:
                        print(f"Error triggering scheduled bot {bot['bot_id']}: {rb_exc}")
            except Exception as e:
                # Invalid cron syntax
                pass
                
        # Wait until the start of the next minute
        sleep_secs = 60 - datetime.now().second
        time.sleep(max(1, sleep_secs))

if __name__ == "__main__":
    t_cron = threading.Thread(target=cron_scheduler_loop, daemon=True)
    t_cron.start()
    
    print("\n" + "=" * 55)
    print("  ⚡  NEXUS RPA SYSTEM — Backend")
    print("=" * 55)
    print(f"  Frontend: {FRONTEND_DIR}")
    print("  API:      http://localhost:8000/api/docs")
    print("  App:      http://localhost:8000")
    print("  Login:    admin@rpa.local / admin123")
    print("=" * 55 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
