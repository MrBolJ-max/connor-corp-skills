#!/usr/bin/env python3
"""
AI Sales Caller - Make Calls
Handles outbound calls via Twilio + OpenAI Realtime Voice API
"""
import os
import sys
import json
import time
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import queue
import threading

# Third-party imports
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
import websockets
import aiohttp

# Load credentials from env files
def load_env_file(filepath: str) -> dict:
    """Load key=value pairs from env file."""
    result = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    result[key] = val
    return result

openai_creds = load_env_file(os.path.expanduser('~/.openclaw/credentials/openai.env'))
twilio_creds = load_env_file(os.path.expanduser('~/.openclaw/credentials/twilio.env'))

OPENAI_API_KEY = openai_creds.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
TWILIO_ACCOUNT_SID = twilio_creds.get('TWILIO_ACCOUNT_SID', os.getenv('TWILIO_ACCOUNT_SID'))
TWILIO_AUTH_TOKEN = twilio_creds.get('TWILIO_AUTH_TOKEN', os.getenv('TWILIO_AUTH_TOKEN'))
TWILIO_PHONE_NUMBER = twilio_creds.get('TWILIO_PHONE_NUMBER', os.getenv('TWILIO_PHONE_NUMBER'))

# Paths
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / 'logs'
RECORDINGS_DIR = BASE_DIR / 'recordings'
CALLS_DB_PATH = BASE_DIR / 'data' / 'calls.jsonl'

LOGS_DIR.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
CALLS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / f'calls_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('make-calls')


class CallOutcome(Enum):
    """Possible outcomes of a sales call."""
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    HANGUP = "hangup"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    MEETING_BOOKED = "meeting_booked"
    FOLLOW_UP_REQUIRED = "follow_up_required"
    CALLBACK_REQUESTED = "callback_requested"
    GATEKEEPER_BLOCKED = "gatekeeper_blocked"
    DNC = "do_not_call"
    ERROR = "error"


class CallStage(Enum):
    """Stages of a call lifecycle."""
    PENDING = "pending"
    DIALING = "dialing"
    CONNECTED = "connected"
    SPEAKING = "speaking"
    HOLDING = "holding"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Prospect:
    """Represents a person to call."""
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    title: Optional[str] = None
    notes: str = ""
    timezone: str = "America/New_York"
    best_time_to_call: Optional[str] = None  # e.g., "9-11 AM"
    last_called: Optional[str] = None
    call_count: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class CallResult:
    """Result of a single call attempt."""
    call_sid: str
    prospect_id: str
    status: str
    outcome: CallOutcome
    duration_seconds: int = 0
    recording_url: Optional[str] = None
    transcript: str = ""
    summary: str = ""
    next_action: Optional[str] = None
    booked_meeting: Optional[Dict] = None
    follow_up_date: Optional[str] = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RateLimit:
    """Rate limit configuration."""
    calls_per_minute: int = 10
    calls_per_hour: int = 60
    calls_per_day: int = 200
    concurrent_calls: int = 3


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, config: RateLimit):
        self.config = config
        self.minute_lock = threading.Lock()
        self.hour_lock = threading.Lock()
        self.day_lock = threading.Lock()
        self.concurrent_lock = threading.Lock()
        
        self.minute_calls: queue.Queue = queue.Queue()
        self.hour_calls: queue.Queue = queue.Queue()
        self.day_calls: queue.Queue = queue.Queue()
        self.active_calls: int = 0
    
    def _clean_old(self, q: queue.Queue, seconds: int):
        """Remove timestamps older than given seconds."""
        now = time.time()
        cleaned = []
        while not q.empty():
            try:
                ts = q.get_nowait()
                if now - ts < seconds:
                    cleaned.append(ts)
            except queue.Empty:
                break
        for ts in cleaned:
            q.put(ts)
    
    def can_call(self) -> bool:
        """Check if a call can be made under current rate limits."""
        with self.minute_lock:
            self._clean_old(self.minute_calls, 60)
            if self.minute_calls.qsize() >= self.config.calls_per_minute:
                return False
        
        with self.hour_lock:
            self._clean_old(self.hour_calls, 3600)
            if self.hour_calls.qsize() >= self.config.calls_per_hour:
                return False
        
        with self.day_lock:
            self._clean_old(self.day_calls, 86400)
            if self.day_calls.qsize() >= self.config.calls_per_day:
                return False
        
        with self.concurrent_lock:
            if self.active_calls >= self.config.concurrent_calls:
                return False
        
        return True
    
    def record_call(self):
        """Record that a call was initiated."""
        ts = time.time()
        with self.minute_lock:
            self.minute_calls.put(ts)
        with self.hour_lock:
            self.hour_calls.put(ts)
        with self.day_lock:
            self.day_calls.put(ts)
        with self.concurrent_lock:
            self.active_calls += 1
    
    def release_call(self):
        """Release a concurrent call slot."""
        with self.concurrent_lock:
            self.active_calls = max(0, self.active_calls - 1)
    
    def wait_time(self) -> float:
        """Calculate seconds until next call slot available."""
        with self.minute_lock:
            self._clean_old(self.minute_calls, 60)
            if self.minute_calls.qsize() >= self.config.calls_per_minute:
                # Wait until oldest call is 60 seconds old
                oldest = None
                temp = []
                while not self.minute_calls.empty():
                    try:
                        ts = self.minute_calls.get_nowait()
                        if oldest is None or ts < oldest:
                            oldest = ts
                        temp.append(ts)
                    except queue.Empty:
                        break
                for ts in temp:
                    self.minute_calls.put(ts)
                if oldest:
                    return 60 - (time.time() - oldest)
        return 0.0


