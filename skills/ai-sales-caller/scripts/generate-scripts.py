#!/usr/bin/env python3
"""Generate personalised AI cold-call scripts for each lead.

Reads a `leads_*.json` file produced by `research-leads.py`, combines each
lead record with the central offer / tone / campaign config, and calls the
OpenAI Chat Completions API (gpt-4o) to produce:

  1. A full conversational script (greeting → hook → value prop → CTA → objection prep)
  2. A concise voicemail variant
  3. A one-paragraph email follow-up

Output:
    Writes `scripts_YYYYMMDD_HHMMSS.json` in the scripts directory.

Usage:
    python generate-scripts.py --leads leads_20260507_120000.json --model gpt-4o
"""

import argparse
import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    CAMPAIGN,
    MAX_RETRIES,
    OFFER,
    OPENAI_API_KEY,
    RETRY_BACKOFF_BASE_SECONDS,
    TONE,
    setup_logging,
)

logger = logging.getLogger("generate-scripts")

# ── Data model ──────────────────────────────────────────────────────────────

@dataclass
class GeneratedScript:
    """Final script bundle for a single lead."""
    lead_id: str
    lead_name: str
    lead_company: str
    lead_title: str
    lead_industry: str
    script_main: str
    script_voicemail: str
    script_email: str
    suggested_time_slot: str
    risk_flags: List[str]
    model_used: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items()}


# ── OpenAI client with retry ─────────────────────────────────────────────────

OPENAI_BASE = "https://api.openai.com/v1"

class OpenAIClient:
    """Minimal typed wrapper around OpenAI Chat Completions."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is missing.")
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE_SECONDS, min=1, max=60),
        reraise=True,
    )
    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 1200) -> str:
        """Call the Chat Completions endpoint and return the assistant message content."""
        url = f"{OPENAI_BASE}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        if not content:
            logger.warning("Empty completion from OpenAI: %s", data)
        return content.strip()

# ── Prompt engineering ───────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    """Return the system prompt that shapes the assistant's personality."""
    return (
        f"You are {TONE.agent_name}, a senior sales development representative.\n"
        f"Voice: {TONE.voice_style}.\n"
        f"Greeting: {TONE.greeting_style}.\n"
        f"Pacing: {TONE.pacing}.\n\n"
        "Rules:\n"
        "1. Never sound robotic or use generic opener clichés.\n"
        "2. Use the industry hook if one matches the lead's sector.\n"
        "3. Insert the lead's first name, company, and title naturally.\n"
        "4. Reference one specific, believable benefit tied to their role.\n"
        "5. Include a soft trial-close and handle the top 2 likely objections.\n"
        "6. Keep the main script under 250 words (≈ 90 seconds spoken).\n"
        "7. Voicemail must be under 30 seconds.\n"
        "8. Email must be 3 short paragraphs max.\n"
    )


