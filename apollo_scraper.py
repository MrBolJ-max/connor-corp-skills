```python
#!/usr/bin/env python3
"""
apollo_lead_scraper.py

Requirements (requirements.txt):
    requests>=2.31.0
    python-dotenv>=1.0.0

Usage:
    export APOLLO_API_KEY=your_key
    python apollo_lead_scraper.py --query "software engineer" --max-results 500 --output leads.json

Note:
    Apollo.io API schemas change over time. If field mappings drift,
    update the `_extract_lead` method below to match the current response shape.
"""

import argparse
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


class ApolloScraper:
    """
    Production-ready scraper for Apollo.io mixed people search.
    """

    BASE_URL: str = "https://api.apollo.io/api/v1/mixed_people/search"
    PER_PAGE: int = 100
    MAX_RETRIES: int = 3
    RATE_LIMIT_PER_MINUTE: int = 10
    MIN_REQUEST_INTERVAL: float = 60.0 / RATE_LIMIT_PER_MINUTE  # 6.0 seconds

    # Basic but practical email regex
    _EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    # Disposable/local domains to reject
    _DISPOSABLE_DOMAINS = {
        "localhost",
        "example.com",
        "test.com",
        "invalid.com",
    }

    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key
        self.session: requests.Session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "apollo-lead-scraper/1.0",
            }
        )
        self._last_request_time: Optional[float] = None

    def _apply_rate_limit(self) -> None:
        """Enforce 10 requests/minute by sleeping between calls."""
        if self._last_request_time is not None:
            elapsed: float = time.monotonic() - self._last_request_time
            sleep_needed: float = self.MIN_REQUEST_INTERVAL - elapsed
            if sleep_needed > 0:
                logging.debug("Rate limit sleep: %.2f seconds", sleep_needed)
                time.sleep(sleep_needed)
        self._last_request_time = time.monotonic()

    def _search_page(self, page: int, query: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single page from Apollo with manual retry + exponential backoff.
        Returns the parsed JSON response or None on hard failure.
        """
        payload: Dict[str, Any] = {
            "api_key": self.api_key,
            "page": page,
            "per_page": self.PER_PAGE,
            "q_keywords": query,
        }

        for attempt in range(1, self.MAX_RETRIES + 1):
            self._apply_rate_limit()

            try:
                response: requests.Response = self.session.post(
                    self.BASE_URL, json=payload, timeout=30
                )

                if response.status_code == 429:
                    backoff: float = 2 ** attempt
                    logging.warning(
                        "API rate limited (HTTP 429). Backing off %.0f seconds (attempt %d/%d).",
                        backoff,
                        attempt,
                        self.MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue

                response.raise_for_status()
                data: Dict[str, Any] = response.json()

                if not isinstance(data, dict):
                    logging.error("Unexpected response type: %s", type(data))
                    return None

                if data.get("error"):
                    logging.error("API error: %s", data.get("message", "Unknown"))
                    return None

                return data

            except requests.exceptions.Timeout:
                backoff = 2 ** (attempt - 1)
                logging.warning(
                    "Request timeout (attempt %d/%d). Retrying in %.0f seconds...",
                    attempt,
                    self.MAX_RETRIES,
                    backoff,
                )
                time.sleep(backoff)

            except requests.exceptions.HTTPError as e:
                status_code: int = e.response.status_code
                if 500 <= status_code < 600:
                    backoff = 2 ** (attempt - 1)
                    logging.warning(
                        "Server error %d (attempt %d/%d). Retrying in %.0f seconds...",
                        status_code,
                        attempt,
                        self.MAX_RETRIES,
                        backoff,
                    )
                    time.sleep(backoff)
                else:
                    logging.error("HTTP client error %d: %s", status_code, e)
                    return None

            except requests.exceptions.RequestException as e:
                backoff = 2 ** (attempt - 1)
                logging.warning(
                    "Network error: %s (attempt %d/%d). Retrying in %.0f seconds...",
                    e,
                    attempt,
                    self.MAX_RETRIES,
                    backoff,
                )
                time.sleep(backoff)

        logging.error("Failed to fetch page %d after %d attempts.", page, self.MAX_RETRIES)
        return None

    @staticmethod
    def validate_email(email: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Basic regex + domain validation.
        Returns (is_valid, normalized_email_or_none).
        """
        if not email or not isinstance(email, str):
            return False, None

        cleaned: str = email.strip().lower()
        if len(cleaned) > 254:
            return False, None

        if not ApolloScraper._EMAIL_REGEX.match(cleaned):
            return False, None

        try:
            local_part, domain = cleaned.rsplit("@", 1)
        except ValueError:
            return False, None

        if not local_part or not domain:
            return False, None

        # Domain-level validation
        if domain in ApolloScraper._DISPOSABLE_DOMAINS:
            return False, None
        if ".." in domain or domain.startswith(".") or domain.endswith("."):
            return False, None
        if domain.startswith("-") or domain.endswith("-"):
            return False, None

        # Ensure a plausible TLD
        parts: List[str] = domain.split(".")
        if len(parts) < 2:
            return False, None
        tld: str = parts[-1]
        if not tld.isalpha() or len(tld) < 2:
            return False, None

        return True, cleaned

    @staticmethod
    def _extract_lead(person: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map Apollo person record to the canonical lead schema.
        Returns None only if the record is unparseable (should be rare).
        """
        if not isinstance(person, dict):
            return None

        org: Dict[str, Any] = person.get("organization") or {}

        # Email
        raw_email: Optional[str] = (
            person.get("email")
            or person.get("contact", {}).get("email")
            or person.get("work_email")
        )
        is_valid_email, normalized_email = ApolloScraper.validate_email(raw_email)
        email: Optional[str] = normalized_email if is_valid_email else None

        # Phone
        phone: Optional[str] = None
        phones: List[Dict[str, Any]] = person.get("phone_numbers") or []
        if phones and isinstance(phones[0], dict):
            phone = phones[0].get("raw_number") or phones[0].get("number")
        if not phone:
            phone = person.get("direct_line") or person.get("mobile_phone") or person.get("phone")

        # LinkedIn
        linkedin: Optional[str] = person.get("linkedin_url") or person.get("linkedin")
        if linkedin and isinstance(linkedin, str) and not linkedin.startswith("http"):
            linkedin = f"https://{linkedin}"

        # Name
        name: Optional[str] = person.get("name")
        if not name:
            first: str = person.get("first_name") or ""
            last: str = person.get("last_name") or ""
            name = f"{first} {last}".strip() or None

        lead: Dict[str, Any] = {
            "name": name,
            "title": person.get("title") or person.get("job_title") or None,
            "company": org.get("name") if isinstance(org, dict) else None,
            "email": email,
            "linkedin_url": linkedin,
            "phone": phone,
            "industry": org.get("industry") if isinstance(org, dict) else None,
            "company_size": org.get("size") if isinstance(org, dict) else None,
        }
        return lead


class ProgressManager:
    """
    Handles incremental persistence so the job survives interruptions.
    """

    def __init__(self, output_path: Path) -> None:
        self.output_path: Path = output_path
        self.progress_path: Path = output_path.with_suffix(".progress.json")
        self.leads: List[Dict[str, Any]] = []
        self.next_page: int = 1
        self.total_fetched: int = 0

    def load(self) -> None:
        """Resume from prior progress file if one exists."""
        if not self.progress_path.exists():
            return

        try:
            with self.progress_path.open("r", encoding="utf-8") as fh:
                state: Dict[str, Any] = json.load(fh)
            self.leads = state.get("leads", [])
            self.next_page = state.get("next_page", 1)
            self.total_fetched = state.get("total_fetched", 0)
            logging.info(
                "Resumed from %s (page %d, %d leads already fetched).",
                self.progress_path,
                self.next_page,
                self.total_fetched,
            )
        except (json.JSONDecodeError, OSError) as e:
            logging.warning("Could not resume progress: %s. Starting fresh.", e)
            self.leads = []
            self.next_page = 1
            self.total_fetched = 0

    def save(self) -> None:
        """Atomically write current state to the progress file."""
        state: Dict[str, Any] = {
            "leads": self.leads,
            "next_page": self.next_page,
            "total_fetched": self.total_fetched,
            "saved_at": datetime.utcnow().isoformat(),
        }
        try:
            with self.progress_path.open("w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, ensure_ascii=False)
        except OSError as e:
            logging.error("Failed to write progress file: %s", e)

    def finalize(self) -> None:
        """Write the final output JSON and remove the progress artifact."""
        try:
            with self.output_path.open("w", encoding="utf-8") as fh:
                json.dump(self.leads, fh, indent=2, ensure_ascii=False)
            logging.info("Output saved to %s (%d leads).", self.output_path, len(self.leads))
            if self.progress_path.exists():
                self.progress_path.unlink()
                logging.info("Progress file cleaned up.")
        except OSError as e:
            logging.error("Failed to write output file: %s", e)
            sys.exit(1)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.Argument