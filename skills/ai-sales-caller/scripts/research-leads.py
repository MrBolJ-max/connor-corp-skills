#!/usr/bin/env python3
"""Lead research engine for AI Sales Caller.

Supports:
  * Apollo.io API search (people / organizations)
  * CSV batch upload as fallback / augmentation
  * Clearbit enrichment (person + company)
  * Proxy rotation, rate limiting, exponential backoff
  * Structured JSON output ready for script generation

Usage:
    python research-leads.py --source apollo --query "software engineer" --limit 50
    python research-leads.py --source csv --file leads.csv --enrich

Output:
    Writes `leads_YYYYMMDD_HHMMSS.json` in the scripts directory.
"""

import argparse
import csv
import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    APOLLO_API_KEY,
    APOLLO_BASE_URL,
    APOLLO_RATE_LIMIT_PER_MINUTE,
    CLEARBIT_API_KEY,
    CLEARBIT_BASE_URL,
    CLEARBIT_RATE_LIMIT_PER_MINUTE,
    MAX_RETRIES,
    PROXY_LIST,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_BACKOFF_BASE_SECONDS,
    USE_PROXY_ROTATION,
    setup_logging,
)

logger = logging.getLogger("research-leads")

# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class Lead:
    """Normalised lead record."""
    id: str
    source: str  # 'apollo' | 'csv' | 'mixed'
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    title: str = ""
    seniority: str = ""
    department: str = ""
    company_name: str = ""
    company_domain: str = ""
    company_industry: str = ""
    company_size: str = ""
    company_annual_revenue: str = ""
    company_tech_stack: List[str] = field(default_factory=list)
    linkedin_url: str = ""
    twitter_handle: str = ""
    location: str = ""
    timezone: str = ""
    enriched: bool = False
    enrichment_source: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items()}


# ── Rate limiter ────────────────────────────────────────────────────────────

class TokenBucket:
    """Thread-safe enough for single-process scripts."""

    def __init__(self, rate_per_minute: int):
        self.tokens = float(rate_per_minute)
        self.cap = float(rate_per_minute)
        self.rate = float(rate_per_minute) / 60.0
        self.last = time.monotonic()
        self._lock = False  # simplicity: we run sync

    def acquire(self, tokens: float = 1.0) -> None:
        """Sleep if necessary until a token is available."""
        while True:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(self.cap, self.tokens + elapsed * self.rate)
            self.last = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            sleep_needed = (tokens - self.tokens) / self.rate
            logger.debug("Rate-limit sleep %.2fs", sleep_needed)
            time.sleep(sleep_needed)


apollo_limiter = TokenBucket(APOLLO_RATE_LIMIT_PER_MINUTE)
clearbit_limiter = TokenBucket(CLEARBIT_RATE_LIMIT_PER_MINUTE)

# ── Proxy rotation ───────────────────────────────────────────────────────────

_proxy_cycle: Iterator[str] = iter([])

def _init_proxies() -> None:
    global _proxy_cycle
    if PROXY_LIST:
        _proxy_cycle = iter(random.sample(PROXY_LIST, len(PROXY_LIST)))
    else:
        _proxy_cycle = iter([])

_init_proxies()

def next_proxy() -> Optional[str]:
    """Return the next proxy URL, cycling through the list."""
    global _proxy_cycle
    try:
        return next(_proxy_cycle)
    except StopIteration:
        if PROXY_LIST:
            _proxy_cycle = iter(random.sample(PROXY_LIST, len(PROXY_LIST)))
            return next(_proxy_cycle)
        return None

# ── HTTP helpers with retry ─────────────────────────────────────────────────

HTTP_ERRORS = (httpx.HTTPStatusError, httpx.NetworkError, httpx.TimeoutException)

@retry(
    retry=retry_if_exception_type(HTTP_ERRORS),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE_SECONDS, min=1, max=60),
    reraise=True,
)
def _http_get(url: str, headers: Dict[str, str], limiter: TokenBucket) -> httpx.Response:
    limiter.acquire()
    proxy = next_proxy() if USE_PROXY_ROTATION else None
    proxies = {"all://": proxy} if proxy else None
    logger.debug("GET %s (proxy=%s)", url, proxy)
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, proxies=proxies) as client:  # type: ignore[arg-type]
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp

@retry(
    retry=retry_if_exception_type(HTTP_ERRORS),
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE_SECONDS, min=1, max=60),
    reraise=True,
)
def _http_post(url: str, headers: Dict[str, str], payload: Dict[str, Any], limiter: TokenBucket) -> httpx.Response:
    limiter.acquire()
    proxy = next_proxy() if USE_PROXY_ROTATION else None
    proxies = {"all://": proxy} if proxy else None
    logger.debug("POST %s (proxy=%s)", url, proxy)
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, proxies=proxies) as client:  # type: ignore[arg-type]
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp

