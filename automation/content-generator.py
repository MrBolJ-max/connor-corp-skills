#!/usr/bin/env python3
"""
content-generator.py — Connor Corp Outreach Automation
Generates Twitter threads, Reddit posts, IndieHackers stories about AI sales calling.
Uses OpenAI to create viral content.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

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

LOG_FILE = OUTPUT_DIR / "content-generator.log"
CONTENT_FILE = OUTPUT_DIR / "content_queue.json"

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
logger = logging.getLogger("content-generator")

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

openai_limiter = RateLimiter(max_calls=10, per_seconds=60)

# ─── Content Prompts ────────────────────────────────────────────────────────────

CONTENT_TYPES = {
    "twitter_thread": {
        "prompt": """Write a viral Twitter/X thread about AI automating sales calls and outreach.

Topic: {topic}

Requirements:
- 8-12 tweets
- Hook in first tweet (curiosity gap or bold claim)
- Educational + entertaining
- Include one personal story or case study
- End with CTA (follow, DM, or link)
- Use numbers, lists, and "THREAD:" format
- Max 280 chars per tweet
- No hashtags (they're dead)

Write each tweet separated by ---""",
        "format": "thread"
    },

    "reddit_post": {
        "prompt": """Write a Reddit post for r/SaaS or r/entrepreneur about AI sales automation.

Topic: {topic}

Requirements:
- Authentic, not promotional
- Share a real lesson or insight
- Include specific numbers/results if possible
- Ask a genuine question at the end to drive comments
- Format: Title + Body
- No emojis, no excessive formatting
- Sound like a fellow founder, not a marketer

Title should be under 100 characters.""",
        "format": "post"
    },

    "indiehackers": {
        "prompt": """Write an IndieHackers-style "build in public" post about AI sales automation.

Topic: {topic}

Requirements:
- Personal journey format
- What I built, why I built it, what I learned
- Include revenue/usage numbers (or projections)
- Honest about struggles, not just wins
- Ask for feedback or ideas
- Community-focused, not salesy
- 300-500 words

Format: Title + Body""",
        "format": "post"
    },

    "linkedin_post": {
        "prompt": """Write a LinkedIn post about AI sales automation for business owners.

Topic: {topic}

Requirements:
- Professional but conversational
- One clear insight or lesson
- Include a story or example
- End with question to drive engagement
- 150-250 words
- Paragraph breaks for readability
- No excessive emojis (1-2 max)

Format: Body only""",
        "format": "post"
    }
}

# ─── Topic Generator ────────────────────────────────────────────────────────────

TOPICS = [
    "How I built an AI that books 47 meetings/month on autopilot",
    "The death of cold calling: Why AI voice agents are replacing SDRs",
    "I spent $0 on ads and grew to $50K MRR using AI outreach",
    "Why most AI sales tools fail (and how to fix them)",
    "The future of sales: Humans close, AI prospects",
    "How to 10x your outreach without hiring a single SDR",
    "I replaced my sales team with AI. Here's what happened.",
    "The $100K mistake: Hiring SDRs before automating outreach",
    "AI voice calls vs human SDRs: The data after 10,000 calls",
    "How to build an outbound machine that runs 24/7"
]

# ─── OpenAI Content Generator ─────────────────────────────────────────────────

def generate_content(content_type: str, topic: str) -> Dict:
    """Generate content using OpenAI."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set. Cannot generate content.")
        return None

    openai_limiter.wait()

    config = CONTENT_TYPES.get(content_type)
    if not config:
        logger.error(f"Unknown content type: {content_type}")
        return None

    prompt = config["prompt"].format(topic=topic)

    system_prompt = """You are Connor, founder of Connor Corp — an AI automation company.
You write content that gets engagement. Your style is direct, insightful, and occasionally controversial.
You share real numbers and honest lessons. No corporate speak. No fluff."""

    try:
        if OPENAI_AVAILABLE:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=2000
            )
            content = response.choices[0].message.content.strip()
        else:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 2000
            }
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()

        # Parse content based on format
        if config["format"] == "thread":
            tweets = [t.strip() for t in content.split("---") if t.strip()]
            return {
                "type": content_type,
                "topic": topic,
                "content": tweets,
                "raw": content
            }
        else:
            # Extract title if present
            lines = content.split("\n")
            title = ""
            body = content
            if lines and ("title:" in lines[0].lower() or len(lines[0]) < 100):
                title = lines[0].replace("Title:", "").replace("TITLE:", "").strip()
                body = "\n".join(lines[1:]).strip()

            return {
                "type": content_type,
                "topic": topic,
                "title": title,
                "body": body,
                "raw": content
            }

    except Exception as e:
        logger.error(f"OpenAI error generating {content_type}: {e}")
        return None

# ─── Content Queue ──────────────────────────────────────────────────────────────

def save_content_queue(contents: List[Dict]):
    """Save content queue to JSON."""
    with open(CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(contents, f, indent=2)
    logger.info(f"Saved {len(contents)} content pieces to {CONTENT_FILE}")

def load_content_queue() -> List[Dict]:
    """Load existing content queue."""
    if CONTENT_FILE.exists():
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ─── Content Scheduler ──────────────────────────────────────────────────────────

def schedule_content(contents: List[Dict]) -> List[Dict]:
    """Add scheduling metadata to content."""
    now = datetime.now()
    scheduled = []

    for i, content in enumerate(contents):
        # Schedule each piece 2 hours apart
        scheduled_time = now.replace(hour=(now.hour + i * 2) % 24)

        content["schedule"] = {
            "post_at": scheduled_time.isoformat(),
            "timezone": "America/New_York",
            "status": "scheduled"
        }
        content["id"] = f"content_{i+1:04d}"
        content["created_at"] = now.isoformat()

        scheduled.append(content)

    return scheduled

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("CONTENT GENERATOR — Connor Corp")
    logger.info("=" * 60)

    # Load existing queue
    existing = load_content_queue()
    logger.info(f"Existing queue: {len(existing)} items")

    # Generate content for each type
    content_types = list(CONTENT_TYPES.keys())
    contents = []

    # Generate 2 pieces per content type
    for content_type in content_types:
        for i in range(2):
            topic = random.choice(TOPICS)
            logger.info(f"Generating {content_type} about: {topic}")

            result = generate_content(content_type, topic)
            if result:
                contents.append(result)

            time.sleep(1)  # Rate limiting

    # Schedule content
    scheduled = schedule_content(contents)

    # Merge with existing and save
    all_content = existing + scheduled
    save_content_queue(all_content)

    logger.info(f"Done. Generated {len(contents)} new content pieces.")
    logger.info(f"Total queue size: {len(all_content)}")
    return len(contents)

if __name__ == "__main__":
    import random
    count = main()
    sys.exit(0 if count > 0 else 1)
