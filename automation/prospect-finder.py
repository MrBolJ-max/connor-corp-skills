#!/usr/bin/env python3
"""
prospect-finder.py — Connor Corp Outreach Automation
Finds agency owners, SaaS founders, consultants on LinkedIn/Apollo/Twitter.
Outputs CSV with: name, company, email, LinkedIn URL, industry, company size, pain signals.
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

import requests

# ─── Configuration ────────────────────────────────────────────────────────────

OUTPUT_DIR = Path.home() / ".openclaw" / "workspace" / "projects" / "connor-corp-skills" / "automation" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUTPUT_DIR / "prospect-finder.log"
CSV_OUTPUT = OUTPUT_DIR / "prospects.csv"
JSON_OUTPUT = OUTPUT_DIR / "prospects.json"

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
LINKEDIN_API_KEY = os.getenv("LINKEDIN_API_KEY", "")

# Target personas
TARGET_TITLES = [
    "CEO", "Founder", "Co-Founder", "Owner", "Managing Director",
    "VP Sales", "Head of Sales", "Sales Director", "Chief Revenue Officer",
    "VP Marketing", "Head of Marketing", "CMO",
    "Consultant", "Agency Owner", "Principal"
]

TARGET_INDUSTRIES = [
    "saas", "software", "marketing agency", "digital agency",
    "consulting", "professional services", "b2b services"
]

COMPANY_SIZE_RANGES = [
    "1-10", "11-50", "51-200", "201-500"
]

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("prospect-finder")

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple token bucket rate limiter."""
    def __init__(self, max_calls: int, per_seconds: int):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls = []
        self._lock = False

    def wait(self):
        now = time.time()
        self.calls = [c for c in self.calls if now - c < self.per_seconds]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.per_seconds - (now - self.calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit hit. Sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        self.calls.append(time.time())

apollo_limiter = RateLimiter(max_calls=100, per_seconds=60)
linkedin_limiter = RateLimiter(max_calls=50, per_seconds=60)

# ─── Prospect Model ───────────────────────────────────────────────────────────

class Prospect:
    def __init__(self, name: str, company: str, email: str = "",
                 linkedin_url: str = "", title: str = "",
                 industry: str = "", company_size: str = "",
                 pain_signals: List[str] = None, source: str = "",
                 confidence: float = 0.0):
        self.name = name
        self.company = company
        self.email = email
        self.linkedin_url = linkedin_url
        self.title = title
        self.industry = industry
        self.company_size = company_size
        self.pain_signals = pain_signals or []
        self.source = source
        self.confidence = confidence

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "company": self.company,
            "email": self.email,
            "linkedin_url": self.linkedin_url,
            "title": self.title,
            "industry": self.industry,
            "company_size": self.company_size,
            "pain_signals": ", ".join(self.pain_signals),
            "source": self.source,
            "confidence": self.confidence,
            "discovered_at": datetime.now().isoformat()
        }

# ─── Pain Signal Detector ─────────────────────────────────────────────────────

PAIN_KEYWORDS = [
    "hiring", "growing fast", "scaling", "new funding", "series a",
    "series b", "expanding", "launching", "new product", "hiring sales",
    "customer acquisition", "lead generation", "outbound", "cold calling",
    "sales team", "revenue growth", "pipeline", "prospecting"
]

def detect_pain_signals(company_data: Dict) -> List[str]:
    """Extract pain signals from company data."""
    signals = []
    text = json.dumps(company_data).lower()
    for keyword in PAIN_KEYWORDS:
        if keyword in text:
            signals.append(keyword)
    return signals[:5]  # Top 5 signals

# ─── Apollo.io Search ─────────────────────────────────────────────────────────

