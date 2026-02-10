"""
filtration_agent.py — Cleans raw OCR output into structured key-value pairs.
Removes noise, extracts telecom-relevant parameters, normalizes labels.
"""

import json
from typing import Optional, Dict
from ..api_manager import APIManager
from ..config import LLMProvider


class FiltrationAgent:
    """
    AI agent that filters raw OCR output into clean parameter:value pairs.
    Uses the reasoning model to intelligently parse noisy OCR text.
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)

    def filter_service_text(self, raw_ocr: str, provider: LLMProvider) -> Optional[str]:
        """Filter service image OCR text. Returns clean JSON string."""
        prompt = f"""You are an OCR output filtration specialist for cellular network service data.

Your job is to take raw OCR text from a cellular network info screen and extract ONLY the relevant telecom parameters as a clean key-value list.

RULES:
1. Extract ONLY telecom parameters — remove timestamps, status bars, UI elements
2. Keep the parameter name exactly as shown (e.g., "NR_BAND", "RSRP", "EARFCN")
3. Keep the value as-is (don't fix numbers yet — a validation step will do that)
4. Strip units from values (remove "dBm", "MHz", "dB", "ms", "K" suffixes)
5. Return ONLY a JSON object with parameter names as keys and values as strings
6. Do NOT include parameters with values like "Active", "Present", "Ready", "--", "Not Config", "Not Configured", "Not present", "err(0)" — these are status fields, not measurement data
7. DO include: NR_BAND, NR_BW, NR_ARFCN, NR_PCI, NRSG_RSRP, NRSG_RSRQ, NRSG_SINR, NR_ANT MAX RSRP, NR_ANT MIN RSRP, BAND, BW, EARFCN, PCI, RSRP, RSRQ, SNR
8. For "BAND: T2" style values, keep as "T2" — validation will handle conversion
9. No extra text, explanations, or markdown — ONLY the JSON object

RELEVANT PARAMETERS TO LOOK FOR:
- NR (5G): NR_BAND, NR_BW, NR_ARFCN, NR_PCI, NRSG_RSRP, NRSG_SINR, NRSG_RSRQ, NR_ANT MAX RSRP
- LTE (4G): BAND, BW, EARFCN, PCI, RSRP, RSRQ, SNR

RAW OCR TEXT:
{raw_ocr}

Return ONLY a JSON object like: {{"NR_BAND": "977", "RSRP": "-73", ...}}"""

        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log(f"[FILTER] Service: extracted parameters from OCR")
        return result

    def filter_speed_text(self, raw_ocr: str, provider: LLMProvider) -> Optional[str]:
        """Filter speed test OCR text. Returns clean JSON string."""
        prompt = f"""You are an OCR output filtration specialist for network speed test results.

Extract ONLY speed test parameters from this raw OCR text.

RULES:
1. Look for: Download speed (Mbps), Upload speed (Mbps), Ping (ms), Jitter (ms)
2. Strip units — return only the numeric part
3. Remove timestamps, "5G+", "SPEEDTEST" headers, and any other UI text
4. Return ONLY a JSON object
5. No extra text or explanations

EXPECTED PARAMETERS:
- "Download Mbps": download speed value
- "Upload Mbps": upload speed value  
- "Ping": ping latency value
- "Jitter": jitter value

RAW OCR TEXT:
{raw_ocr}

Return ONLY a JSON object like: {{"Download Mbps": "382", "Upload Mbps": "95.2", "Ping": "44", "Jitter": "7"}}"""

        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log(f"[FILTER] Speed: extracted parameters from OCR")
        return result

    def filter_video_text(self, raw_ocr: str, provider: LLMProvider) -> Optional[str]:
        """Filter video test OCR text. Returns clean JSON string."""
        prompt = f"""You are an OCR output filtration specialist for video streaming test results.

Extract ONLY video test parameters from this raw OCR text.

RULES:
1. Look for: Max Resolution, Load Time (ms), Buffering percentage
2. Strip units from numeric values (remove "ms", "%")
3. Keep resolution as string (e.g., "2160p", "1080p", "4K")
4. For Buffering, if no percentage is shown, use "0"
5. Remove timestamps, "5G+", "SPEEDTEST" headers, UI text
6. Return ONLY a JSON object
7. No extra text or explanations

RAW OCR TEXT:
{raw_ocr}

Return ONLY a JSON object like: {{"MAX RESOLUTION": "2160p", "Load Time": "985", "Buffering": "0"}}"""

        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log(f"[FILTER] Video: extracted parameters from OCR")
        return result

    def filter_voice_text(self, raw_ocr: str, provider: LLMProvider) -> Optional[str]:
        """Filter voice call OCR text. Returns clean JSON string."""
        prompt = f"""You are an OCR output filtration specialist for voice call screen data.

Extract voice call parameters from this raw OCR text.

RULES:
1. Look for: phone number (format like (xxx) xxx-xxxx), call duration (MM:SS format), location
2. The first line is usually the call duration in MM:SS format (e.g., "00:12" = 12 seconds)
3. The phone number is in format (area_code) xxx-xxxx
4. Remove UI elements like "Speaker", "Mute", "Keypad", "Add call", "FaceTime", etc.
5. If you see a duration like "00:12", convert to seconds: 12
6. Determine call status from context: if duration is shown and buttons are visible, status is "Connected"
7. Return ONLY a JSON object
8. No extra text or explanations

RAW OCR TEXT:
{raw_ocr}

Return ONLY a JSON object like: {{"phone_number": "(312) 774-3128", "call_duration_seconds": "12", "call_status": "Connected", "time": "00:12"}}"""

        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log(f"[FILTER] Voice: extracted parameters from OCR")
        return result
