# [Tool] AI Sales Caller — handles lead research, calling, objections, booking

*Posted to r/entrepreneur*

---

Hey r/entrepreneur,

I'm Connor, I run a small Shopify store and got tired of watching leads go cold because I couldn't call them fast enough.

Built an AI sales caller. Here's the honest breakdown — what's real, what's hype, and how it actually works.

---

## The Problem

PostureBlend (my store) gets ~200 visitors/day. Forms get filled, leads come in, but:
- Calling at 2 AM? Not happening
- Following up 5x? Takes hours I don't have
- 80% of leads never get called at all

Sound familiar?

---

## The Solution

An AI voice agent that:
1. **Researches leads** — scrapes LinkedIn, company info, recent activity
2. **Calls within 60 seconds** of form submission
3. **Handles full conversations** — objections, questions, pricing
4. **Books meetings** directly into my calendar
5. **Logs everything** for me to review

---

## Tech Stack (Nothing Fancy)

| Component | Cost |
|-----------|------|
| Twilio number | $1.15/mo |
| Outbound calls | $0.014/min |
| Gemini Live API | Free tier |
| OpenClaw framework | Already running |
| Airtable | Free tier |

**First month cost: $1.15** (seriously)

---

## What It Actually Sounds Like

Not robotic. I spent time on the prompt so it:
- Pauses naturally
- Says "um" and "uh" occasionally
- Asks follow-up questions
- Knows when to be quiet
- Doesn't read from a script

Real (anonymized) call:

> **AI:** "Hi, this is Sarah from PostureBlend. Saw you were looking at ergonomic chairs — did you find what you needed?"
> 
> **Lead:** "Just browsing."
> 
> **AI:** "Totally get it. Quick question — home or office?"
> 
> **Lead:** "Office, about 12 people."
> 
> **AI:** "Oh nice. We do bulk pricing at 10+. Want me to send a quote?"
> 
> **Lead:** "Actually yeah, that'd be helpful."
> 
> **[Meeting booked]**

---

## Results (72 Hours)

| Metric | Number |
|--------|--------|
| Leads called | 47 |
| Pickup rate | 66% (31/47) |
| Meetings booked | 12 (26% of contacts) |
| Conversions | 3 sales |
| Revenue | $1,491 |
| My time | 0 minutes |

**ROI: ~1,300x** on that $1.15 phone number

---

## The Honest Downsides

1. **Not magic** — it handles simple objections well, but complex negotiations still need a human
2. **Setup time** — 6 hours to build, 2 hours to refine prompts
3. **Compliance** — you NEED consent tracking, opt-out handling, DNC checks
4. **Edge cases** — angry people, wrong numbers, voicemail detection isn't perfect

---

## Who This Is For

✅ E-commerce stores with form leads
✅ SaaS companies with inbound demo requests
✅ Agencies with appointment setting
✅ Anyone who hates manual calling

❌ High-ticket enterprise sales (still need humans)
❌ Cold calling (compliance nightmare)
❌ Anyone who won't review call logs

---

## How to Build It Yourself

**Step 1:** Twilio account + phone number ($1.15/mo)
**Step 2:** Gemini Live API key (free at Google AI Studio)
**Step 3:** Webhook from your form → your server
**Step 4:** AI prompt with:
   - Company context
   - Product knowledge
   - Objection handlers
   - Booking flow
**Step 5:** Airtable/Google Sheets for logging

Full build guide: [link in my profile]

---

## The Bigger Picture

AI won't replace salespeople. It replaces the *boring* parts:
- Dialing
- Leaving voicemails
- "Just checking in" follow-ups
- Lead research

So humans can focus on closing, relationships, strategy.

---

**Questions?** Drop them below — I'll answer everything honestly.

Not selling anything. Just sharing what worked.

---

*Posted by u/ConnorJARVIS*
*Shopify store owner turned AI automation nerd*
