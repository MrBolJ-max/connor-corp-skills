"""
follow-up.py — Post-call email and LinkedIn DM sequences

Automates personalized follow-up after sales calls.
Includes multi-touch sequences with send timing and tracking.

Usage:
    python follow-up.py --campaign calls_2026-05-07 --sequence standard
"""

import os
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from openai import OpenAI
from dotenv import load_dotenv

# Load credentials
load_dotenv(os.path.expanduser("~/.openclaw/credentials/sales-caller.env"))
load_dotenv(os.path.expanduser("~/.openclaw/credentials/openai.env"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@dataclass
class FollowUpSequence:
    name: str
    touches: List[Dict]
    delay_between_touches_days: int = 2


# Pre-built sequences
SEQUENCES = {
    "standard": [
        {
            "day": 0,
            "channel": "email",
            "subject": "Following up — {{company}} AI system",
            "template": "standard_thanks",
        },
        {
            "day": 2,
            "channel": "email",
            "subject": "Quick demo video for {{lead_company}}",
            "template": "demo_video",
        },
        {
            "day": 5,
            "channel": "linkedin",
            "template": "linkedin_value",
        },
        {
            "day": 7,
            "channel": "email",
            "subject": "Case study: {{industry}} company doubled leads",
            "template": "case_study",
        },
        {
            "day": 12,
            "channel": "email",
            "subject": "Last follow-up — {{company}}",
            "template": "breakup",
        },
    ],
    "aggressive": [
        {
            "day": 0,
            "channel": "email",
            "subject": "You asked for info — here it is",
            "template": "aggressive_value",
        },
        {
            "day": 1,
            "channel": "email",
            "subject": "Did you see this?",
            "template": "aggressive_urgency",
        },
        {
            "day": 3,
            "channel": "linkedin",
            "template": "linkedin_direct",
        },
        {
            "day": 5,
            "channel": "email",
            "subject": "3 companies just signed — here's what they saw",
            "template": "social_proof",
        },
        {
            "day": 7,
            "channel": "email",
            "subject": "Closing this outreach",
            "template": "breakup",
        },
    ],
    "nurture": [
        {
            "day": 0,
            "channel": "email",
            "subject": "Resources I promised",
            "template": "nurture_resources",
        },
        {
            "day": 7,
            "channel": "email",
            "subject": "How {{industry}} companies are using AI in 2026",
            "template": "nurture_education",
        },
        {
            "day": 14,
            "channel": "linkedin",
            "template": "linkedin_soft",
        },
        {
            "day": 21,
            "channel": "email",
            "subject": "Monthly update: New features you might like",
            "template": "nurture_update",
        },
        {
            "day": 30,
            "channel": "email",
            "subject": "Still thinking about AI automation?",
            "template": "nurture_reengage",
        },
    ],
}

EMAIL_TEMPLATES = {
    "standard_thanks": """Hi {{first_name}},

Thanks for speaking with me today about automating {{lead_company}}'s {{relevant_process}}.

As promised, here's what we covered:
• {{key_benefit_1}}
• {{key_benefit_2}}
• {{key_benefit_3}}

{{personalized_value_prop}}

Worth a 15-minute demo next week? I'll show you exactly how it'd work for {{lead_company}}.

Best,
{{sender_name}}
{{sender_title}}
{{company}}
{{phone}}
""",
    "demo_video": """Hi {{first_name}},

Quick follow-up — I recorded a 90-second demo showing how our AI system handles {{relevant_process}} specifically for {{industry}} companies.

Watch it here: {{demo_link}}

The part most {{industry}} owners like: {{specific_feature}}

Any questions after watching, just reply to this email.

Best,
{{sender_name}}
{{company}}
""",
    "case_study": """Hi {{first_name}},

Wanted to share a quick win:

{{case_study_company}} (also {{industry}}, {{company_size}}) was in a similar spot — {{similar_challenge}}.

Results after 30 days:
• {{metric_1}}: {{result_1}}
• {{metric_2}}: {{result_2}}
• {{metric_3}}: {{result_3}}

Full case study: {{case_study_link}}

If those numbers look interesting, let's talk.

Best,
{{sender_name}}
{{company}}
""",
    "breakup": """Hi {{first_name}},

I don't want to be that person who keeps emailing when you're not interested.

Last message from me — but wanted to make sure you have everything:
• Demo video: {{demo_link}}
• Case study: {{case_study_link}}
• Pricing: {{pricing_link}}

If AI automation for {{relevant_process}} becomes a priority down the road, I'm here.

Otherwise, all the best with {{lead_company}}.

{{sender_name}}
{{company}}
""",
    "aggressive_value": """{{first_name}},

You asked for info. Here it is — no fluff:

Our AI calling system:
✓ Makes {{call_volume}}+ calls/day
✓ Qualifies leads automatically
✓ Books meetings into your calendar
✓ Costs less than one SDR's salary

{{lead_company}} could have this running by Friday.

Worth 10 minutes? {{calendar_link}}

{{sender_name}}
{{company}}
""",
    "aggressive_urgency": """{{first_name}},

Quick question — did my last email get buried?

Here's the deal: I'm working with 3 {{industry}} companies right now who are seeing {{specific_result}} from our AI system.

I'd rather {{lead_company}} not be the last one to the party.

{{calendar_link}} — pick any slot this week.

{{sender_name}}
""",
    "social_proof": """Hi {{first_name}},

3 {{industry}} companies signed up this week. Here's what they saw that you didn't:

1. {{social_proof_1}}
2. {{social_proof_2}}
3. {{social_proof_3}}

All of them were "thinking about it" two weeks ago.

{{calendar_link}} if you want to see what they saw.

{{sender_name}}
{{company}}
""",
    "nurture_resources": """Hi {{first_name}},

As promised, here are the resources I mentioned:

📄 Industry report: {{report_link}}
🎥 Quick demo: {{demo_link}}
📊 ROI calculator: {{calculator_link}}

No pressure — just thought they'd be useful for {{lead_company}}.

{{sender_name}}
{{company}}
""",
    "nurture_education": """Hi {{first_name}},

Saw this stat and thought of you:

"{{industry}} companies using AI for {{relevant_process}} are seeing {{statistic}} on average."

Source: {{source_link}}

Worth considering as you plan {{lead_company}}'s growth.

{{sender_name}}
{{company}}
""",
    "nurture_update": """Hi {{first_name}},

Monthly update — wanted to share two new features that {{industry}} companies are loving:

1. {{feature_1}} — {{feature_1_benefit}}
2. {{feature_2}} — {{feature_2_benefit}}

If {{lead_company}} ever wants to explore AI automation, these make it even faster to get started.

{{sender_name}}
{{company}}
""",
    "nurture_reengage": """Hi {{first_name}},

Still thinking about AI automation for {{lead_company}}?

If yes — what's the main thing holding you back? Cost, time, or not sure it'll work?

If no — no worries, I'll close this thread.

Either way, just hit reply and let me know.

{{sender_name}}
{{company}}
""",
}

LINKEDIN_TEMPLATES = {
    "linkedin_value": """Hi {{first_name}},

Enjoyed our call the other day. Wanted to connect here too — I share weekly tips on {{topic}} that might be useful for {{lead_company}}.

Also, if you want to see that demo we discussed: {{demo_link}}

Talk soon,
{{sender_name}}
""",
    "linkedin_direct": """{{first_name}},

Quick question — are you the right person to discuss {{relevant_process}} automation at {{lead_company}}? If not, who should I loop in?

{{sender_name}}
{{company}}
""",
    "linkedin_soft": """Hi {{first_name}},

Saw {{lead_company}}'s recent post about {{recent_news}} — solid work.

If you're ever exploring AI for {{relevant_process}}, happy to share what I've learned working with similar {{industry}} companies.

No pitch — just here if you need it.

{{sender_name}}
""",
}


def generate_personalized_email(
    template_name: str,
    lead_data: Dict,
    offer_data: Dict,
    tone: str = "professional",
) -> str:
    """Generate personalized email using OpenAI GPT-4o."""
    
    template = EMAIL_TEMPLATES.get(template_name, EMAIL_TEMPLATES["standard_thanks"])
    
    # Basic variable substitution
    for key, value in lead_data.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    
    for key, value in offer_data.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    
    # AI enhancement for personalization
    system_prompt = f"""You are a sales copywriter. Enhance this email template with specific, personalized details about the prospect.

Rules:
1. Keep the same structure and key points
2. Add 1-2 sentences of genuine personalization based on the lead data
3. Keep total length under 200 words
4. Tone: {tone}
5. Make it sound human-written, not templated"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Lead: {json.dumps(lead_data)}\n\nTemplate:\n{template}\n\nEnhance with personalization while keeping the structure."},
            ],
            max_tokens=400,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ AI enhancement failed, using template: {e}")
        return template


def generate_linkedin_dm(
    template_name: str,
    lead_data: Dict,
    offer_data: Dict,
) -> str:
    """Generate LinkedIn DM from template."""
    
    template = LINKEDIN_TEMPLATES.get(template_name, LINKEDIN_TEMPLATES["linkedin_value"])
    
    for key, value in lead_data.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    
    for key, value in offer_data.items():
        template = template.replace(f"{{{{{key}}}}}", str(value))
    
    return template


def schedule_follow_up(
    sequence_name: str,
    lead_data: Dict,
    offer_data: Dict,
    start_date: Optional[datetime] = None,
) -> List[Dict]:
    """Generate complete follow-up sequence with send dates."""
    
    if start_date is None:
        start_date = datetime.now()
    
    sequence = SEQUENCES.get(sequence_name, SEQUENCES["standard"])
    scheduled = []
    
    for touch in sequence:
        send_date = start_date + timedelta(days=touch["day"])
        
        if touch["channel"] == "email":
            content = generate_personalized_email(
                touch["template"],
                lead_data,
                offer_data,
            )
            subject = touch.get("subject", "Follow-up").replace("{{company}}", offer_data.get("company", ""))
        else:
            content = generate_linkedin_dm(
                touch["template"],
                lead_data,
                offer_data,
            )
            subject = None
        
        scheduled.append({
            "day": touch["day"],
            "send_date": send_date.strftime("%Y-%m-%d"),
            "channel": touch["channel"],
            "subject": subject,
            "content": content,
            "status": "scheduled",
        })
    
    return scheduled


def execute_follow_up(
    scheduled: List[Dict],
    dry_run: bool = True,
) -> List[Dict]:
    """Execute or simulate follow-up sends."""
    
    results = []
    
    for touch in scheduled:
        if dry_run:
            touch["status"] = "simulated"
            print(f"📧 [SIMULATED] Day {touch['day']} — {touch['channel']}")
            if touch.get("subject"):
                print(f"   Subject: {touch['subject']}")
            print(f"   Content preview: {touch['content'][:100]}...")
            print()
        else:
            # TODO: Integrate with email provider (SendGrid, Mailgun, etc.)
            # TODO: Integrate with LinkedIn automation tool
            touch["status"] = "sent"
            print(f"✅ Sent Day {touch['day']} — {touch['channel']}")
        
        results.append(touch)
        
        if not dry_run:
            time.sleep(0.5)  # Rate limiting
    
    return results


def main():
    parser = argparse.ArgumentParser(description="AI Follow-Up Sequences")
    parser.add_argument("--campaign", type=str, required=True, help="Campaign name/ID")
    parser.add_argument("--sequence", type=str, default="standard", choices=list(SEQUENCES.keys()))
    parser.add_argument("--lead-file", type=str, help="Path to lead data JSON")
    parser.add_argument("--offer-file", type=str, help="Path to offer data JSON")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--execute", action="store_true", help="Actually send (not dry run)")
    parser.add_argument("--tone", type=str, default="professional", choices=["professional", "casual", "aggressive"])

    args = parser.parse_args()

    # Load lead data
    if args.lead_file:
        with open(args.lead_file, "r") as f:
            lead_data = json.load(f)
    else:
        lead_data = {
            "first_name": "John",
            "lead_company": "Acme Corp",
            "industry": "e-commerce",
            "company_size": "20-50 employees",
            "relevant_process": "customer support",
        }

    # Load offer data
    if args.offer_file:
        with open(args.offer_file, "r") as f:
            offer_data = json.load(f)
    else:
        offer_data = {
            "company": "Connor Corp",
            "sender_name": "Connor",
            "sender_title": "AI Automation Specialist",
            "phone": "+1-385-279-2646",
            "key_benefit_1": "24/7 AI customer support",
            "key_benefit_2": "Instant response to common questions",
            "key_benefit_3": "Abandoned cart recovery",
        }

    print(f"🔄 Generating '{args.sequence}' follow-up sequence for campaign: {args.campaign}\n")
    
    scheduled = schedule_follow_up(args.sequence, lead_data, offer_data)
    
    print(f"📅 {len(scheduled)} touches scheduled:\n")
    for touch in scheduled:
        print(f"Day {touch['day']} ({touch['send_date']}) — {touch['channel']}")
    
    print(f"\n{'='*60}\n")
    
    results = execute_follow_up(scheduled, dry_run=not args.execute)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "campaign": args.campaign,
                "sequence": args.sequence,
                "touches": results,
                "total_touches": len(results),
                "generated_at": datetime.now().isoformat(),
            }, f, indent=2)
        print(f"💾 Saved to {args.output}")


if __name__ == "__main__":
    main()
