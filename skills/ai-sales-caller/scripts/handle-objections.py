"""
handle-objections.py — Real-time objection handling for AI sales calls

Matches common objection patterns and generates AI-powered responses
using OpenAI GPT-4o. Includes confidence scoring and escalation triggers.

Usage:
    python handle-objections.py --input call_transcript.txt --confidence 0.8
"""

import os
import re
import json
import argparse
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from openai import OpenAI
from dotenv import load_dotenv

# Load credentials
load_dotenv(os.path.expanduser("~/.openclaw/credentials/sales-caller.env"))
load_dotenv(os.path.expanduser("~/.openclaw/credentials/openai.env"))

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@dataclass
class ObjectionMatch:
    objection_type: str
    pattern: str
    confidence: float
    suggested_response: str
    escalation_needed: bool


# Pre-built objection patterns from the objection handbook
OBJECTION_PATTERNS: Dict[str, List[str]] = {
    "price": [
        r"too expensive", r"can't afford", r"high price", r"costs too much",
        r"overpriced", r"out of our budget", r"pricing is high",
        r"can't justify the cost", r"cheaper alternative",
    ],
    "budget": [
        r"no budget", r"budget('s| is) tight", r"cutting costs",
        r"no money for this", r"financial constraints",
    ],
    "timing": [
        r"not (right |a good )?time", r"bad timing", r"busy season",
        r"next quarter", r"call me (back |next )(month|week)",
        r"too busy right now", r"in the middle of",
    ],
    "authority": [
        r"not my (call|decision)", r"need to (ask|check with|talk to)",
        r"not in charge", r"have to run it by",
        r"I'm not the (decision maker|one who decides)",
    ],
    "product": [
        r"already (have|use|using)", r"we have a system",
        r"tried (AI|this|something similar) before",
        r"doesn't work for us", r"not interested in (changing|switching)",
    ],
    "brush_off": [
        r"send me (an )?email", r"not interested", r"don't need this",
        r"remove me from", r"take me off your list",
        r"I get calls like this all the time", r"just email me",
    ],
    "trust": [
        r"how do I know this works", r"sounds too good to be true",
        r"never heard of", r"don't trust", r"prove it",
        r"what guarantee", r"money back",
    ],
    "technical": [
        r"don't have (the |a )?tech team", r"no developer",
        r"sounds complicated", r"too complex", r"hard to implement",
    ],
}

# Context-aware response templates
RESPONSE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "price": {
        "consultative": "I hear that. What are you currently spending on this function? Most of our clients find this replaces $5-8K/month in payroll while doing 3× the output.",
        "aggressive": "Expensive compared to what? A human SDR costs $6K/month plus benefits. This costs less than one day's salary and works 24/7. Do the math.",
        "casual": "Yeah, I get it — price matters. But here's the thing: most people who say it's expensive haven't calculated what they're losing by NOT having it. Want to see the ROI breakdown?",
    },
    "budget": {
        "consultative": "Totally understand. What's your current monthly spend on lead generation? Most clients find this saves money within 30 days.",
        "aggressive": "Budgets are tight everywhere. But smart companies invest in tools that generate revenue, not just cut costs. Which bucket does lead generation fall in for you?",
        "casual": "I feel you — been there. The companies that make it work during tight budgets are the ones that invest in automation. Want to see how others did it?",
    },
    "timing": {
        "consultative": "Fair enough — when would be the right time? I'll check back then, or send you a quick video now so you have all the info when you're ready.",
        "aggressive": "Most people who say 'not now' end up wishing they'd started 3 months earlier. What's really changing between now and next month?",
        "casual": "No worries — timing's everything. Mind if I shoot you a quick demo video? 90 seconds, no pressure, and you'll know if it's worth exploring later.",
    },
    "authority": {
        "consultative": "Makes sense — who would be the right person to loop in? I can send you both the info so you're aligned when you discuss it.",
        "aggressive": "Sure — but while we're talking, what's their main concern usually? Cost, results, or implementation time? I want to make sure I send the right info.",
        "casual": "No problem — happens all the time. Want me to send a one-pager you can forward? Makes the conversation easier when you bring it up.",
    },
    "product": {
        "consultative": "Nice — [competitor] is solid. What I'm hearing from switchers is [specific pain point]. Is that something you run into?",
        "aggressive": "If what you have is perfect, you wouldn't still be talking to me. What's the one thing you'd change about your current setup?",
        "casual": "Cool — what do you like about it? And is there anything you wish it did that it doesn't?",
    },
    "brush_off": {
        "consultative": "I will — but honestly, 80% of emails get buried. This is 2 minutes and you'll know if it's worth exploring. What do you look for in a solution like this?",
        "aggressive": "You get 10 calls a day. I get it. But I only call businesses I genuinely think I can help. What's your current process for [relevant function]?",
        "casual": "Totally fair — I hate cold calls too. Before I go, real quick: are you actually happy with your current [metric], or is there room to improve?",
    },
    "trust": {
        "consultative": "Smart question. Here's what I'd do: [case study]. They're now [result]. Want their contact info to verify?",
        "aggressive": "It does sound too good to be true — and it won't work for everyone. But if you have a solid offer and just need more conversations, the data is consistent. Want to see it?",
        "casual": "I get it — skepticism is healthy. Check out [case study link]. If those results don't convince you, nothing will.",
    },
    "technical": {
        "consultative": "That's the best part — we handle all implementation. No dev team needed. Usually live in 48 hours, and we do the setup.",
        "aggressive": "It's complicated on our end. For you, it's dead simple. [One sentence]. That's it. Want a 5-minute walkthrough?",
        "casual": "Zero tech skills needed — we literally do everything. You just watch the appointments roll in. Want me to show you how easy it is?",
    },
}


