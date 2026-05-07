"""Central configuration for the AI Sales Caller.

Loads API keys from credential files, defines offer details,
campaign settings, and tone customization options.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

WORKSPACE = Path("~/.openclaw/workspace").expanduser()
CREDENTIALS_DIR = Path("~/.openclaw/credentials").expanduser()
PROJECT_DIR = Path(__file__).resolve().parent

# ── API Keys (loaded from env files) ─────────────────────────────────────────

def _load_env_file(path: Path) -> None:
    """Load a .env file if it exists."""
    if path.exists():
        load_dotenv(path, override=False)
        logger.debug("Loaded env file: %s", path)
    else:
        logger.warning("Env file not found: %s", path)

_load_env_file(CREDENTIALS_DIR / "openai.env")
_load_env_file(CREDENTIALS_DIR / "twilio.env")

OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER: Optional[str] = os.getenv("TWILIO_PHONE_NUMBER")

if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set. Add it to %s", CREDENTIALS_DIR / "openai.env")
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    logger.error("Twilio credentials incomplete. Check %s", CREDENTIALS_DIR / "twilio.env")

# ── Apollo.io Configuration ─────────────────────────────────────────────────

APOLLO_API_KEY: Optional[str] = os.getenv("APOLLO_API_KEY")
APOLLO_BASE_URL: str = "https://api.apollo.io/v1"
APOLLO_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("APOLLO_RATE_LIMIT_PER_MINUTE", "100"))

# ── Clearbit Configuration ──────────────────────────────────────────────────

CLEARBIT_API_KEY: Optional[str] = os.getenv("CLEARBIT_API_KEY")
CLEARBIT_BASE_URL: str = "https://person.clearbit.com/v2"
CLEARBIT_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("CLEARBIT_RATE_LIMIT_PER_MINUTE", "600"))

# ── Proxy / Rotation ────────────────────────────────────────────────────────

PROXY_LIST: List[str] = field(default_factory=list)
_PROXY_ENV = os.getenv("PROXY_LIST", "")
if _PROXY_ENV:
    PROXY_LIST = [p.strip() for p in _PROXY_ENV.split(",") if p.strip()]

USE_PROXY_ROTATION: bool = os.getenv("USE_PROXY_ROTATION", "false").lower() == "true"
REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE_SECONDS: float = float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "1.5"))

# ── Offer / Campaign Configuration ──────────────────────────────────────────

@dataclass
class OfferConfig:
    """Describes the product / service being pitched."""
    name: str = "PostureBlend"
    tagline: str = "AI-powered posture correction for remote workers"
    value_proposition: str = (
        "Reduce back pain by 60% in 30 days without expensive ergonomic chairs. "
        "Our AI-driven daily routines adapt to your work schedule."
    )
    pricing_tier: str = "$49/month"
    target_audience: str = "Remote workers, software engineers, digital nomads"
    key_benefits: List[str] = field(default_factory=lambda: [
        "60% back-pain reduction in 30 days",
        "Personalised daily 5-minute routines",
        "Integrates with Slack & calendar",
        "No extra hardware needed",
    ])
    social_proof: str = "Used by 2,000+ remote-first companies including Canva & Atlassian"
    cta: str = "Can I book you a 10-minute demo this week?"
    objections_handling: Dict[str, str] = field(default_factory=lambda: {
        "price": "That's less than a single physio session — and it works every day.",
        "time": "Just 5 minutes a day. We integrate into your existing Slack stand-ups.",
        "already_have_solution": "Most ergonomic chairs fix the chair, not the person. We fix the habit.",
        "not_decision_maker": "Happy to loop in whoever signs off. I can send a one-pager they can review in 90 seconds.",
    })

@dataclass
class CampaignConfig:
    """Campaign-level settings."""
    campaign_name: str = "Q2-Remote-Worker-Outbound"
    max_leads_per_day: int = 50
    parallel_calls: int = 3
    call_window_start: str = "09:00"  # local time
    call_window_end: str = "17:00"
    timezone: str = "Australia/Melbourne"
    follow_up_days: List[int] = field(default_factory=lambda: [1, 3, 7])
    voicemail_script: str = (
        "Hi {first_name}, it's Connor from PostureBlend. I wanted to share how remote teams "
        "at {similar_company} cut back-pain complaints by 60%% in a month. "
        "Call me back on {agent_phone} or reply to my email. Thanks!"
    )

@dataclass
class ToneConfig:
    """Tone and style for generated scripts."""
    agent_name: str = "Connor"
    voice_style: str = "calm, confident, consultative — not salesy"
    greeting_style: str = "warm first-name basis, assume familiarity"
    pacing: str = "measured, pause after value prop, invite dialogue"
    industry_hooks: Dict[str, str] = field(default_factory=lambda: {
        "software": "I know stand-ups are sacred — what if posture cues were baked into them?",
        "finance": "Compliance teams love our audit-ready wellness ROI reports.",
        "healthcare": "Your clinicians sit for 10+ hours charting — we reduce their MSD claims.",
        "education": "Faculty wellness budgets are tight; our per-seat pricing scales down to $9.",
        "ecommerce": "Peak season means 14-hour desk days — our fatigue alerts keep AOV up.",
    })

# ── Global instances (import these) ─────────────────────────────────────────

OFFER = OfferConfig()
CAMPAIGN = CampaignConfig()
TONE = ToneConfig()

# ── Logging setup helper ─────────────────────────────────────────────────────

def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> None:
    """Configure root logger for the sales-caller scripts."""
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=handlers,
    )
    logger.info("Logging initialised (level=%s)", logging.getLevelName(level))

if __name__ == "__main__":
    setup_logging()
    logger.info("Config loaded. Offer=%s Campaign=%s", OFFER.name, CAMPAIGN.campaign_name)
