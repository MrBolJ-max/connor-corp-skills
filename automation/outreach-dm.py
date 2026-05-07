#!/usr/bin/env python3
"""
outreach-dm.py — Connor Corp Outreach Automation
Generates personalized LinkedIn DMs and emails using OpenAI.
Reads prospect CSV, generates 50 personalized messages, saves to outreach_queue.json.
"""

import csv
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Try to import openai, fallback to requests if not available
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    import requests

# ─── Configuration ────────────────────────────────────────────────────────────

OUTPUT_DIR = Path.home() / ".openclaw" / "workspace" / "projects" / "connor-corp-skills" / "automation" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUTPUT_DIR / "outreach-dm.log"
QUEUE_FILE = OUTPUT_DIR / "outreach_queue.json"
PROSPECTS_CSV = OUTPUT_DIR / "prospects.csv"

# Load API key from credentials file
CREDENTIALS_FILE = Path.home() / ".openclaw" / "credentials" / "openai.env"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY and CREDENTIALS_FILE.exists():
    with open(CREDENTIALS_FILE) as f:
        for line in f:
            if line.startswith("OPENAI_API_KEY="):
                OPENAI_API_KEY = line.strip().split("=", 1)[1].strip().strip('"\'')
                break

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("outreach-dm")

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, max_calls: int, per_seconds: int):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls = []

    def wait(self):
        now = time.time()
        self.calls = [c for c in self.calls if now - c < self.per_seconds]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.per_seconds - (now - self.calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit hit. Sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        self.calls.append(time.time())

openai_limiter = RateLimiter(max_calls=20, per_seconds=60)  # OpenAI TPM limits

# ─── Message Templates ────────────────────────────────────────────────────────

DM_TEMPLATES = [
    """Hi {name}, noticed {company} is {pain_signal}. 

We help {industry} companies automate outreach and book more meetings with AI. 

Worth a quick chat?""",

    """{name} — saw {company}'s growth. Impressive.

Quick question: are you manually doing outreach right now, or using automation?

We built something that handles prospecting → messaging → follow-ups on autopilot. 

Interested in seeing how it works for {industry} companies like yours?""",

    """Hi {name},

{company} looks like it's scaling fast. Most {industry} founders I talk to at this stage say outbound is their biggest bottleneck.

We help automate the entire pipeline — find prospects, personalize messages, and book meetings.

Worth a 5-min demo?""",

    """{name}, congrats on {company}'s momentum.

I work with {industry} companies to automate their sales outreach. One client went from 0 to 15 booked calls/week in 30 days.

Would you be open to seeing how we could do something similar for {company}?""",

    """Hey {name},

Noticed {company} is hiring — usually a sign you're scaling outreach too.

Instead of hiring more SDRs, what if AI could handle your prospecting and follow-ups?

We do exactly that for {industry} companies. Worth exploring?"""
]

EMAIL_TEMPLATES = [
    """Subject: {company}'s outreach — automate or scale the team?

Hi {name},

I came across {company} while researching fast-growing {industry} companies. With {pain_signal}, I imagine outbound is a priority right now.

Most companies at your stage face a choice: hire more SDRs or automate.

We built an AI system that:
• Finds qualified prospects automatically
• Generates personalized messages at scale  
• Handles follow-ups and booking
• Runs 24/7 without headcount

One agency owner using our system booked 47 meetings in his first month — with zero additional hires.

Worth a 10-minute call to see if this fits {company}'s roadmap?

Best,
Connor

P.S. If this isn't relevant right now, just reply "not now" and I won't follow up.""",

    """Subject: AI outreach system for {industry} companies

{name},

Quick question: how many hours per week does your team spend on manual prospecting and follow-ups?

We help {industry} companies automate that entire workflow:
- Prospect finding across LinkedIn, Apollo, Twitter
- Personalized message generation (not templates — actual personalization)
- Smart follow-up sequences
- Meeting booking integration

The result: your team focuses on closing, not chasing.

Would you be open to a brief demo tailored to {company}?

Best,
Connor""",

    """Subject: {company} — scaling without more headcount

Hi {name},

{company} is clearly growing fast. But scaling outreach usually means scaling headcount — expensive and slow.

What if you could 10x your outreach without adding a single SDR?

That's what we do. Our AI system:
✓ Sources 200+ qualified prospects/week
✓ Writes personalized messages for each
✓ Manages follow-ups automatically
✓ Books meetings directly to your calendar

A SaaS founder in {industry} used this to go from 3 demos/week to 18.

Interested in seeing how it could work for {company}?

Best,
Connor

---
If now's not the time, just say "later" and I'll check back in a few months. No hard feelings."""
]

# ─── OpenAI Personalization ───────────────────────────────────────────────────

def generate_ai_message(prospect: Dict, message_type: str = "dm") -> str:
    """Generate a personalized message using OpenAI."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set. Using template fallback.")
        return None

    openai_limiter.wait()

    name = prospect.get("name", "there")
    company = prospect.get("company", "your company")
    industry = prospect.get("industry", "your industry")
    pain_signals = prospect.get("pain_signals", "")
    title = prospect.get("title", "")

    system_prompt = """You are Connor, founder of Connor Corp. You write short, punchy, personalized outreach messages.
Your style: direct, no fluff, one clear call-to-action. Never use corporate speak. Sound like a human, not a marketer.
"""

    if message_type == "dm":
        user_prompt = f"""Write a personalized LinkedIn DM for {name}, {title} at {company} ({industry}).

Context: {pain_signals}

Requirements:
- Max 100 words
- 1-2 sentences only
- Ask ONE question or make ONE offer
- No fluff, no "hope you're well"
- Sound confident but not arrogant

Write only the message, nothing else."""
    else:
        user_prompt = f"""Write a personalized cold email for {name}, {title} at {company} ({industry}).

Context: {pain_signals}

Requirements:
- Subject line + body
- Max 150 words
- One clear value proposition
- One call-to-action
- Mention something specific about their company/industry
- No generic "we help businesses grow"

Format:
Subject: [subject]

[body]"""

    try:
        if OPENAI_AVAILABLE:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        else:
            # Fallback to requests
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 300
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None

# ─── Template Fallback ─────────────────────────────────────────────────────────

def generate_template_message(prospect: Dict, message_type: str = "dm") -> str:
    """Generate a message using templates as fallback."""
    name = prospect.get("name", "there").split()[0] if prospect.get("name") else "there"
    company = prospect.get("company", "your company")
    industry = prospect.get("industry", "your industry")
    pain_signals = prospect.get("pain_signals", "scaling")
    pain_signal = pain_signals.split(", ")[0] if pain_signals else "growing fast"

    if message_type == "dm":
        template = random.choice(DM_TEMPLATES)
    else:
        template = random.choice(EMAIL_TEMPLATES)

    return template.format(
        name=name,
        company=company,
        industry=industry,
        pain_signal=pain_signal,
        pain_signals=pain_signals
    )

# ─── Message Generator ────────────────────────────────────────────────────────

def generate_messages(prospects: List[Dict], count: int = 50) -> List[Dict]:
    """Generate personalized messages for prospects."""
    messages = []
    use_openai = bool(OPENAI_API_KEY)

    logger.info(f"Generating {count} messages (OpenAI: {'enabled' if use_openai else 'disabled'})")

    for i, prospect in enumerate(prospects[:count]):
        logger.info(f"Generating message {i+1}/{count} for {prospect.get('name', 'Unknown')}")

        # Generate DM
        if use_openai:
            dm = generate_ai_message(prospect, "dm")
            if not dm:
                dm = generate_template_message(prospect, "dm")
        else:
            dm = generate_template_message(prospect, "dm")

        # Generate Email
        if use_openai:
            email = generate_ai_message(prospect, "email")
            if not email:
                email = generate_template_message(prospect, "email")
        else:
            email = generate_template_message(prospect, "email")

        message_entry = {
            "id": f"msg_{i+1:04d}",
            "prospect": prospect,
            "dm": dm,
            "email": email,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "sent_at": None,
            "opened": False,
            "replied": False,
            "follow_up_count": 0,
            "next_follow_up": None
        }

        messages.append(message_entry)
        time.sleep(0.5)  # Rate limiting

    return messages

# ─── Queue Management ─────────────────────────────────────────────────────────

def save_queue(messages: List[Dict]):
    """Save outreach queue to JSON."""
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2)
    logger.info(f"Saved {len(messages)} messages to {QUEUE_FILE}")

def load_queue() -> List[Dict]:
    """Load existing outreach queue."""
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def load_prospects() -> List[Dict]:
    """Load prospects from CSV."""
    if not PROSPECTS_CSV.exists():
        logger.error(f"Prospects CSV not found: {PROSPECTS_CSV}")
        return []

    prospects = []
    with open(PROSPECTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prospects.append(row)

    logger.info(f"Loaded {len(prospects)} prospects from {PROSPECTS_CSV}")
    return prospects

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("OUTREACH DM GENERATOR — Connor Corp")
    logger.info("=" * 60)

    # Load prospects
    prospects = load_prospects()
    if not prospects:
        logger.error("No prospects found. Run prospect-finder.py first.")
        return 0

    # Generate messages
    count = int(os.getenv("MESSAGE_COUNT", "50"))
    messages = generate_messages(prospects, count)

    # Save queue
    save_queue(messages)

    logger.info(f"Done. Generated {len(messages)} messages.")
    return len(messages)

if __name__ == "__main__":
    count = main()
    sys.exit(0 if count > 0 else 1)
