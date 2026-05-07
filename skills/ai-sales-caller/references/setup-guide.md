# Setup Guide — AI Sales Caller

## Prerequisites

1. OpenClaw installed
2. Python 3.11+
3. API keys (see below)

## API Keys Needed

Create `~/.openclaw/credentials/sales-caller.env`:

```bash
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890
ELEVENLABS_API_KEY=eleven_...  # Optional — OpenAI voice works too
APOLLO_API_KEY=...              # Optional — can use CSV upload instead
CALENDLY_API_KEY=...            # Optional — for meeting booking
```

## Installation

1. Copy skill to OpenClaw skills directory:
```bash
cp -r ~/.openclaw/workspace/projects/connor-corp-skills/skills/ai-sales-caller ~/.openclaw/skills-external/
```

2. Install dependencies:
```bash
pip install openai twilio requests beautifulsoup4 pandas python-dotenv
```

3. Configure your offer:
Edit `scripts/config.py` with your:
- Company name
- What you sell
- Target customer
- Pricing
- Key benefits

## Running Your First Campaign

### Step 1: Research Leads
```bash
python scripts/research-leads.py --source apollo --query "e-commerce owner" --limit 50
```
Outputs: `data/leads_2026-05-07.json`

### Step 2: Generate Scripts
```bash
python scripts/generate-scripts.py --leads data/leads_2026-05-07.json --tone professional
```
Outputs: `data/scripts_2026-05-07.json`

### Step 3: Make Calls
```bash
python scripts/make-calls.py --scripts data/scripts_2026-05-07.json --batch 10
```
Logs: `logs/calls_2026-05-07.log`

### Step 4: Follow Up
```bash
python scripts/follow-up.py --campaign calls_2026-05-07
```

## Monitoring

- Check `logs/` for call outcomes
- View `data/` for lead enrichment
- Run `python scripts/analytics.py` for campaign metrics

## Troubleshooting

**Twilio errors:** Verify phone number has Voice capability enabled
**OpenAI rate limits:** Add `time.sleep(1)` between calls or upgrade plan
**Low answer rate:** Try different times (8-10 AM, 1-3 PM local time)

## Safety / Compliance

- Always check Do Not Call lists
- Include opt-out language
- Record calls where legally required
- Never call same lead more than 3 times in 7 days

---
Built by Connor Corp
