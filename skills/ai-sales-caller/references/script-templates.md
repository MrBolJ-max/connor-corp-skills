# Script Templates — AI Sales Caller

These proven templates are included with the skill and auto-customized by AI based on lead research.

---

## Template 1: SaaS Founder / Decision Maker

**Opening (0-15 seconds):**
> "Hi {{first_name}}, this is {{caller_name}} from {{company}}. I know I'm calling out of the blue — I'll keep this under 30 seconds. We help {{industry}} companies like {{lead_company}} automate their sales outreach. I noticed {{personalization_hook}}. Is now a terrible time?"

**Value Prop (15-45 seconds):**
> "Here's why I'm calling: Our AI agents handle lead research, personalized outreach, and follow-ups — basically everything an SDR does, but 10× faster and without the $6K/month salary. {{lead_company}} could be qualifying {{estimated_leads}} leads per day instead of {{current_volume}}."

**Question (45-60 seconds):**
> "Quick question: Are you currently using any automation for outbound sales, or is your team doing it manually?"

**Close:**
> "Worth a 15-minute conversation next week? I can show you exactly how it'd work for {{lead_company}} specifically. How's Tuesday or Wednesday looking?"

---

## Template 2: Local Service Business

**Opening:**
> "Hi {{first_name}}, this is {{caller_name}} with {{company}}. I'm calling local {{industry}} businesses in {{city}} today — real quick, do you handle your own marketing or do you have someone for that?"

**Value Prop:**
> "Most {{industry}} owners I talk to are great at the work but hate chasing leads. We built an AI system that calls, texts, and emails your prospects automatically — books appointments while you sleep. One client in {{nearby_city}} went from 3 leads a week to 12 in the first month."

**Question:**
> "How are you getting most of your customers right now — referrals, Google, something else?"

**Close:**
> "Mind if I send you a quick video showing how it works? Takes 90 seconds and you'll know if it's worth a conversation. What's the best email for you?"

---

## Template 3: Real Estate Agent / Broker

**Opening:**
> "Hi {{first_name}}, {{caller_name}} here from {{company}}. I'm working with top agents in {{city}} who are using AI to stay in front of buyers and sellers without the manual work. Got 60 seconds?"

**Value Prop:**
> "Here's the deal: Our system automatically calls your expired listings, FSBOs, and past clients — has real conversations, qualifies them, and books appointments straight into your calendar. You show up, they sign. One agent in {{nearby_area}} added 4 listings in 30 days from old contacts she wasn't calling."

**Question:**
> "How many past clients do you have that you haven't spoken to in the last 6 months?"

**Close:**
> "I'll send you a breakdown of how many appointments our agents are booking per week. If the numbers make sense, we talk. If not, no hard feelings. Best email?"

---

## Template 4: E-commerce / Shopify Store Owner

**Opening:**
> "Hi {{first_name}}, this is {{caller_name}} with {{company}}. I help Shopify store owners automate their customer support so they can stop losing sales to slow responses. 30 seconds?"

**Value Prop:**
> "{{lead_company}} probably gets the same 10 questions over and over — shipping times, sizing, returns. Our AI answers them instantly, 24/7, in your brand voice. Plus it upsells and recovers abandoned carts in the same conversation. One store doing $50K/month added $8K in recovered sales in the first month."

**Question:**
> "Are you handling support yourself right now, or do you have a VA or team?"

**Close:**
> "I can set up a demo using your actual store data — you'll see exactly how it'd respond to your customers. Takes 5 minutes. When's a good time this week?"

---

## Template 5: Agency Owner

**Opening:**
> "Hi {{first_name}}, {{caller_name}} from {{company}}. I work with marketing agencies who want to add AI-powered services without hiring a dev team. Quick question — you guys doing any AI automation for clients yet?"

**Value Prop:**
> "Most agencies I talk to are getting asked about AI by every client but don't have a fast way to deliver. We white-label our AI calling and chatbot platform — you sell it, we run it, you keep 60-70% margin. Your clients think you built it."

**Question:**
> "What's your current biggest bottleneck — getting new clients or delivering for existing ones?"

**Close:**
> "Let me send you our partner deck. If the margins work, we can have your first white-label client live in 48 hours. Good email?"

---

## Customization Variables

The AI auto-populates these from lead research:

| Variable | Source |
|----------|--------|
| `{{first_name}}` | Apollo.io / LinkedIn |
| `{{company}}` | Your company (from config.py) |
| `{{lead_company}}` | Lead's company name |
| `{{industry}}` | Apollo industry tag |
| `{{city}}` | Lead location |
| `{{personalization_hook}}` | AI-generated from recent company news, posts, or website |
| `{{estimated_leads}}` | AI-calculated based on company size |
| `{{current_volume}}` | Estimated from job postings, team size, or public data |

---

## Tone Options

Configure in `config.py`:

- `professional` — Polished, consultative, enterprise-friendly
- `casual` — Conversational, friendly, startup-style
- `aggressive` — Fast-paced, assumption-based, high-energy
- `empathetic` — Problem-focused, understanding, consultative

---
Built by Connor Corp
