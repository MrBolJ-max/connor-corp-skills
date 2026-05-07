"""
book-meetings.py — Calendar integration for AI sales calls

Automatically books meetings via Cal.com or Calendly API after a successful call.
Handles timezone conversion, availability checking, and confirmation emails.

Usage:
    python book-meetings.py --lead "John Doe" --email "john@example.com" --duration 30
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

# Load credentials
load_dotenv(os.path.expanduser("~/.openclaw/credentials/sales-caller.env"))


@dataclass
class MeetingRequest:
    lead_name: str
    lead_email: str
    lead_phone: str = ""
    duration_minutes: int = 30
    preferred_times: List[str] = None
    timezone: str = "America/New_York"
    notes: str = ""
    calendar_type: str = "calcom"  # calcom or calendly


class Calendar Booker:
    def __init__(self):
        self.calcom_api_key = os.getenv("CALCOM_API_KEY")
        self.calendly_api_key = os.getenv("CALENDLY_API_KEY")
        self.calcom_base_url = "https://api.cal.com/v1"
        self.calendly_base_url = "https://api.calendly.com/v2"
    
    def _get_headers(self, calendar_type: str) -> Dict:
        if calendar_type == "calcom":
            return {
                "Authorization": f"Bearer {self.calcom_api_key}",
                "Content-Type": "application/json",
            }
        else:
            return {
                "Authorization": f"Bearer {self.calendly_api_key}",
                "Content-Type": "application/json",
            }
    
    def check_availability_calcom(
        self,
        event_type_id: str,
        date_from: str,
        date_to: str,
        timezone: str = "UTC",
    ) -> List[Dict]:
        """Check available slots via Cal.com API."""
        url = f"{self.calcom_base_url}/slots"
        params = {
            "eventTypeId": event_type_id,
            "startTime": date_from,
            "endTime": date_to,
            "timeZone": timezone,
        }
        
        try:
            response = requests.get(url, headers=self._get_headers("calcom"), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("slots", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Cal.com availability error: {e}")
            return []
    
    def check_availability_calendly(
        self,
        event_type_uri: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict]:
        """Check available slots via Calendly API."""
        url = f"{self.calendly_base_url}/event_type_available_times"
        params = {
            "event_type": event_type_uri,
            "start_time": start_date,
            "end_time": end_date,
        }
        
        try:
            response = requests.get(url, headers=self._get_headers("calendly"), params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("collection", [])
        except requests.exceptions.RequestException as e:
            print(f"❌ Calendly availability error: {e}")
            return []
    
    def book_calcom(
        self,
        event_type_id: str,
        start_time: str,
        name: str,
        email: str,
        notes: str = "",
        timezone: str = "UTC",
    ) -> Optional[Dict]:
        """Book a meeting via Cal.com."""
        url = f"{self.calcom_base_url}/bookings"
        payload = {
            "eventTypeId": int(event_type_id),
            "start": start_time,
            "responses": {
                "name": name,
                "email": email,
                "notes": notes,
            },
            "timeZone": timezone,
            "language": "en",
        }
        
        try:
            response = requests.post(url, headers=self._get_headers("calcom"), json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Cal.com booking error: {e}")
            return None
    
    def book_calendly(
        self,
        event_type_uri: str,
        invitee_email: str,
        invitee_name: str,
        start_time: str,
        timezone: str = "UTC",
    ) -> Optional[Dict]:
        """Book a meeting via Calendly API."""
        url = f"{self.calendly_base_url}/scheduled_events"
        payload = {
            "event_type": event_type_uri,
            "invitee": {
                "email": invitee_email,
                "name": invitee_name,
                "timezone": timezone,
            },
            "start_time": start_time,
        }
        
        try:
            response = requests.post(url, headers=self._get_headers("calendly"), json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Calendly booking error: {e}")
            return None
    
    def find_next_available_slot(
        self,
        calendar_type: str,
        event_id: str,
        days_ahead: int = 7,
        timezone: str = "UTC",
    ) -> Optional[str]:
        """Find the next available meeting slot."""
        today = datetime.now()
        date_from = today.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        date_to = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        if calendar_type == "calcom":
            slots = self.check_availability_calcom(event_id, date_from, date_to, timezone)
            if slots:
                # Get first available slot
                for day_slots in slots.values():
                    if day_slots:
                        return day_slots[0].get("time")
        else:
            slots = self.check_availability_calendly(event_id, date_from, date_to)
            if slots:
                return slots[0].get("scheduling_url")
        
        return None
    
    def book_meeting(self, request: MeetingRequest, event_id: str) -> Dict:
        """Main booking flow."""
        print(f"📅 Booking meeting for {request.lead_name} ({request.lead_email})")
        
        # Find next available slot
        slot = self.find_next_available_slot(
            request.calendar_type,
            event_id,
            timezone=request.timezone,
        )
        
        if not slot:
            return {
                "success": False,
                "error": "No available slots found",
                "lead": request.lead_name,
            }
        
        # Book the meeting
        if request.calendar_type == "calcom":
            result = self.book_calcom(
                event_id,
                slot,
                request.lead_name,
                request.lead_email,
                request.notes,
                request.timezone,
            )
        else:
            result = self.book_calendly(
                event_id,
                request.lead_email,
                request.lead_name,
                slot,
                request.timezone,
            )
        
        if result:
            return {
                "success": True,
                "booking": result,
                "lead": request.lead_name,
                "email": request.lead_email,
                "scheduled_time": slot,
                "calendar": request.calendar_type,
            }
        else:
            return {
                "success": False,
                "error": "Booking failed",
                "lead": request.lead_name,
            }


def generate_booking_email(meeting_result: Dict, company_name: str = "") -> str:
    """Generate confirmation email text."""
    if not meeting_result.get("success"):
        return f"""Subject: Following up on our call