def search_apollo(title: str, industry: str, page: int = 1) -> List[Prospect]:
    """Search Apollo.io for prospects."""
    if not APOLLO_API_KEY:
        logger.warning("APOLLO_API_KEY not set. Skipping Apollo search.")
        return []

    apollo_limiter.wait()

    url = "https://api.apollo.io/v1/mixed_people/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {APOLLO_API_KEY}"
    }
    payload = {
        "person_titles": [title],
        "person_locations": ["United States", "United Kingdom", "Australia", "Canada"],
        "organization_industries": [industry],
        "page": page,
        "per_page": 25
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        prospects = []
        for person in data.get("people", []):
            org = person.get("organization", {})
            pain = detect_pain_signals(org)

            prospect = Prospect(
                name=f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                company=org.get("name", ""),
                email=person.get("email", ""),
                linkedin_url=person.get("linkedin_url", ""),
                title=person.get("title", ""),
                industry=org.get("industry", industry),
                company_size=org.get("estimated_num_employees", ""),
                pain_signals=pain,
                source="apollo",
                confidence=person.get("contact_accuracy_score", 0.5)
            )
            prospects.append(prospect)

        logger.info(f"Apollo: Found {len(prospects)} prospects for {title} in {industry}")
        return prospects

    except requests.exceptions.RequestException as e:
        logger.error(f"Apollo API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected Apollo error: {e}")
        return []

# ─── LinkedIn Search (Mock/Scrape placeholder) ────────────────────────────────

def search_linkedin(title: str, industry: str) -> List[Prospect]:
    """Search LinkedIn for prospects. Requires LinkedIn API or scraping."""
    if not LINKEDIN_API_KEY:
        logger.warning("LINKEDIN_API_KEY not set. Skipping LinkedIn search.")
        return []

    linkedin_limiter.wait()

    # Placeholder for LinkedIn API integration
    # LinkedIn requires OAuth2 and special API access
    # For now, return empty and log instructions
    logger.info("LinkedIn search requires OAuth2 setup. See documentation.")
    return []

# ─── Twitter/X Search ─────────────────────────────────────────────────────────

def search_twitter_bio_keywords(keywords: List[str]) -> List[Prospect]:
    """Search Twitter/X bios for prospect signals."""
    # Placeholder for Twitter API integration
    # Twitter API v2 requires bearer token
    logger.info("Twitter search requires Twitter API v2 setup.")
    return []

# ─── CSV/JSON Export ────────────────────────────────────────────────────────────

def export_prospects(prospects: List[Prospect]):
    """Export prospects to CSV and JSON."""
    if not prospects:
        logger.warning("No prospects to export")
        return

    # CSV export
    fieldnames = ["name", "company", "email", "linkedin_url", "title",
                  "industry", "company_size", "pain_signals", "source",
                  "confidence", "discovered_at"]

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in prospects:
            writer.writerow(p.to_dict())

    # JSON export
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in prospects], f, indent=2)

    logger.info(f"Exported {len(prospects)} prospects to {CSV_OUTPUT} and {JSON_OUTPUT}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("PROSPECT FINDER — Connor Corp Outreach Automation")
    logger.info("=" * 60)

    all_prospects: List[Prospect] = []
    max_prospects = int(os.getenv("MAX_PROSPECTS", "200"))

    # Search across multiple titles and industries
    for title in TARGET_TITLES[:5]:  # Limit to top 5 titles
        for industry in TARGET_INDUSTRIES[:3]:  # Limit to top 3 industries
            if len(all_prospects) >= max_prospects:
                break

            logger.info(f"Searching: {title} in {industry}")

            # Apollo search
            prospects = search_apollo(title, industry)
            all_prospects.extend(prospects)

            # Rate limiting between searches
            time.sleep(random.uniform(1, 3))

        if len(all_prospects) >= max_prospects:
            break

    # Deduplicate by email/LinkedIn
    seen = set()
    unique_prospects = []
    for p in all_prospects:
        key = p.email or p.linkedin_url or f"{p.name}-{p.company}"
        if key and key not in seen:
            seen.add(key)
            unique_prospects.append(p)

    logger.info(f"Total unique prospects: {len(unique_prospects)}")
    export_prospects(unique_prospects)

    logger.info("Done.")
    return len(unique_prospects)

if __name__ == "__main__":
    count = main()
    sys.exit(0 if count > 0 else 1)
