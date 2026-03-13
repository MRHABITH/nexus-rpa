"""
╔══════════════════════════════════════════════════════════╗
║      GROQ AI AUTOMATION ENGINE — Llama 3.3 70B          ║
║  Integrates Groq API for intelligent automation prompts  ║
║  pip install groq                                        ║
╚══════════════════════════════════════════════════════════╝
"""

import re
import json
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta

# ─── Groq API Integration ──────────────────────────────────────────────────────
try:
    from groq import Groq
except ImportError:
    print("⚠️  Install groq: pip install groq")
    Groq = None

class GroqAutomationEngine:
    """AI-powered automation engine using Groq Llama 3.3 70B."""
    
    def __init__(self, api_key: str):
        """Initialize Groq client with your API key.
        
        EXAMPLE:
            engine = GroqAutomationEngine(api_key="gsk_...")
        """
        if not Groq:
            raise ImportError("groq not installed. Run: pip install groq")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
    
    def parse_automation_intent(self, user_prompt: str) -> Dict:
        """Parse natural language prompt and extract automation intent.
        
        EXAMPLE input: "Set reminder message as 'you do allocated next task' with every 10 seconds"
        EXAMPLE output: {
            "action_type": "reminder",
            "message": "you do allocated next task",
            "interval_seconds": 10,
            "duration": None
        }
        """
        system_prompt = """You are an automation intent parser. Parse the user's request and extract:
1. action_type: 'reminder', 'schedule', 'email', 'data_sync', 'monitor', 'alert'
2. message/subject: the main content
3. interval_seconds: repeat interval (if applicable)
4. trigger_condition: what triggers this (if applicable)
5. stop_condition: when to stop (if applicable)
6. recipients: who to notify (if applicable)

Return ONLY a valid JSON object, no other text.
Example: {"action_type":"reminder","message":"Take a break","interval_seconds":300,"stop_condition":"manual"}"""
        
        try:
            message = self.client.chat.completions.create(
                model=self.model,
                max_tokens=500,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            response_text = message.choices[0].message.content.strip()
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                intent = json.loads(json_match.group())
                return intent
            else:
                return {"error": "Could not parse response", "raw": response_text}
        except Exception as e:
            return {"error": str(e)}
    
    def suggest_workflow_steps(self, automation_description: str) -> List[Dict]:
        """Generate workflow steps based on automation description.
        
        Returns a list of workflow step objects for the visual builder.
        """
        system_prompt = """You are a workflow designer. Given an automation description, generate a sequence of steps.
Each step should have: id (int), type ('trigger','action','condition','end'), label (string), icon (emoji)

Return ONLY a valid JSON array of objects, no other text.
Example: [
  {"id":1,"type":"trigger","label":"Schedule Trigger","icon":"⏰"},
  {"id":2,"type":"action","label":"Send Email","icon":"📧"},
  {"id":3,"type":"end","label":"Complete","icon":"✅"}
]"""
        
        try:
            message = self.client.chat.completions.create(
                model=self.model,
                max_tokens=800,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": automation_description}
                ]
            )
            
            response_text = message.choices[0].message.content.strip()
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                steps = json.loads(json_match.group())
                return steps
            else:
                return []
        except Exception as e:
            print(f"Error generating workflow: {e}")
            return []
    
    def generate_automation_config(self, intent: Dict) -> Dict:
        """Generate complete automation configuration from parsed intent."""
        config = {
            "action_type": intent.get("action_type", "reminder"),
            "message": intent.get("message", ""),
            "interval_seconds": intent.get("interval_seconds", 600),
            "trigger_condition": intent.get("trigger_condition", "time"),
            "stop_condition": intent.get("stop_condition", "manual"),
            "recipients": intent.get("recipients", []),
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "last_executed": None,
            "execution_count": 0,
        }
        return config


