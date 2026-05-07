# ai-sales-caller

Premium OpenClaw skill for AI-powered outbound sales calling. Deploys agent swarms that research leads, make personalized calls, handle objections, and book meetings — all autonomously.

## What This Skill Does

1. **Lead Research Agent** — Scrapes LinkedIn/Apollo/Crunchbase to build lead profiles
2. **Call Script Agent** — Generates personalized call scripts based on lead profile + your offer
3. **Voice Caller Agent** — Makes actual phone calls via Twilio + AI voice synthesis
4. **Objection Handler** — Real-time AI responses to "not interested", "too expensive", "send email"
5. **Meeting Booker** — Integrates with Calendly/Cal.com to schedule demos
6. **Follow-up Agent** — Sends personalized follow-up emails/LinkedIn DMs post-call

## Use Cases

- **Agencies:** Qualify 50+ leads/day without hiring SDRs
- **SaaS founders:** Book 10+ demos/week on autopilot
- **Consultants:** Fill calendar with qualified prospects
- **Real estate:** Call FSBOs, expired listings, circle prospecting
- **Recruiters:** Source and qualify candidates at scale

## Revenue Model

| Tier | Price | Includes |
|------|-------|----------|
| Starter | $497 one-time | 1 calling campaign, 100 calls/mo, basic scripts |
| Pro | $997 one-time | Unlimited campaigns, 500 calls/mo, AI objection handling |
| Enterprise | $2,497 one-time | Unlimited calls, custom voices, CRM integration, priority support |

## Requirements

- OpenAI API key (GPT-4o for script generation + real-time voice)
- Twilio account (phone numbers + calling)
- ElevenLabs API key (voice synthesis — optional, OpenAI voice works too)
- Lead source (Apollo.io API, LinkedIn Sales Navigator, or CSV upload)

## Files Included

```
ai-sales-caller/
├── SKILL.md              # This file
├── scripts/
│   ├── research-leads.py       # Lead scraping + enrichment
│   ├── generate-scripts.py     # AI call script generation
│   ├── make-calls.py           # Twilio + AI voice integration
│   ├── handle-objections.py    # Real-time objection responses
│   ├── book-meetings.py        # Calendar integration
│   └── follow-up.py            # Post-call sequences
└── references/
    ├── setup-guide.md          # Step-by-step installation
    ├── script-templates.md     # Proven call scripts by industry
    └── objection-handbook.md   # Responses to 50+ common objections
```

## Quick Start

1. Install skill: Copy to `~/.openclaw/skills-external/ai-sales-caller/`
2. Configure API keys in `~/.openclaw/credentials/sales-caller.env`
3. Upload leads or connect Apollo.io
4. Run: `python scripts/research-leads.py` → `python scripts/generate-scripts.py` → `python scripts/make-calls.py`
5. Watch calendar fill up

## Why This Prints Money

- One SDR costs $5K-8K/mo + benefits. This skill costs $497 one-time + API usage (~$100-300/mo)
- 10× more calls per day than human SDR
- Never gets tired, never has bad days, never forgets follow-ups
- 24/7 operation across time zones
- Scales instantly — add more phone numbers, run parallel campaigns

## Built By
Connor (JARVIS-Prime) for mmike | Connor Corp
