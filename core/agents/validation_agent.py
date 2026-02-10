"""
validation_agent.py — Telecom expert + OCR error corrector.
Validates extracted data, fixes OCR misreads, enforces parameter ranges.
NEVER removes values — always guesses the closest valid value.
"""

import json
from typing import Optional
from ..api_manager import APIManager
from ..config import LLMProvider
from ..constants import (
    SERVICE_PARAMS, SPEED_TEST_PARAMS, VIDEO_TEST_PARAMS, VOICE_TEST_PARAMS,
    OCR_CHAR_CORRECTIONS, SAMPLE_SERVICE_OCR, SAMPLE_SPEED_OCR,
    SAMPLE_VIDEO_OCR, SAMPLE_VOICE_OCR,
)


def _format_param_metadata(params: dict) -> str:
    """Format parameter metadata into a readable string for the prompt."""
    lines = []
    for name, meta in params.items():
        parts = [f"  - {name}: type={meta['type']}"]
        if "range" in meta:
            parts.append(f"range={meta['range']}")
        if "unit" in meta:
            parts.append(f"unit={meta.get('unit', 'none')}")
        if "allowed" in meta:
            parts.append(f"allowed={meta['allowed']}")
        parts.append(f"sample={meta.get('sample', 'N/A')}")
        parts.append(f"desc=\"{meta['desc']}\"")
        lines.append(", ".join(parts))
    return "\n".join(lines)


def _format_ocr_corrections() -> str:
    """Format OCR correction table for the prompt."""
    lines = []
    for char, digit in OCR_CHAR_CORRECTIONS.items():
        lines.append(f"  '{char}' is often misread for '{digit}'")
    return "\n".join(lines)


# ─── Shared validation rules injected into every prompt ───
VALIDATION_RULES = f"""
CRITICAL RULES — YOU MUST FOLLOW ALL OF THESE:

1. NEVER REMOVE A VALUE. If a value looks wrong, GUESS the closest valid value.
2. Fix common OCR character misreads:
{_format_ocr_corrections()}

3. If a value is out of the valid range, adjust to the nearest boundary OR guess what OCR misread.
   Example: if RSRP shows "73" but range is (-156, -31), it should be "-73" (missing negative sign).

4. Type enforcement:
   - If type is "int" or "float", the value MUST be a number
   - If OCR shows "3B4" for a float field, guess "384" (B→8)
   - If OCR shows "1o4" for an int field, guess "104" (o→0)

5. BAND notation: "T2" means Band 2, "B66" means Band 66. Extract the number only.

6. NO NULL VALUES in the output. Every parameter must have a value.
   If you truly cannot determine a value, use the sample value provided.

7. Return ONLY a JSON object with corrected values. No explanations.
"""