class VoicemailDetector:
    """Detects voicemail beeps and automated systems."""
    
    PATTERNS = [
        r"voicemail",
        r"leave a message",
        r"after the tone",
        r"beep",
        r"tone.*record",
        r"not available",
        r"not reach",
        r"unable to take",
        r"mailbox.*full",
        r"automated",
        r"press \d",
        r"extension",
        r"dial \d",
        r"menu",
        r"custom.*service",
    ]
    
    def __init__(self):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.PATTERNS]
        self.confidence = 0.0
        self.detected = False
    
    def analyze(self, text: str) -> float:
        """Analyze transcript text for voicemail indicators. Returns 0-1 confidence."""
        matches = sum(1 for p in self.patterns if p.search(text))
        # Each match adds 0.25 confidence, cap at 1.0
        self.confidence = min(1.0, matches * 0.25)
        self.detected = self.confidence > 0.5
        return self.confidence
    
    def is_voicemail(self) -> bool:
        return self.detected


class CallManager:
    """Manages outbound calls via Twilio and OpenAI Realtime Voice."""
    
    def __init__(self, rate_limit: Optional[RateLimit] = None):
        self.twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        self.rate_limiter = RateLimiter(rate_limit or RateLimit())
        self.voicemail_detector = VoicemailDetector()
        self.active_websockets: Dict[str, websockets.WebSocketServerProtocol] = {}
        self._outcome_callbacks: List[Callable[[CallResult], None]] = []
        
        # OpenAI Realtime config
        self.openai_model = "gpt-4o-realtime-preview"
        self.openai_voice = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
        self.system_prompt = """You are a professional sales development representative for a B2B software company. 

Your goal: Qualify the prospect, understand their pain points, and book a meeting if there's fit.

Rules:
1. Be concise — get to the point fast
2. Listen more than you talk (2:1 ratio)
3. Ask open-ended questions about their current process
4. If interested, guide them to book a meeting
5. Handle objections with empathy and data
6. Never be pushy — one "no" means polite wrap-up
7. If voicemail, leave a brief 20-second message with callback number

You are speaking with: {name} at {company}. They are a {title} in the {industry} industry.

Your name is Connor. You work for a company that helps businesses automate their operations.
"""
    
    def on_outcome(self, callback: Callable[[CallResult], None]):
        """Register callback for call outcomes."""
        self._outcome_callbacks.append(callback)
    
    def _notify_outcome(self, result: CallResult):
        """Notify all registered callbacks."""
        for cb in self._outcome_callbacks:
            try:
                cb(result)
            except Exception as e:
                logger.error(f"Outcome callback error: {e}")
    
    def _log_call(self, result: CallResult):
        """Persist call result to JSONL database."""
        try:
            with open(CALLS_DB_PATH, 'a') as f:
                f.write(json.dumps(asdict(result), default=str) + '\n')
        except Exception as e:
            logger.error(f"Failed to log call: {e}")
    
    def _build_twiml(self, prospect: Prospect, stream_url: str) -> str:
        """Build TwiML for connecting call to OpenAI via WebSocket stream."""
        response = VoiceResponse()
        
        # Add recording
        response.record(
            max_length=1800,  # 30 min max
            recording_status_callback='/webhook/recording',
            recording_status_callback_event=['completed', 'absent'],
            trim='trim-silence'
        )
        
        # Connect to Media Stream
        connect = Connect()
        connect.stream(
            name=f"call_{prospect.id}",
            url=stream_url,
            track='both_tracks'
        )
        response.append(connect)
        
        return str(response)
    
    def make_call(self, prospect: Prospect, campaign_id: str = "default") -> Optional[CallResult]:
        """
        Make a single outbound call to a prospect.
        
        Args:
            prospect: The person to call
            campaign_id: Identifier for the calling campaign
            
        Returns:
            CallResult or None if call couldn't be initiated
        """
        if not self.rate_limiter.can_call():
            wait = self.rate_limiter.wait_time()
            logger.warning(f"Rate limit hit. Waiting {wait:.1f}s before calling {prospect.name}")
            time.sleep(wait)
        
        self.rate_limiter.record_call()
        
        try:
            # Update system prompt with prospect info
            system_msg = self.system_prompt.format(
                name=prospect.name,
                company=prospect.company or "their company",
                title=prospect.title or "professional",
                industry=prospect.industry or "business"
            )
            
            # Create call via Twilio
            call = self.twilio.calls.create(
                to=prospect.phone,
                from_=TWILIO_PHONE_NUMBER,
                url=f"https://your-server.com/twiml/{prospect.id}",  # TwiML endpoint
                status_callback="https://your-server.com/webhook/call-status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST',
                record=True,
                recording_channels='dual',
                machine_detection='Enable',  # Detect voicemail
                machine_detection_timeout=30,
                async_amd=True,
                trim='trim-silence'
            )
            
            logger.info(f"Call initiated: {call.sid} -> {prospect.name} ({prospect.phone})")
            
            # Build result (will be updated as call progresses)
            result = CallResult(
                call_sid=call.sid,
                prospect_id=prospect.id,
                status=CallStage.DIALING.value,
                outcome=CallOutcome.NO_ANSWER
            )
            
            # Poll for status updates
            result = self._poll_call_status(call.sid, result, prospect)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to make call to {prospect.name}: {e}")
            self.rate_limiter.release_call()
            return CallResult(
                call_sid="",
                prospect_id=prospect.id,
                status=CallStage.FAILED.value,
                outcome=CallOutcome.ERROR,
                notes=str(e)
            )
    
    def _poll_call_status(self, call_sid: str, result: CallResult, prospect: Prospect, timeout: int = 300) -> CallResult:
        """Poll Twilio for call status updates until completion."""
        start_time = time.time()
        transcript_parts = []
        
        while time.time() - start_time < timeout:
            try:
                call = self.twilio.calls(call_sid).fetch()
                
                result.status = call.status.lower()
                
                # Check for voicemail detection
                if hasattr(call, 'machine_detection') and call.machine_detection:
                    if 'machine' in str(call.machine_detection).lower():
                        result.outcome = CallOutcome.VOICEMAIL
                        logger.info(f"Voicemail detected for {prospect.name}")
                        break
                
                # Handle completed statuses
                if call.status in ['completed', 'busy', 'failed', 'no-answer', 'canceled']:
                    result.duration_seconds = call.duration or 0
                    
                    if call.status == 'no-answer':
                        result.outcome = CallOutcome.NO_ANSWER
                    elif call.status == 'busy':
                        result.outcome = CallOutcome.NO_ANSWER
                    elif call.status == 'failed':
                        result.outcome = CallOutcome.ERROR
                    elif result.duration_seconds < 30:
                        # Short call likely hangup/voicemail
                        result.outcome = CallOutcome.HANGUP
                    
                    # Get recording if available
                    try:
                        recordings = self.twilio.calls(call_sid).recordings.list()
                        if recordings:
                            result.recording_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Recordings/{recordings[0].sid}"
                    except Exception as e:
                        logger.warning(f"Could not fetch recording: {e}")
                    
                    break
                
                # Active call — could fetch transcript from websocket here
                if call.status == 'in-progress':
                    result.status = CallStage.SPEAKING.value
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error polling call {call_sid}: {e}")
                result.outcome = CallOutcome.ERROR
                break
        
        self.rate_limiter.release_call()
        
        # Generate summary from transcript
        if transcript_parts:
            result.transcript = " ".join(transcript_parts)
            result.summary = self._generate_summary(result.transcript)
        
        # Determine final outcome if still ambiguous
        if result.outcome == CallOutcome.NO_ANSWER and result.duration_seconds > 60:
            # Long call but no clear outcome — assume conversation happened
            result.outcome = CallOutcome.FOLLOW_UP_REQUIRED
        
        self._log_call(result)
        self._notify_outcome(result)
        
        logger.info(f"Call completed: {prospect.name} -> {result.outcome.value} ({result.duration_seconds}s)")
        return result
    
    def _generate_summary(self, transcript: str) -> str:
        """Generate a brief summary of the call transcript."""
        # In production, this would call GPT-4 via API
        # For now, return first 200 chars as placeholder
        return transcript[:200] + "..." if len(transcript) > 200 else transcript
    
    def batch_call(self, prospects: List[Prospect], campaign_id: str = "default", 
                   stagger_seconds: float = 2.0) -> List[CallResult]:
        """
        Make calls to multiple prospects with rate limiting and staggering.
        
        Args:
            prospects: List of prospects to call
            campaign_id: Campaign identifier
            stagger_seconds: Seconds between call attempts
            
        Returns:
            List of CallResult objects
        """
        results = []
        logger.info(f"Starting batch of {len(prospects)} calls (stagger: {stagger_seconds}s)")
        
        for i, prospect in enumerate(prospects):
            # Check best time to call
            if prospect.best_time_to_call and not self._is_good_time(prospect):
                logger.info(f"Skipping {prospect.name} — outside best calling window")
                continue
            
            result = self.make_call(prospect, campaign_id)
            if result:
                results.append(result)
            
            # Stagger calls
            if i < len(prospects) - 1:
                time.sleep(stagger_seconds)
        
        logger.info(f"Batch complete: {len(results)}/{len(prospects)} calls made")
        return results
    
    def _is_good_time(self, prospect: Prospect) -> bool:
        """Check if current time is within prospect's preferred calling window."""
        if not prospect.best_time_to_call:
            return True
        
        # Parse simple time windows like "9-11 AM", "2-4 PM"
        try:
            tz = prospect.timezone or "America/New_York"
            now = datetime.now()  # Would use timezone-aware in production
            hour = now.hour
            
            window = prospect.best_time_to_call.lower()
            
            if 'morning' in window or 'am' in window:
                return 8 <= hour <= 11
            elif 'afternoon' in window or 'pm' in window:
                return 13 <= hour <= 16
            elif 'evening' in window:
                return 17 <= hour <= 19
            
            return True
        except Exception:
            return True
    
    def get_call_history(self, prospect_id: Optional[str] = None, 
                        since: Optional[str] = None,
                        limit: int = 100) -> List[Dict]:
        """Retrieve call history from JSONL database."""
        results = []
        
        if not CALLS_DB_PATH.exists():
            return results
        
        try:
            with open(CALLS_DB_PATH) as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if prospect_id and record.get('prospect_id') != prospect_id:
                            continue
                        if since and record.get('created_at', '') < since:
                            continue
                        results.append(record)
                        if len(results) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error reading call history: {e}")
        
        return results
    
    def get_stats(self, days: int = 30) -> Dict:
        """Get call statistics for the last N days."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        calls = self.get_call_history(since=since, limit=10000)
        
        if not calls:
            return {"total": 0, "by_outcome": {}, "avg_duration": 0}
        
        outcomes = {}
        total_duration = 0
        
        for call in calls:
            outcome = call.get('outcome', 'unknown')
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            total_duration += call.get('duration_seconds', 0)
        
        return {
            "total": len(calls),
            "by_outcome": outcomes,
            "avg_duration": total_duration / len(calls),
            "connect_rate": outcomes.get('interested', 0) + outcomes.get('meeting_booked', 0),
            "conversion_rate": outcomes.get('meeting_booked', 0) / len(calls) if calls else 0
        }


# WebSocket handler for OpenAI Realtime Voice API
class OpenAIRealtimeHandler:
    """Handles WebSocket connection between Twilio and OpenAI Realtime API."""
    
    def __init__(self, api_key: str, system_prompt: str):
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.openai_ws = None
        self.twilio_ws = None
    
    async def connect(self):
        """Connect to OpenAI Realtime API."""
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
        
        self.openai_ws = await websockets.connect(url, extra_headers=headers)
        
        # Send initial session config
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.system_prompt,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            }
        }))
    
    async def handle_twilio_stream(self, twilio_ws):
        """Handle media streaming from Twilio."""
        self.twilio_ws = twilio_ws
        
        async for message in twilio_ws:
            data = json.loads(message)
            
            if data.get('event') == 'media':
                # Forward audio to OpenAI
                audio_data = data['media']['payload']
                await self.openai_ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_data
                }))
            
            elif data.get('event') == 'start':
                logger.info(f"Stream started: {data.get('start', {}).get('streamSid')}")
    
    async def handle_openai_response(self):
        """Handle responses from OpenAI."""
        async for message in self.openai_ws:
            response = json.loads(message)
            
            if response.get('type') == 'response.audio.delta':
                # Send audio back to Twilio
                if self.twilio_ws:
                    await self.twilio_ws.send(json.dumps({
                        "event": "media",
                        "streamSid": "",
                        "media": {
                            "payload": response['delta']
                        }
                    }))
            
            elif response.get('type') == 'response.text.done':
                logger.info(f"AI said: {response.get('text', '')}")
            
            elif response.get('type') == 'conversation.item.input_audio_transcription.completed':
                logger.info(f"User said: {response.get('transcript', '')}")


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Sales Caller")
    parser.add_argument("--call", help="Call a single prospect by phone number")
    parser.add_argument("--batch", help="JSON file with prospects array")
    parser.add_argument("--stats", action="store_true", help="Show call statistics")
    parser.add_argument("--history", help="Show call history for prospect ID")
    parser.add_argument("--campaign", default="default", help="Campaign ID")
    
    args = parser.parse_args()
    
    manager = CallManager()
    
    if args.stats:
        stats = manager.get_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.history:
        history = manager.get_call_history(prospect_id=args.history)
        for call in history:
            print(f"[{call['created_at']}] {call['outcome']} ({call['duration_seconds']}s)")
    
    elif args.call:
        prospect = Prospect(
            id="manual",
            name="Unknown",
            phone=args.call
        )
        result = manager.make_call(prospect, args.campaign)
        print(json.dumps(asdict(result), indent=2, default=str))
    
    elif args.batch:
        with open(args.batch) as f:
            data = json.load(f)
        prospects = [Prospect(**p) for p in data]
        results = manager.batch_call(prospects, args.campaign)
        print(f"Completed {len(results)} calls")
        for r in results:
            print(f"  {r.prospect_id}: {r.outcome.value}")
    
    else:
        parser.print_help()