def match_objection(text: str, confidence_threshold: float = 0.7) -> Optional[ObjectionMatch]:
    """Match objection patterns in transcript text."""
    text_lower = text.lower()
    best_match = None
    highest_confidence = 0.0

    for obj_type, patterns in OBJECTION_PATTERNS.items():
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower))
            if matches > 0:
                confidence = min(0.5 + (matches * 0.25), 1.0)
                if confidence > highest_confidence and confidence >= confidence_threshold:
                    highest_confidence = confidence
                    best_match = ObjectionMatch(
                        objection_type=obj_type,
                        pattern=pattern,
                        confidence=confidence,
                        suggested_response="",
                        escalation_needed=confidence < 0.85,
                    )

    return best_match


def generate_ai_response(
    objection_type: str,
    transcript_context: str,
    tone: str = "consultative",
    offer_description: str = "",
    company_name: str = "",
) -> str:
    """Generate AI-powered response using GPT-4o."""
    
    system_prompt = f"""You are an expert sales objection handler. 
You work for {company_name} selling: {offer_description}

Your tone is: {tone}
- consultative = helpful, understanding, asks questions
- aggressive = direct, challenges assumptions, pushes back gently
- casual = friendly, conversational, low pressure

Rules:
1. Keep responses under 40 words spoken (about 15 seconds)
2. Always pivot to a question or next step
3. Never argue — acknowledge and redirect
4. Use the prospect's words when possible
5. End with a soft close or question

Objection type: {objection_type}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Prospect said: '{transcript_context}'\n\nGenerate a response that handles this objection and moves toward booking a meeting or sending more info."},
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=120,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        # Fallback to template
        templates = RESPONSE_TEMPLATES.get(objection_type, {})
        return templates.get(tone, templates.get("consultative", "I understand. Let me send you some information to review at your convenience."))


def handle_objection(
    transcript_text: str,
    tone: str = "consultative",
    confidence_threshold: float = 0.7,
    use_ai: bool = True,
    offer_description: str = "",
    company_name: str = "",
) -> Dict:
    """Main handler — detect objection and generate response."""
    
    match = match_objection(transcript_text, confidence_threshold)
    
    if not match:
        return {
            "objection_detected": False,
            "response": None,
            "confidence": 0.0,
            "escalation_needed": False,
        }

    if use_ai:
        response = generate_ai_response(
            match.objection_type,
            transcript_text,
            tone,
            offer_description,
            company_name,
        )
    else:
        templates = RESPONSE_TEMPLATES.get(match.objection_type, {})
        response = templates.get(tone, templates.get("consultative", "I understand. Let me send you more information."))

    return {
        "objection_detected": True,
        "objection_type": match.objection_type,
        "confidence": match.confidence,
        "pattern_matched": match.pattern,
        "response": response,
        "escalation_needed": match.escalation_needed,
        "tone": tone,
    }


def batch_process_transcripts(
    transcripts: List[str],
    tone: str = "consultative",
    confidence_threshold: float = 0.7,
) -> List[Dict]:
    """Process multiple transcripts and generate reports."""
    results = []
    
    for i, transcript in enumerate(transcripts):
        result = handle_objection(transcript, tone, confidence_threshold)
        result["transcript_id"] = i
        results.append(result)
    
    return results


def generate_analytics_report(results: List[Dict]) -> Dict:
    """Generate analytics from objection handling results."""
    total = len(results)
    objections_found = [r for r in results if r.get("objection_detected")]
    escalations = [r for r in objections_found if r.get("escalation_needed")]
    
    type_breakdown = {}
    for r in objections_found:
        obj_type = r.get("objection_type", "unknown")
        type_breakdown[obj_type] = type_breakdown.get(obj_type, 0) + 1

    avg_confidence = sum(r.get("confidence", 0) for r in objections_found) / len(objections_found) if objections_found else 0

    return {
        "total_transcripts": total,
        "objections_detected": len(objections_found),
        "detection_rate": f"{len(objections_found) / total * 100:.1f}%" if total > 0 else "0%",
        "avg_confidence": f"{avg_confidence:.2f}",
        "escalations_needed": len(escalations),
        "escalation_rate": f"{len(escalations) / len(objections_found) * 100:.1f}%" if objections_found else "0%",
        "objection_types": type_breakdown,
    }


def main():
    parser = argparse.ArgumentParser(description="AI Sales Objection Handler")
    parser.add_argument("--input", type=str, help="Path to transcript file or text")
    parser.add_argument("--tone", type=str, default="consultative", choices=["consultative", "aggressive", "casual"])
    parser.add_argument("--confidence", type=float, default=0.7, help="Confidence threshold (0.0-1.0)")
    parser.add_argument("--batch", type=str, help="Path to JSON file with multiple transcripts")
    parser.add_argument("--company", type=str, default="", help="Your company name")
    parser.add_argument("--offer", type=str, default="", help="What you're selling")
    parser.add_argument("--no-ai", action="store_true", help="Use template responses instead of AI generation")
    parser.add_argument("--analytics", action="store_true", help="Generate analytics report")

    args = parser.parse_args()

    if args.batch:
        with open(args.batch, "r") as f:
            data = json.load(f)
            transcripts = data if isinstance(data, list) else data.get("transcripts", [])
        
        results = batch_process_transcripts(transcripts, args.tone, args.confidence)
        
        if args.analytics:
            report = generate_analytics_report(results)
            print(json.dumps(report, indent=2))
        else:
            for result in results:
                print(json.dumps(result, indent=2))
                print("-" * 50)
    
    elif args.input:
        if os.path.isfile(args.input):
            with open(args.input, "r") as f:
                text = f.read()
        else:
            text = args.input
        
        result = handle_objection(
            text,
            args.tone,
            args.confidence,
            not args.no_ai,
            args.offer,
            args.company,
        )
        print(json.dumps(result, indent=2))
    
    else:
        # Demo mode
        demo_transcripts = [
            "That sounds really expensive. We're already spending a lot on marketing.",
            "Not right now, we're in the middle of a big project.",
            "I need to talk to my partner about this before making any decisions.",
            "We already have a system that handles this. It's working fine.",
            "Just send me an email with the details. I'll review it later.",
        ]
        
        print("🎯 Running demo with 5 common objections:\n")
        for transcript in demo_transcripts:
            result = handle_objection(transcript, args.tone, args.confidence, not args.no_ai, args.offer, args.company)
            print(f"Prospect: \"{transcript}\"")
            print(f"Detected: {result['objection_type']} ({result['confidence']:.0%} confidence)")
            print(f"Response: \"{result['response']}\"")
            print(f"Escalate: {'Yes' if result['escalation_needed'] else 'No'}")
            print("-" * 70)


if __name__ == "__main__":
    main()