# ─── Automation Task Runner ───────────────────────────────────────────────────
class AutomationTask:
    """Represents a single automation task that runs on schedule."""
    
    def __init__(self, task_id: str, config: Dict, on_execute: Callable = None):
        """Initialize automation task.
        
        Args:
            task_id: Unique identifier
            config: Configuration dictionary with action details
            on_execute: Callback when task should execute
        """
        self.id = task_id
        self.config = config
        self.on_execute = on_execute or (lambda: None)
        self.is_running = False
        self.next_execution = datetime.now()
    
    def should_execute(self) -> bool:
        """Check if task is due for execution."""
        if not self.config.get("enabled"):
            return False
        return datetime.now() >= self.next_execution
    
    def execute(self) -> Dict:
        """Execute the automation task and return result."""
        result = {
            "task_id": self.id,
            "action_type": self.config.get("action_type"),
            "executed_at": datetime.now().isoformat(),
            "status": "success",
            "message": self.config.get("message"),
        }
        
        try:
            # Call the registered callback
            self.on_execute()
            
            # Update next execution time
            interval = self.config.get("interval_seconds", 600)
            self.next_execution = datetime.now() + timedelta(seconds=interval)
            
            # Update execution count
            self.config["execution_count"] = self.config.get("execution_count", 0) + 1
            self.config["last_executed"] = datetime.now().isoformat()
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    def stop(self):
        """Stop the automation task."""
        self.is_running = False
        self.config["enabled"] = False


# ─── 5 Automation Examples ─────────────────────────────────────────────────────
AUTOMATION_EXAMPLES = [
    {
        "id": "AUTO-001",
        "name": "Periodic Reminder Task",
        "description": "Set reminder message as 'you do allocated next task' with every 10 seconds",
        "icon": "📢",
        "prompt": "Set reminder message as 'you do allocated next task' with every 10 seconds",
        "expected_config": {
            "action_type": "reminder",
            "message": "you do allocated next task",
            "interval_seconds": 10,
            "trigger_condition": "time",
            "stop_condition": "manual"
        },
        "sample_output": "Reminder sent: 'you do allocated next task' [Every 10s]"
    },
    {
        "id": "AUTO-002",
        "name": "Daily Email Report",
        "description": "Send daily email report every morning at 9 AM with performance summary",
        "icon": "📧",
        "prompt": "Send daily email report at 9 AM with performance metrics and errors to admin@company.com",
        "expected_config": {
            "action_type": "email",
            "message": "Daily Performance Report",
            "trigger_condition": "schedule:0 9 * * *",
            "recipients": ["admin@company.com"],
            "stop_condition": "manual"
        },
        "sample_output": "Email scheduled for 09:00 daily"
    },
    {
        "id": "AUTO-003",
        "name": "Database Backup Monitor",
        "description": "Check database health every 5 minutes, alert if issues found",
        "icon": "🗄️",
        "prompt": "Monitor database health every 5 minutes and alert if backup fails or disk space is low",
        "expected_config": {
            "action_type": "monitor",
            "message": "Database health check",
            "interval_seconds": 300,
            "trigger_condition": "health_check",
            "recipients": ["ops@company.com"],
            "stop_condition": "manual"
        },
        "sample_output": "Monitoring started - checks every 5 minutes"
    },
    {
        "id": "AUTO-004",
        "name": "CRM Data Sync",
        "description": "Sync customer data from CRM to data warehouse hourly",
        "icon": "🔄",
        "prompt": "Sync CRM customer records to data warehouse every hour, log changes",
        "expected_config": {
            "action_type": "data_sync",
            "message": "Sync CRM to Data Warehouse",
            "interval_seconds": 3600,
            "trigger_condition": "schedule:0 * * * *",
            "stop_condition": "manual"
        },
        "sample_output": "Data sync scheduled hourly at :00"
    },
    {
        "id": "AUTO-005",
        "name": "System Alert on Threshold",
        "description": "Alert team when API response time exceeds 2 seconds",
        "icon": "⚠️",
        "prompt": "Monitor API response time, send alert to team channel if latency exceeds 2000ms",
        "expected_config": {
            "action_type": "alert",
            "message": "API latency alert",
            "trigger_condition": "threshold:response_time>2000",
            "recipients": ["team-channel"],
            "stop_condition": "manual"
        },
        "sample_output": "Alert configured - will notify on threshold breach"
    },
    {
        "id": "AUTO-006",
        "name": "Web Scraper",
        "description": "Scrape product data from an e-commerce site with multi-step real-time logging.",
        "icon": "🌐",
        "prompt": "Scrape product names and prices from https://example-scraped.com/search?q=automation and save 150 items with real-time logs.",
        "expected_config": {
            "action_type": "web",
            "message": "E-commerce Data Scraper",
            "interval_seconds": 3600,
            "trigger_condition": "schedule:0 * * * *",
            "stop_condition": "manual"
        },
        "sample_output": "Scraper initialized - starting DOM extraction"
    },
    {
        "id": "AUTO-007",
        "name": "Amazon Product Scraper",
        "description": "Scrape product names and prices from Amazon.in search results with instant report generation.",
        "icon": "🛒",
        "prompt": "Scrape products and prices from https://www.amazon.in/s?k=amazon+products... and generate an instant report.",
        "expected_config": {
            "action_type": "web",
            "message": "Amazon Market Research",
            "interval_seconds": 86400,
            "trigger_condition": "schedule:0 0 * * *",
            "stop_condition": "manual"
        },
        "sample_output": "Amazon Scraper: Scraped 6 products and generated report."
    }
]