# ── Apollo.io scraper ───────────────────────────────────────────────────────

class ApolloClient:
    """Thin wrapper around the Apollo.io REST API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or APOLLO_API_KEY
        if not self.api_key:
            raise RuntimeError("Apollo API key is missing. Set APOLLO_API_KEY in env.")
        self.base = APOLLO_BASE_URL
        self.headers = {"Content-Type": "application/json", "X-Api-Key": self.api_key}

    def search_people(
        self,
        query: Optional[str] = None,
        titles: Optional[List[str]] = None,
        person_locations: Optional[List[str]] = None,
        organization_domains: Optional[List[str]] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> Tuple[List[Lead], bool]:
        """Search Apollo people. Returns (leads, has_next_page)."""
        url = urljoin(self.base, "/mixed_people/search")
        payload: Dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),
            "contact_email_status": ["verified", "unverified", "likely_valid"],
        }
        if query:
            payload["q_keywords"] = query
        if titles:
            payload["person_titles"] = titles
        if person_locations:
            payload["person_locations"] = person_locations
        if organization_domains:
            payload["organization_domains"] = organization_domains

        resp = _http_post(url, self.headers, payload, apollo_limiter)
        data = resp.json()
        people = data.get("people", [])
        leads = [self._to_lead(p, "apollo") for p in people]
        has_next = data.get("pagination", {}).get("page", page) < data.get("pagination", {}).get("total_pages", page)
        logger.info("Apollo page %d -> %d leads (has_next=%s)", page, len(leads), has_next)
        return leads, has_next

    def _to_lead(self, person: Dict[str, Any], source: str) -> Lead:
        org = person.get("organization", {})
        return Lead(
            id=str(person.get("id", "")) or f"apollo_{random.randint(10**6, 10**7)}",
            source=source,
            first_name=person.get("first_name", ""),
            last_name=person.get("last_name", ""),
            email=person.get("email", ""),
            phone=person.get("phone", ""),
            title=person.get("title", ""),
            seniority=person.get("seniority", ""),
            department=person.get("department", ""),
            company_name=org.get("name", ""),
            company_domain=org.get("primary_domain", ""),
            company_industry=org.get("industry", ""),
            company_size=org.get("estimated_num_employees", ""),
            company_annual_revenue=org.get("annual_revenue", ""),
            company_tech_stack=org.get("technologies", []),
            linkedin_url=person.get("linkedin_url", ""),
            twitter_handle=person.get("twitter_url", ""),
            location=person.get("location", ""),
            timezone=person.get("time_zone", ""),
            raw=person,
        )

# ── Clearbit enrichment ─────────────────────────────────────────────────────

class ClearbitClient:
    """Enrich leads via Clearbit Person + Company APIs."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or CLEARBIT_API_KEY
        self.base = CLEARBIT_BASE_URL
        self.headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def enrich(self, lead: Lead) -> Lead:
        """Enrich a single lead in-place. Returns the same instance."""
        if not self.api_key:
            logger.warning("Clearbit key missing — skipping enrichment for %s", lead.id)
            return lead

        # Try person enrichment by email
        if lead.email:
            try:
                person_url = urljoin(self.base, f"/combined/find?email={lead.email}")
                resp = _http_get(person_url, self.headers, clearbit_limiter)
                data = resp.json()
                person = data.get("person", {})
                company = data.get("company", {})
                self._apply(lead, person, company)
                lead.enriched = True
                lead.enrichment_source = "clearbit"
                logger.info("Enriched %s via email", lead.id)
                return lead
            except Exception as exc:
                logger.warning("Clearbit email enrichment failed for %s: %s", lead.id, exc)

        # Fallback: company enrichment by domain
        if lead.company_domain:
            try:
                company_url = urljoin("https://company.clearbit.com/v2/", f"companies/find?domain={lead.company_domain}")
                resp = _http_get(company_url, self.headers, clearbit_limiter)
                company = resp.json()
                self._apply(lead, {}, company)
                lead.enriched = True
                lead.enrichment_source = "clearbit_company"
                logger.info("Enriched %s via domain", lead.id)
            except Exception as exc:
                logger.warning("Clearbit domain enrichment failed for %s: %s", lead.id, exc)

        return lead

    def _apply(self, lead: Lead, person: Dict[str, Any], company: Dict[str, Any]) -> None:
        if person.get("name", {}).get("givenName"):
            lead.first_name = person["name"]["givenName"]
        if person.get("name", {}).get("familyName"):
            lead.last_name = person["name"]["familyName"]
        if person.get("employment", {}).get("title"):
            lead.title = person["employment"]["title"]
        if person.get("employment", {}).get("seniority"):
            lead.seniority = person["employment"]["seniority"]
        if person.get("employment", {}).get("role"):
            lead.department = person["employment"]["role"]
        if person.get("linkedin", {}).get("handle"):
            lead.linkedin_url = f"https://linkedin.com/in/{person['linkedin']['handle']}"
        if person.get("location"):
            lead.location = person["location"]
        if person.get("timeZone"):
            lead.timezone = person["timeZone"]

        if company.get("name"):
            lead.company_name = company["name"]
        if company.get("domain"):
            lead.company_domain = company["domain"]
        if company.get("industry"):
            lead.company_industry = company["industry"]
        if company.get("metrics", {}).get("employees"):
            lead.company_size = str(company["metrics"]["employees"])
        if company.get("metrics", {}).get("annualRevenue"):
            lead.company_annual_revenue = str(company["metrics"]["annualRevenue"])
        if company.get("tech"):
            lead.company_tech_stack = company["tech"]