Hi {meeting_result.get('lead', 'there')},

Thanks for speaking with me today. I tried to book a time on your calendar but couldn't find an available slot.

Could you send me a few times that work for you next week? I'll make it work.

Best,
{company_name or "Our team"}
"""
    
    return f"""Subject: Meeting confirmed — {meeting_result.get('scheduled_time', 'TBD')}

Hi {meeting_result.get('lead', 'there')},

Great speaking with you today!

Your meeting is confirmed for {meeting_result.get('scheduled_time', 'TBD')}.

Here's what we'll cover:
• How our AI system works for your specific business
• ROI breakdown based on your current volume
• Live demo with your actual use case
• Q&A — bring any questions

Calendar invite attached. Talk soon!

Best,
{company_name or "Our team"}
"""


def main():
    parser = argparse.ArgumentParser(description="AI Meeting Booker")
    parser.add_argument("--lead", type=str, required=True, help="Lead name")
    parser.add_argument("--email", type=str, required=True, help="Lead email")
    parser.add_argument("--phone", type=str, default="", help="Lead phone")
    parser.add_argument("--duration", type=int, default=30, help="Meeting duration in minutes")
    parser.add_argument("--event-id", type=str, required=True, help="Calendar event type ID/URI")
    parser.add_argument("--calendar", type=str, default="calcom", choices=["calcom", "calendly"])
    parser.add_argument("--timezone", type=str, default="America/New_York", help="Lead timezone")
    parser.add_argument("--notes", type=str, default="", help="Meeting notes/context")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--company", type=str, default="", help="Your company name")

    args = parser.parse_args()

    request = MeetingRequest(
        lead_name=args.lead,
        lead_email=args.email,
        lead_phone=args.phone,
        duration_minutes=args.duration,
        timezone=args.timezone,
        notes=args.notes,
        calendar_type=args.calendar,
    )

    booker = Calendar Booker()
    result = booker.book_meeting(request, args.event_id)
    
    # Generate confirmation email
    result["confirmation_email"] = generate_booking_email(result, args.company)
    
    print(json.dumps(result, indent=2))
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved to {args.output}")


if __name__ == "__main__":
    main()