# ─── Example Automation Workflows ──────────────────────────────────────────────
AUTOMATION_WORKFLOWS = [
    {
        "name": "Smart Reminder Pipeline",
        "description": "Periodic reminder workflow with escalation",
        "steps": [
            {"id": 1, "type": "trigger", "label": "Time Trigger", "icon": "⏰"},
            {"id": 2, "type": "action", "label": "Send Reminder", "icon": "📢"},
            {"id": 3, "type": "condition", "label": "Count Reached?", "icon": "⚡"},
            {"id": 4, "type": "action", "label": "Send Escalation", "icon": "📣"},
            {"id": 5, "type": "end", "label": "Complete", "icon": "✅"}
        ]
    },
    {
        "name": "Email Notification Flow",
        "description": "Send daily/weekly email reports with summaries",
        "steps": [
            {"id": 1, "type": "trigger", "label": "Schedule Trigger", "icon": "⏰"},
            {"id": 2, "type": "action", "label": "Fetch Data", "icon": "📊"},
            {"id": 3, "type": "action", "label": "Generate Report", "icon": "📄"},
            {"id": 4, "type": "action", "label": "Send Email", "icon": "📧"},
            {"id": 5, "type": "end", "label": "Complete", "icon": "✅"}
        ]
    },
    {
        "name": "Health Check Monitor",
        "description": "Continuous monitoring with alerting",
        "steps": [
            {"id": 1, "type": "trigger", "label": "Interval Trigger", "icon": "⏰"},
            {"id": 2, "type": "action", "label": "Check Health", "icon": "🩺"},
            {"id": 3, "type": "condition", "label": "Healthy?", "icon": "⚡"},
            {"id": 4, "type": "action", "label": "Log Status", "icon": "📝"},
            {"id": 5, "type": "action", "label": "Alert on Failure", "icon": "⚠️"},
            {"id": 6, "type": "end", "label": "Complete", "icon": "✅"}
        ]
    },
    {
        "name": "Data Sync Workflow",
        "description": "Periodic synchronization with error handling",
        "steps": [
            {"id": 1, "type": "trigger", "label": "Schedule Trigger", "icon": "⏰"},
            {"id": 2, "type": "action", "label": "Connect Source", "icon": "🔗"},
            {"id": 3, "type": "action", "label": "Fetch Records", "icon": "📥"},
            {"id": 4, "type": "action", "label": "Transform", "icon": "⚙️"},
            {"id": 5, "type": "action", "label": "Load to Target", "icon": "📤"},
            {"id": 6, "type": "action", "label": "Verify", "icon": "✔️"},
            {"id": 7, "type": "end", "label": "Complete", "icon": "✅"}
        ]
    },
    {
        "name": "Threshold Alert System",
        "description": "Monitor metrics and alert on threshold breach",
        "steps": [
            {"id": 1, "type": "trigger", "label": "Continuous Monitor", "icon": "📡"},
            {"id": 2, "type": "action", "label": "Measure Metric", "icon": "📊"},
            {"id": 3, "type": "condition", "label": "Threshold Met?", "icon": "⚡"},
            {"id": 4, "type": "action", "label": "Send Alert", "icon": "🚨"},
            {"id": 5, "type": "action", "label": "Log Event", "icon": "📝"},
            {"id": 6, "type": "end", "label": "Complete", "icon": "✅"}
        ]
    }
]