def _build_user_prompt(lead: Dict[str, Any]) -> str:
    """Build the user prompt for a single lead."""
    industry = (lead.get("company_industry", "") or "general").lower()
    hook = TONE.industry_hooks.get(industry, "")
    if not hook:
        # fuzzy fallback
        for key, value in TONE.industry_hooks.items():
            if key in industry or industry in key:
                hook = value
                break

    return (
        "Generate three outputs for this lead:\n\n"
        f"Lead: {lead.get('first_name', '')} {lead.get('last_name', '')}, "
        f"{lead.get('title', '')} at {lead.get('company_name', '')}.\n"
        f"Industry: {lead.get('company_industry', 'unknown')}.\n"
        f"Location: {lead.get('location', '')}.\n"
        f"Company size: {lead.get('company_size', '')}.\n"
        f"Tech stack: {', '.join(lead.get('company_tech_stack', [])[:5]) or 'N/A'}.\n\n"
        f"Offer: {OFFER.name} — {OFFER.tagline}.\n"
        f"Value prop: {OFFER.value_proposition}\n"
        f"Pricing: {OFFER.pricing_tier}\n"
        f"Social proof: {OFFER.social_proof}\n"
        f"CTA: {OFFER.cta}\n\n"
        f"Industry hook (use if relevant): {hook}\n\n"
        "Output format (strict JSON):\n"
        "{\n"
        '  "script_main": "...",\n'
        '  "script_voicemail": "...",\n'
        '  "script_email": "...",\n'
        '  "suggested_time_slot": "Tuesday 10:30 AM",\n'
        '  "risk_flags": ["no_phone", "junior_title"]\n'
        "}\n"
    )


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extract JSON from the model response, tolerating markdown fences."""
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed (%s). Wrapping raw text.", exc)
        return {
            "script_main": text,
            "script_voicemail": "",
            "script_email": "",
            "suggested_time_slot": "",
            "risk_flags": ["parse_error"],
        }

# ── Risk flags ──────────────────────────────────────────────────────────────

def _compute_risk_flags(lead: Dict[str, Any]) -> List[str]:
    """Static risk analysis independent of the LLM."""
    flags: List[str] = []
    if not lead.get("phone"):
        flags.append("no_phone")
    if not lead.get("email"):
        flags.append("no_email")
    title = (lead.get("title", "") or "").lower()
    junior_titles = {"intern", "student", "junior", "associate", "assistant", "coordinator"}
    if any(j in title for j in junior_titles):
        flags.append("junior_title")
    if lead.get("company_size") and int(str(lead["company_size"]).replace(",", "")) < 10:
        flags.append("tiny_company")
    if not lead.get("company_industry"):
        flags.append("unknown_industry")
    return flags

# ── Orchestrator ─────────────────────────────────────────────────────────────

class ScriptGenerator:
    """High-level generator that marries leads + config + LLM."""

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.7):
        self.client = OpenAIClient(model=model)
        self.temperature = temperature
        self.system_prompt = _build_system_prompt()

    def generate(self, lead: Dict[str, Any]) -> GeneratedScript:
        """Produce a script bundle for one lead."""
        user_prompt = _build_user_prompt(lead)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = self.client.chat_completion(messages, temperature=self.temperature)
        parsed = _parse_response(raw)
        risk_flags = list(set(_compute_risk_flags(lead) + parsed.get("risk_flags", [])))

        # Fill voicemail fallback if empty
        voicemail = parsed.get("script_voicemail", "")
        if not voicemail:
            first_name = lead.get("first_name", "there")
            similar = lead.get("company_name", "a similar team")
            agent_phone = CAMPAIGN.voicemail_script.split("{agent_phone}")[0] if "{agent_phone}" in CAMPAIGN.voicemail_script else ""
            # crude template fallback
            voicemail = (
                f"Hi {first_name}, it's {TONE.agent_name} from {OFFER.name}. "
                f"I wanted to share how teams like {similar} cut back-pain complaints by 60% in a month. "
                f"Call me back or reply to my email. Thanks!"
            )

        return GeneratedScript(
            lead_id=lead.get("id", "unknown"),
            lead_name=f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
            lead_company=lead.get("company_name", ""),
            lead_title=lead.get("title", ""),
            lead_industry=lead.get("company_industry", ""),
            script_main=parsed.get("script_main", ""),
            script_voicemail=voicemail,
            script_email=parsed.get("script_email", ""),
            suggested_time_slot=parsed.get("suggested_time_slot", ""),
            risk_flags=risk_flags,
            model_used=self.client.model,
            generated_at=datetime.now().isoformat(),
        )

# ── I/O helpers ─────────────────────────────────────────────────────────────

def load_leads(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_scripts(scripts: List[GeneratedScript], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"scripts_{ts}.json"
    records = [s.to_dict() for s in scripts]
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote %d scripts -> %s", len(scripts), out_path)
    return out_path

# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate personalised sales call scripts")
    p.add_argument("--leads", type=Path, required=True, help="Path to leads JSON file")
    p.add_argument("--model", default="gpt-4o", help="OpenAI model ID")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--limit", type=int, default=0, help="Max leads to process (0 = all)")
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--dry-run", action="store_true", help="Print prompt, skip API call")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    setup_logging(level=getattr(logging, args.log_level.upper()), log_file=args.out_dir / "scripts.log")

    if not args.leads.exists():
        raise FileNotFoundError(f"Leads file not found: {args.leads}")

    leads = load_leads(args.leads)
    if args.limit > 0:
        leads = leads[: args.limit]
    logger.info("Loaded %d leads from %s", len(leads), args.leads)

    generator = ScriptGenerator(model=args.model, temperature=args.temperature)
    scripts: List[GeneratedScript] = []

    for idx, lead in enumerate(leads, start=1):
        logger.info("[%d/%d] Generating script for %s @ %s", idx, len(leads), lead.get("first_name", "?"), lead.get("company_name", "?"))
        if args.dry_run:
            print("--- PROMPT ---")
            print(_build_user_prompt(lead))
            print("--------------")
            continue
        try:
            script = generator.generate(lead)
            scripts.append(script)
        except Exception as exc:
            logger.error("Failed for lead %s: %s", lead.get("id", "?"), exc)
        # polite rate limiting: 20 RPM on gpt-4o tier 1
        time.sleep(3.0)

    if not args.dry_run:
        out_path = write_scripts(scripts, args.out_dir)
        logger.info("Done. %d scripts generated -> %s", len(scripts), out_path)


if __name__ == "__main__":
    main()