# ── CSV loader ───────────────────────────────────────────────────────────────

def load_csv(path: Path) -> List[Lead]:
    """Load leads from a CSV file, normalising common header variants."""
    leads: List[Lead] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader, start=1):
            leads.append(
                Lead(
                    id=f"csv_{idx}_{datetime.now().strftime('%Y%m%d')}",
                    source="csv",
                    first_name=_col(row, ["first_name", "firstname", "first name", "fname"]),
                    last_name=_col(row, ["last_name", "lastname", "last name", "lname"]),
                    email=_col(row, ["email", "e-mail", "email_address"]),
                    phone=_col(row, ["phone", "phone_number", "mobile", "tel"]),
                    title=_col(row, ["title", "job_title", "role"]),
                    company_name=_col(row, ["company", "company_name", "organisation", "organization"]),
                    company_domain=_col(row, ["domain", "company_domain", "website"]),
                    company_industry=_col(row, ["industry", "sector"]),
                    company_size=_col(row, ["company_size", "employees", "headcount"]),
                    location=_col(row, ["location", "city", "country"]),
                    raw=dict(row),
                )
            )
    logger.info("Loaded %d leads from %s", len(leads), path)
    return leads


def _col(row: Dict[str, str], variants: List[str]) -> str:
    """Return the first matching column value (case-insensitive)."""
    lower = {k.lower().strip(): v for k, v in row.items() if k}
    for v in variants:
        if v in lower:
            return lower[v].strip()
    return ""

# ── Output helpers ───────────────────────────────────────────────────────────

def write_leads(leads: List[Lead], out_dir: Optional[Path] = None) -> Path:
    """Serialize leads to a timestamped JSON file."""
    out_dir = out_dir or Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"leads_{ts}.json"
    records = [l.to_dict() for l in leads]
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote %d leads -> %s", len(leads), out_path)
    return out_path

# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Research and enrich sales leads")
    p.add_argument("--source", choices=["apollo", "csv", "both"], required=True)
    p.add_argument("--query", default="", help="Apollo keywords / job titles")
    p.add_argument("--titles", nargs="+", default=["Software Engineer"], help="Apollo person titles filter")
    p.add_argument("--limit", type=int, default=50, help="Max leads to fetch")
    p.add_argument("--file", type=Path, help="CSV input path (required when source=csv)")
    p.add_argument("--enrich", action="store_true", help="Run Clearbit enrichment")
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--log-level", default="INFO")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    setup_logging(level=getattr(logging, args.log_level.upper()), log_file=args.out_dir / "research.log")

    all_leads: List[Lead] = []

    # ── Apollo ──
    if args.source in ("apollo", "both"):
        if not APOLLO_API_KEY:
            logger.error("Apollo API key missing — skipping.")
        else:
            client = ApolloClient()
            page = 1
            while len(all_leads) < args.limit:
                batch, has_next = client.search_people(
                    query=args.query,
                    titles=args.titles,
                    page=page,
                    per_page=100,
                )
                all_leads.extend(batch)
                if not has_next or not batch:
                    break
                page += 1
                if len(all_leads) >= args.limit:
                    break
            all_leads = all_leads[: args.limit]

    # ── CSV ──
    if args.source in ("csv", "both"):
        if not args.file or not args.file.exists():
            raise FileNotFoundError(f"CSV file required but not found: {args.file}")
        csv_leads = load_csv(args.file)
        all_leads.extend(csv_leads)

    # ── Enrichment ──
    if args.enrich:
        cb = ClearbitClient()
        for lead in all_leads:
            cb.enrich(lead)
            time.sleep(0.5)  # polite pacing

    # ── Deduplicate by email ──
    seen: set = set()
    deduped: List[Lead] = []
    for l in all_leads:
        key = l.email or l.linkedin_url or l.id
        if key not in seen:
            seen.add(key)
            deduped.append(l)

    # ── Write ──
    out_path = write_leads(deduped, args.out_dir)
    logger.info("Done. %d unique leads -> %s", len(deduped), out_path)


if __name__ == "__main__":
    main()