class ValidationAgent:
    """
    AI agent that validates and corrects filtered OCR data.
    Has full telecom parameter metadata: names, types, ranges, samples.
    Acts as both an OCR error corrector and a telecom domain expert.
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)

    def validate_service(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct service data parameters."""
        param_info = _format_param_metadata(SERVICE_PARAMS)

        prompt = f"""You are a telecom data validation expert and OCR error correction specialist.

You are validating cellular network SERVICE data extracted by OCR.

PARAMETER DEFINITIONS (name, type, valid range, unit, sample value):
{param_info}

{VALIDATION_RULES}

REFERENCE — what correct service data looks like:
{SAMPLE_SERVICE_OCR}

FILTERED DATA TO VALIDATE:
{filtered_json}

Map the input parameter names to the schema field names:
- NR_ARFCN / NR ARFCN → nr_arfcn
- NR_BAND / NR BAND → nr_band
- NR_PCI / NR PCI → nr_pci
- NR_BW / NR BW → nr_bw
- NRSG_RSRP / NR_ANT MAX RSRP → nr5g_rsrp
- NRSG_RSRQ → nr5g_rsrq
- NRSG_SINR → nr5g_sinr
- BAND → lte_band (extract number from "T2" → 2)
- EARFCN → lte_earfcn
- PCI → lte_pci (the standalone "PCI" not "NR_PCI")
- BW → lte_bw (the standalone "BW" not "NR_BW")
- RSRP → lte_rsrp (the standalone "RSRP" not "NRSG_RSRP")
- RSRQ → lte_rsrq
- SNR → lte_sinr

Return ONLY a JSON object with the SCHEMA field names as keys and corrected numeric values:
{{"nr_arfcn": 632736, "nr_band": 977, "nr_pci": 966, "nr_bw": 70, "nr5g_rsrp": -93, "nr5g_rsrq": -11, "nr5g_sinr": 230, "lte_band": 2, "lte_earfcn": 5110, "lte_pci": 320, "lte_bw": 10, "lte_rsrp": -73, "lte_rsrq": -12, "lte_sinr": 106}}"""

        self.log("[VALIDATE] Running service data validation...")
        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log("[VALIDATE] Service data validated successfully")
        else:
            self.log("[VALIDATE] WARNING: Service validation returned no result")
        return result

    def validate_speed(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct speed test parameters."""
        param_info = _format_param_metadata(SPEED_TEST_PARAMS)

        prompt = f"""You are a telecom data validation expert and OCR error correction specialist.

You are validating network SPEED TEST data extracted by OCR.

PARAMETER DEFINITIONS (name, type, valid range, unit, sample value):
{param_info}

{VALIDATION_RULES}

REFERENCE — what correct speed test data looks like:
{SAMPLE_SPEED_OCR}

FILTERED DATA TO VALIDATE:
{filtered_json}

Map the input parameter names to the schema field names:
- Download Mbps / Download → download_mbps
- Upload Mbps / Upload → upload_mbps
- Ping → ping_ms
- Jitter → jitter_ms

ADDITIONAL SPEED TEST RULES:
- Download and Upload speeds are ALWAYS positive (Mbps)
- Ping and Jitter are ALWAYS positive (ms)
- Download is usually higher than Upload
- Typical 5G download: 100-1000 Mbps, upload: 10-200 Mbps
- Typical ping: 10-100 ms, jitter: 1-50 ms

Return ONLY a JSON object with schema field names and corrected numeric values:
{{"download_mbps": 382, "upload_mbps": 95.2, "ping_ms": 44, "jitter_ms": 7}}"""

        self.log("[VALIDATE] Running speed test validation...")
        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log("[VALIDATE] Speed test data validated successfully")
        else:
            self.log("[VALIDATE] WARNING: Speed validation returned no result")
        return result

    def validate_video(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct video test parameters."""
        param_info = _format_param_metadata(VIDEO_TEST_PARAMS)

        prompt = f"""You are a telecom data validation expert and OCR error correction specialist.

You are validating VIDEO STREAMING TEST data extracted by OCR.

PARAMETER DEFINITIONS (name, type, valid range/allowed values, unit, sample value):
{param_info}

{VALIDATION_RULES}

REFERENCE — what correct video test data looks like:
{SAMPLE_VIDEO_OCR}

FILTERED DATA TO VALIDATE:
{filtered_json}

Map the input parameter names to the schema field names:
- MAX RESOLUTION / Max Resolution → max_resolution
- Load Time → load_time_ms
- Buffering → buffering_percentage

ADDITIONAL VIDEO TEST RULES:
- max_resolution must be one of: "360p", "480p", "720p", "1080p", "1440p", "2160p", "4K"
- If OCR shows "216Op" → correct to "2160p" (O→0)
- load_time_ms is ALWAYS positive
- buffering_percentage is 0-100, if empty/missing default to 0

Return ONLY a JSON object with schema field names and corrected values:
{{"max_resolution": "2160p", "load_time_ms": 985, "buffering_percentage": 0}}"""

        self.log("[VALIDATE] Running video test validation...")
        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log("[VALIDATE] Video test data validated successfully")
        else:
            self.log("[VALIDATE] WARNING: Video validation returned no result")
        return result

    def validate_voice(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct voice call parameters."""
        param_info = _format_param_metadata(VOICE_TEST_PARAMS)

        prompt = f"""You are a telecom data validation expert and OCR error correction specialist.

You are validating VOICE CALL data extracted by OCR.

PARAMETER DEFINITIONS (name, type, valid range/allowed values, unit, sample value):
{param_info}

{VALIDATION_RULES}

REFERENCE — what correct voice call data looks like:
{SAMPLE_VOICE_OCR}

FILTERED DATA TO VALIDATE:
{filtered_json}

SCHEMA FIELD MAPPING:
- phone_number: string in format "(xxx) xxx-xxxx"
- call_duration_seconds: float, duration in seconds
- call_status: one of "Connected", "Completed", "Failed", "Ringing", "Dialing"
- time: string in "MM:SS" or "HH:MM" format

ADDITIONAL VOICE TEST RULES:
- Phone number format: (area_code) exchange-subscriber, e.g., "(312) 774-3128"
- If OCR misreads digits in phone number, try to correct (e.g., "3l2" → "312")
- Duration "00:12" = 12 seconds, "01:30" = 90 seconds
- If call buttons (Speaker, Mute) are present, call_status is "Connected"
- time field should be the call duration display value as-is (e.g., "00:12")

Return ONLY a JSON object with schema field names and corrected values:
{{"phone_number": "(312) 774-3128", "call_duration_seconds": 12, "call_status": "Connected", "time": "00:12"}}"""

        self.log("[VALIDATE] Running voice call validation...")
        result = self.api.call_reasoning(prompt, provider)
        if result:
            self.log("[VALIDATE] Voice call data validated successfully")
        else:
            self.log("[VALIDATE] WARNING: Voice validation returned no result")
        return result
