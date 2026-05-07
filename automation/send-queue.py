#!/usr/bin/env python3
"""
send-queue.py — Connor Corp Outreach Automation
Sends messages from outreach_queue.json via email (SMTP) or LinkedIn automation.
Includes rate limiting, tracking, and follow-up scheduling.
"""

import json
import logging
import os
import random
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Optional

import requests

# ─── Configuration ────────────────────────────────────────────────────────────

OUTPUT_DIR = Path.home() / ".openclaw" / "workspace" / "projects" / "connor-corp-skills" / "automation" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUTPUT_DIR / "send-queue.log"
QUEUE_FILE = OUTPUT_DIR / "outreach_queue.json"
SENT_LOG = OUTPUT_DIR / "sent_log.json"

# SMTP Configuration (from env or credentials file)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

# LinkedIn Automation (requires third-party tool or API)
LINKEDIN_API_KEY = os.getenv("LINKEDIN_API_KEY", "")
LINKEDIN_API_URL = os.getenv("LINKEDIN_API_URL", "")

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("send-queue")

# ─── Rate Limiters ────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, max_calls: int, per_seconds: int, name: str = ""):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.name = name
        self.calls = []

    def wait(self):
        now = time.time()
        self.calls = [c for c in self.calls if now - c < self.per_seconds]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.per_seconds - (now - self.calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit [{self.name}]: Sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        self.calls.append(time.time())

# Conservative limits to avoid spam flags
email_limiter = RateLimiter(max_calls=50, per_seconds=3600, name="email")  # 50/hour
linkedin_limiter = RateLimiter(max_calls=20, per_seconds=3600, name="linkedin")  # 20/hour

# ─── Queue Management ─────────────────────────────────────────────────────────

def load_queue() -> List[Dict]:
    """Load outreach queue."""
    if not QUEUE_FILE.exists():
        logger.error(f"Queue file not found: {QUEUE_FILE}")
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_queue(queue: List[Dict]):
    """Save updated queue."""
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)

def load_sent_log() -> List[Dict]:
    """Load sent message log."""
    if not SENT_LOG.exists():
        return []
    with open(SENT_LOG, "r", encoding="utf-8") as f:
        return json.load(f)

