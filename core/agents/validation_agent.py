"""
validation_agent.py — Telecom expert + OCR error corrector.
Validates extracted data, fixes OCR misreads, enforces parameter ranges.
NEVER removes values — always guesses the closest valid value.
"""

import json
import time
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

    def _log_validation_result(self, test_type: str, input_json: str, result: Optional[str], elapsed: float):
        """Log validation input/output comparison."""
        if result:
            try:
                in_data = json.loads(input_json) if isinstance(input_json, str) else {}
                out_data = json.loads(result) if isinstance(result, str) else {}
                in_keys = set(in_data.keys()) if isinstance(in_data, dict) else set()
                out_keys = set(out_data.keys()) if isinstance(out_data, dict) else set()
                
                self.log(f"[VALIDATE] ✓ {test_type} validated ({elapsed:.1f}s)")
                self.log(f"[VALIDATE]   Input keys:  {sorted(in_keys)}")
                self.log(f"[VALIDATE]   Output keys: {sorted(out_keys)}")
                
                # Show corrected values
                if isinstance(in_data, dict) and isinstance(out_data, dict):
                    corrections = []
                    for key in out_keys:
                        in_val = in_data.get(key)
                        out_val = out_data.get(key)
                        if in_val is not None and str(in_val) != str(out_val):
                            corrections.append(f"{key}: {in_val} → {out_val}")
                    if corrections:
                        self.log(f"[VALIDATE]   Corrections: {', '.join(corrections[:5])}")
                    else:
                        self.log(f"[VALIDATE]   No corrections needed")
            except Exception:
                self.log(f"[VALIDATE] ✓ {test_type} validated ({elapsed:.1f}s, {len(result)} chars)")
        else:
            self.log(f"[VALIDATE] ✗ {test_type} validation FAILED ({elapsed:.1f}s)")

    def validate_service(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct service data parameters."""
        self.log(f"[VALIDATE] Service validation starting (input: {len(filtered_json)} chars)")
        start = time.time()
        param_info = _format_param_metadata(SERVICE_PARAMS)

        prompt = f"""You are a telecom data validation expert.
        
CRITICAL VALIDATION RULES:
1. **PCI (Physical Cell ID)**: MUST be an integer between 0 and 1008. 
   - If OCR shows negative (e.g., "-150"), ASSUME IT IS POSITIVE (correct to "150").
   - If OCR shows "l50", correct to "150".
2. **EARFCN / NR_ARFCN**: MUST be a positive integer.
3. **BAND / NR_BAND**: Must be a valid integer band number (e.g., 2, 66, 71, 41, 77, 48).
   - If "T2", return 2. If "B66", return 66.
4. **Signal Metrics**:
   - **RSRP**: Range -140 to -40 dBm.
   - **RSRQ**: Range -40 to -3 dB.
   - **SINR**: Range -10 to 40 dB.
   - If values are outside these ranges, try to fix common OCR errors (e.g., missing negative sign).

5. **NEVER RETURN NULL** if a value can be recovered. Guess the most likely valid value.

PARAMETER DEFINITIONS:
{param_info}

{VALIDATION_RULES}

FILTERED DATA:
{filtered_json}

MAPPING:
- NR_ARFCN / NR ARFCN → nr_arfcn
- NR_BAND / NR BAND → nr_band
- NR_PCI / NR PCI → nr_pci
- NR_BW / NR BW → nr_bw
- NRSG_RSRP / NR_ANT MAX RSRP → nr5g_rsrp
- NRSG_RSRQ → nr5g_rsrq
- NRSG_SINR → nr5g_sinr
- BAND → lte_band
- EARFCN → lte_earfcn
- PCI → lte_pci
- BW → lte_bw
- RSRP → lte_rsrp
- RSRQ → lte_rsrq
- SNR → lte_sinr

Return ONLY a JSON object with the SCHEMA fields and CORRECTED values.
Example: {{"nr_pci": 150, "lte_pci": 320, ...}}"""

        result = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        self._log_validation_result("Service", filtered_json, result, elapsed)
        return result

    def validate_speed(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct speed test parameters."""
        self.log(f"[VALIDATE] Speed validation starting (input: {len(filtered_json)} chars)")
        start = time.time()
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

        result = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        self._log_validation_result("Speed", filtered_json, result, elapsed)
        return result

    def validate_video(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct video test parameters."""
        self.log(f"[VALIDATE] Video validation starting (input: {len(filtered_json)} chars)")
        start = time.time()
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

        result = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        self._log_validation_result("Video", filtered_json, result, elapsed)
        return result

    def validate_voice(self, filtered_json: str, provider: LLMProvider) -> Optional[str]:
        """Validate and correct voice call parameters."""
        self.log(f"[VALIDATE] Voice validation starting (input: {len(filtered_json)} chars)")
        start = time.time()
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

        result = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        self._log_validation_result("Voice", filtered_json, result, elapsed)
        return result
