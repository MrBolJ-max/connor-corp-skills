#!/bin/bash
# 24/7 cron job for Connor Corp operations
# Runs every 2 hours to execute outreach, content posting, and monitoring

# Log file
LOG_FILE="/root/.openclaw/workspace/logs/cron-$(date +%Y%m%d).log"
mkdir -p /root/.openclaw/workspace/logs

echo "[$(date)] Starting Connor Corp automation cycle..." >> $LOG_FILE

# 1. Find new prospects (every 6 hours)
if [ $(($(date +%H) % 6)) -eq 0 ]; then
    echo "[$(date)] Finding new prospects..." >> $LOG_FILE
    cd /root/.openclaw/workspace/projects/connor-corp-skills/automation
    python3 prospect-finder.py --source apollo --industry agency --limit 20 >> $LOG_FILE 2>&1
fi

# 2. Generate outreach messages (every 4 hours)
if [ $(($(date +%H) % 4)) -eq 0 ]; then
    echo "[$(date)] Generating outreach messages..." >> $LOG_FILE
    cd /root/.openclaw/workspace/projects/connor-corp-skills/automation
    python3 outreach-dm.py --prospects data/prospects.csv --campaign daily >> $LOG_FILE 2>&1
fi

# 3. Send messages (every 2 hours)
echo "[$(date)] Sending queued messages..." >> $LOG_FILE
cd /root/.openclaw/workspace/projects/connor-corp-skills/automation
python3 send-queue.py --limit 10 >> $LOG_FILE 2>&1

# 4. Check Stripe for new sales (every hour)
echo "[$(date)] Checking Stripe..." >> $LOG_FILE
# TODO: Integrate with Stripe API to check for new payments

# 5. Update GitHub repo (every 12 hours)
if [ $(($(date +%H) % 12)) -eq 0 ]; then
    echo "[$(date)] Updating GitHub..." >> $LOG_FILE
    cd /root/.openclaw/workspace/projects/connor-corp-skills
    git add . >> $LOG_FILE 2>&1
    git commit -m "auto: $(date +%Y-%m-%d-%H:%M) updates" >> $LOG_FILE 2>&1
    git push origin main >> $LOG_FILE 2>&1
fi

echo "[$(date)] Cycle complete." >> $LOG_FILE