def save_sent_log(log: List[Dict]):
    """Save sent message log."""
    with open(SENT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

# ─── Email Sender ─────────────────────────────────────────────────────────────

def send_email(prospect: Dict, subject: str, body: str) -> bool:
    """Send email via SMTP."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        logger.warning("SMTP not configured. Skipping email send.")
        return False

    email_limiter.wait()

    to_email = prospect.get("email", "")
    if not to_email:
        logger.warning(f"No email for {prospect.get('name', 'Unknown')}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email

        # Plain text version
        msg.attach(MIMEText(body, "plain"))

        # HTML version (simple)
        html_body = body.replace("\n", "<br>\n")
        html = f"""<html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        {html_body}
        </body>
        </html>"""
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())

        logger.info(f"Email sent to {to_email}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return False

# ─── LinkedIn DM Sender ─────────────────────────────────────────────────────

def send_linkedin_dm(prospect: Dict, message: str) -> bool:
    """Send LinkedIn DM via API or automation tool."""
    if not LINKEDIN_API_KEY:
        logger.warning("LINKEDIN_API_KEY not set. Skipping LinkedIn send.")
        return False

    linkedin_limiter.wait()

    linkedin_url = prospect.get("linkedin_url", "")
    if not linkedin_url:
        logger.warning(f"No LinkedIn URL for {prospect.get('name', 'Unknown')}")
        return False

    # Extract LinkedIn profile ID from URL
    # This would typically use a third-party API like PhantomBuster, Expandi, or HeyReach
    try:
        if LINKEDIN_API_URL:
            # Custom API endpoint
            headers = {
                "Authorization": f"Bearer {LINKEDIN_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "linkedin_url": linkedin_url,
                "message": message,
                "prospect_name": prospect.get("name", "")
            }
            response = requests.post(
                LINKEDIN_API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            logger.info(f"LinkedIn DM queued for {prospect.get('name', 'Unknown')}")
            return True
        else:
            logger.info("LinkedIn API URL not configured. Message queued for manual send.")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"LinkedIn API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected LinkedIn error: {e}")
        return False

# ─── Follow-up Scheduler ──────────────────────────────────────────────────────

def schedule_follow_up(message: Dict) -> Optional[datetime]:
    """Schedule follow-up based on previous attempts."""
    follow_up_count = message.get("follow_up_count", 0)

    # Exponential backoff for follow-ups
    delays = [3, 7, 14, 30]  # days
    if follow_up_count < len(delays):
        delay_days = delays[follow_up_count]
        next_date = datetime.now() + timedelta(days=delay_days)
        return next_date
    return None

def generate_follow_up_message(original_message: Dict, prospect: Dict) -> str:
    """Generate a follow-up message."""
    name = prospect.get("name", "").split()[0] if prospect.get("name") else "there"
    company = prospect.get("company", "your company")

    follow_ups = [
        f"Hey {name}, just bumping this to the top of your inbox. Still interested in exploring how we could help {company} with outreach automation?",

        f"{name} — wanted to follow up on my last message. We're helping similar {prospect.get('industry', 'companies')} automate their sales pipeline and seeing great results. Worth a 5-min chat?",

        f"Hi {name}, I know you're busy. Quick follow-up: would it make sense to explore AI-powered outreach for {company}? If not, no worries — just reply 'pass' and I'll close the loop.",

        f"{name}, final follow-up here. If automating {company}'s prospecting isn't a priority right now, totally get it. If it is, happy to show you what we've built in 10 minutes. Either way, all good."
    ]

    count = original_message.get("follow_up_count", 0)
    if count < len(follow_ups):
        return follow_ups[count]
    return follow_ups[-1]

# ─── Message Processor ────────────────────────────────────────────────────────

def process_message(message: Dict) -> bool:
    """Process a single message from the queue."""
    prospect = message.get("prospect", {})
    msg_type = os.getenv("SEND_TYPE", "both")  # email, linkedin, both

    success = False

    # Send email
    if msg_type in ("email", "both"):
        email_body = message.get("email", "")
        if email_body:
            # Extract subject from email body
            lines = email_body.split("\n")
            subject = "Quick question about your outreach"
            body = email_body

            if lines[0].startswith("Subject:"):
                subject = lines[0].replace("Subject:", "").strip()
                body = "\n".join(lines[1:]).strip()

            if send_email(prospect, subject, body):
                success = True

    # Send LinkedIn DM
    if msg_type in ("linkedin", "both"):
        dm = message.get("dm", "")
        if dm:
            if send_linkedin_dm(prospect, dm):
                success = True

    # Update message status
    if success:
        message["status"] = "sent"
        message["sent_at"] = datetime.now().isoformat()
        logger.info(f"Message sent to {prospect.get('name', 'Unknown')}")
    else:
        message["status"] = "failed"
        message["error_count"] = message.get("error_count", 0) + 1
        logger.warning(f"Failed to send to {prospect.get('name', 'Unknown')}")

    return success

def process_queue(max_messages: int = 50):
    """Process pending messages from the queue."""
    queue = load_queue()
    if not queue:
        logger.info("No messages in queue")
        return 0

    sent_log = load_sent_log()
    sent_count = 0
    failed_count = 0

    # Filter pending messages
    pending = [m for m in queue if m.get("status") == "pending"]
    logger.info(f"Processing {len(pending[:max_messages])} of {len(pending)} pending messages")

    for message in pending[:max_messages]:
        try:
            if process_message(message):
                sent_count += 1
                sent_log.append({
                    "message_id": message.get("id"),
                    "prospect": message.get("prospect", {}).get("name", "Unknown"),
                    "sent_at": datetime.now().isoformat(),
                    "status": "sent"
                })
            else:
                failed_count += 1

            # Rate limiting between sends
            time.sleep(random.uniform(30, 90))

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            failed_count += 1

    # Save updated queue and log
    save_queue(queue)
    save_sent_log(sent_log)

    logger.info(f"Done. Sent: {sent_count}, Failed: {failed_count}")
    return sent_count

# ─── Follow-up Processor ──────────────────────────────────────────────────────

def process_follow_ups():
    """Process messages that need follow-ups."""
    queue = load_queue()
    sent_log = load_sent_log()
    follow_up_count = 0

    now = datetime.now()

    for message in queue:
        if message.get("status") != "sent":
            continue

        # Check if follow-up is due
        next_follow_up = message.get("next_follow_up")
        if next_follow_up:
            next_date = datetime.fromisoformat(next_follow_up)
            if now < next_date:
                continue

        # Check if we've hit max follow-ups
        if message.get("follow_up_count", 0) >= 4:
            continue

        # Generate and send follow-up
        prospect = message.get("prospect", {})
        follow_up_msg = generate_follow_up_message(message, prospect)

        # Determine channel (use same as original)
        if message.get("email"):
            success = send_email(prospect, "Following up", follow_up_msg)
        else:
            success = send_linkedin_dm(prospect, follow_up_msg)

        if success:
            message["follow_up_count"] = message.get("follow_up_count", 0) + 1
            message["next_follow_up"] = schedule_follow_up(message)
            follow_up_count += 1

            sent_log.append({
                "message_id": message.get("id"),
                "prospect": prospect.get("name", "Unknown"),
                "sent_at": now.isoformat(),
                "status": "follow_up",
                "follow_up_number": message["follow_up_count"]
            })

            time.sleep(random.uniform(60, 120))

    save_queue(queue)
    save_sent_log(sent_log)

    logger.info(f"Sent {follow_up_count} follow-ups")
    return follow_up_count

# ─── Queue Stats ────────────────────────────────────────────────────────────

def print_stats():
    """Print queue statistics."""
    queue = load_queue()
    if not queue:
        print("Queue is empty")
        return

    status_counts = {}
    for m in queue:
        status = m.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    print("\n" + "=" * 50)
    print("OUTREACH QUEUE STATS")
    print("=" * 50)
    print(f"Total messages: {len(queue)}")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print("=" * 50 + "\n")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Send outreach messages")
    parser.add_argument("--stats", action="store_true", help="Show queue stats")
    parser.add_argument("--follow-ups", action="store_true", help="Process follow-ups only")
    parser.add_argument("--max", type=int, default=50, help="Max messages to send")
    parser.add_argument("--type", choices=["email", "linkedin", "both"], default="both",
                        help="Message type to send")
    args = parser.parse_args()

    # Set env var for send type
    os.environ["SEND_TYPE"] = args.type

    if args.stats:
        print_stats()
        return 0

    logger.info("=" * 60)
    logger.info("SEND QUEUE — Connor Corp Outreach Automation")
    logger.info("=" * 60)

    if args.follow_ups:
        count = process_follow_ups()
    else:
        count = process_queue(args.max)

    logger.info("Done.")
    return count

if __name__ == "__main__":
    count = main()
    sys.exit(0 if count >= 0 else 1)
