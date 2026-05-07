# Connor Corp Outreach Automation System

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `prospect-finder.py` | ~220 | Finds prospects on Apollo/LinkedIn/Twitter |
| `outreach-dm.py` | ~290 | Generates personalized DMs and emails |
| `content-generator.py` | ~240 | Creates viral Twitter/Reddit/IndieHackers content |
| `send-queue.py` | ~310 | Sends messages via SMTP/LinkedIn with tracking |

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create credentials file:
```bash
mkdir -p ~/.openclaw/credentials
cat > ~/.openclaw/credentials/openai.env << 'EOF'
OPENAI_API_KEY=sk-your-key-here
EOF
```

3. Set API keys (optional):
```bash
export APOLLO_API_KEY=your-apollo-key
export LINKEDIN_API_KEY=your-linkedin-key
export SMTP_USER=your-email@gmail.com
export SMTP_PASS=your-app-password
```

## How to Run

### Find Prospects
```bash
python prospect-finder.py
# Output: output/prospects.csv, output/prospects.json
```

### Generate Messages
```bash
python outreach-dm.py
# Output: output/outreach_queue.json
```

### Generate Content
```bash
python content-generator.py
# Output: output/content_queue.json
```

### Send Messages
```bash
# Show stats
python send-queue.py --stats

# Send emails only (50 max)
python send-queue.py --type email --max 50

# Send LinkedIn DMs only
python send-queue.py --type linkedin --max 20

# Send both (default)
python send-queue.py --max 50

# Process follow-ups only
python send-queue.py --follow-ups
```

## Architecture

```
prospect-finder.py → prospects.csv
        ↓
outreach-dm.py → outreach_queue.json
        ↓
send-queue.py → sends via SMTP/LinkedIn
        ↓
tracks opens/replies/follow-ups
```

## Rate Limits

- **Email**: 50/hour (conservative to avoid spam flags)
- **LinkedIn**: 20/hour (platform limits)
- **OpenAI**: 20/minute for DM generation, 10/minute for content

## Follow-up Schedule

| Follow-up | Delay |
|-----------|-------|
| 1st | 3 days |
| 2nd | 7 days |
| 3rd | 14 days |
| 4th | 30 days |

## Output Structure

```
output/
├── prospects.csv
├── prospects.json
├── outreach_queue.json
├── content_queue.json
├── sent_log.json
├── prospect-finder.log
├── outreach-dm.log
├── content-generator.log
└── send-queue.log
```
