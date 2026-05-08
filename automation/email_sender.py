#!/usr/bin/env python3
"""
Connor Corp Email Outreach Sender
Sends personalized cold emails to prospects using company emails
"""

import csv
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import random

# Email templates
TEMPLATES = {
    "ai_sales_caller": """
Subject: AI Sales Caller for {company} — 48hr deploy, no monthly fees

Hey {first_name},

I came across {company} and see you're {title}.

I built an AI sales caller that handles full sales conversations — qualification, objection handling, and appointment booking — 24/7.

What makes it different:
• $497 one-time (not $300/mo + usage fees like competitors)
• 48-hour done-for-you deployment
• Industry-specific script trained on your business
• Warm transfers qualified leads to your phone
• 30-day money-back guarantee

It's basically an SDR that works nights and weekends for a one-time fee.

Worth a 15-minute call to see if it fits {company}?

— Connor
Connor Corp | AI Automation for Modern Businesses

P.S. If it doesn't deliver within 30 days, full refund. No questions.
""",
    
    "leadgen_swarm": """
Subject: Scale {company}'s outreach without hiring SDRs

Hey {first_name},

I built an AI lead generation system that auto-scrapes LinkedIn + Apollo, enriches every profile with 50+ data points, and writes personalized outreach messages.

For {company} specifically, this could:
• Find qualified prospects at scale
• Auto-personalize every touchpoint
• Cut prospecting time from 6hrs/day to 30 min/day
• Cost $297 one-time (vs $3-5K/mo for an SDR)

30-day money-back guarantee. If it doesn't work, full refund.

Worth 15 minutes to see the demo?

— Connor
"""
}

def send_email(smtp_server, smtp_port, username, password, from_email, to_email, subject, body):
    """Send a single email via SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)

def load_prospects(csv_file):
    """Load prospects from CSV"""
    prospects = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prospects.append(row)
    return prospects

def guess_personal_email(first_name, last_name, domain):
    """Guess common email patterns"""
    patterns = [
        f"{first_name.lower()}.{last_name.lower()}@{domain}",
        f"{first_name.lower()}{last_name.lower()}@{domain}",
        f"{first_name.lower()[0]}{last_name.lower()}@{domain}",
        f"{first_name.lower()}@{domain}",
        f"{last_name.lower()}@{domain}",
    ]
    return patterns

def main():
    # Configuration
    csv_file = "/root/.openclaw/workspace/projects/connor-corp-skills/automation/output/all-prospects-60.csv"
    
    # SMTP config (user needs to fill these in)
    smtp_config = {
        "server": "smtp.zoho.com",  # or smtp.gmail.com
        "port": 587,
        "username": "mike.josephh@zohomail.com.au",  # user's email
        "password": "",  # NEEDS APP PASSWORD
        "from_email": "connor@connorcorp.ai"  # or user's email
    }
    
    # Load prospects
    prospects = load_prospects(csv_file)
    
    print(f"Loaded {len(prospects)} prospects")
    print("SMTP config needs:")
    print(f"  - Username: {smtp_config['username']}")
    print(f"  - Password: (needs app-specific password)")
    print(f"  - From: {smtp_config['from_email']}")
    print()
    
    # Show top 5 prospects with emails
    print("Top 5 prospects:")
    for i, p in enumerate(prospects[:5]):
        print(f"{i+1}. {p['Name']} @ {p['Company']} — {p.get('Email', 'NO EMAIL')}")
    
    print()
    print("To send emails:")
    print("1. Set up app password in Zoho/Gmail")
    print("2. Fill in smtp_config password above")
    print("3. Run: python3 email_sender.py --send")
    print()
    print("Email templates ready:")
    for name in TEMPLATES.keys():
        print(f"  - {name}")

if __name__ == "__main__":
    main()
