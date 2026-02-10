"""
filling_agent.py — Maps validated key-value pairs into exact Pydantic schemas.
Takes corrected data from the validation agent and produces schema-ready JSON.
"""

import json
import re
import time
from typing import Optional
from ..api_manager import APIManager
from ..config import LLMProvider, ServiceData, SpeedTestData, VideoTestData, VoiceCallData


class FillingAgent:
    """
    AI agent that fills Pydantic schemas from validated parameter data.
    If the validated data is already in schema format (which it should be
    after the validation agent), this agent does final cleanup and parsing.
    Falls back to reasoning model if simple parsing fails.
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)

    def _clean_number(self, value) -> Optional[float]:
        """Extract a numeric value from potentially messy input."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().strip("'\"")
        # Extract number from string like "363 Mbps" or "-85 dBm"
        match = re.search(r'(-?\d+\.?\d*)', s)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, TypeError):
                return None
        return None

    def _try_direct_parse(self, validated_json: str, schema_cls):
        """
        Try to directly parse validated JSON into the schema.
        The validation agent should already return schema-ready field names.
        """
        try:
            data = json.loads(validated_json)
            if not isinstance(data, dict):
                self.log(f"[FILL]   Direct parse: JSON is not a dict (type: {type(data).__name__})")
                return None

            # Clean numeric values
            cleaned = {}
            string_fields = {"max_resolution", "call_status", "phone_number", "time"}
            for key, value in data.items():
                if key in string_fields:
                    cleaned[key] = str(value) if value is not None else None
                else:
                    cleaned[key] = self._clean_number(value)

            self.log(f"[FILL]   Direct parse: cleaned {len(cleaned)} fields: {list(cleaned.keys())}")
            result = schema_cls(**cleaned)
            self.log(f"[FILL]   Direct parse: ✓ Schema constructed successfully")
            return result
        except Exception as e:
            self.log(f"[FILL]   Direct parse failed: {type(e).__name__}: {e}")
            return None

    def fill_service(self, validated_json: str, provider: LLMProvider) -> Optional[ServiceData]:
        """Fill ServiceData schema using AI Reasoning."""
        self.log(f"[FILL] Filling ServiceData (input: {len(validated_json)} chars)...")
        start = time.time()

        prompt = f"""You are a telecom data specialist. Map this validated input data into the EXACT ServiceData schema.
        
INPUT DATA:
{validated_json}

INSTRUCTIONS:
1. Map input keys to the required schema keys intelligently (e.g., "NR_BAND" -> "nr_band").
2. Ensure all values are numeric (float/int).
3. Handle any minor naming mismatches using your knowledge of telecom parameters.
4. If a value is missing or null, leave it as null (do not invent data).

REQUIRED OUTPUT SCHEMA (JSON only, no markdown):
{{
    "nr_arfcn": <int or null>,
    "nr_band": <int or null>,
    "nr_pci": <int or null>,
    "nr_bw": <int or null>,
    "nr5g_rsrp": <float or null>,
    "nr5g_rsrq": <float or null>,
    "nr5g_sinr": <float or null>,
    "lte_band": <int or null>,
    "lte_earfcn": <int or null>,
    "lte_pci": <int or null>,
    "lte_bw": <int or null>,
    "lte_rsrp": <float or null>,
    "lte_rsrq": <float or null>,
    "lte_sinr": <float or null>
}}"""

        json_str = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        if json_str:
            self.log(f"[FILL]   AI response: {len(json_str)} chars ({elapsed:.1f}s)")
            result = self._try_direct_parse(json_str, ServiceData)
            if result:
                self.log(f"[FILL] ✓ Service schema filled ({elapsed:.1f}s)")
                return result

        self.log(f"[FILL] ✗ Could not fill service schema ({elapsed:.1f}s)")
        return None

    def fill_speed(self, validated_json: str, provider: LLMProvider) -> Optional[SpeedTestData]:
        """Fill SpeedTestData schema using AI Reasoning."""
        self.log(f"[FILL] Filling SpeedTestData (input: {len(validated_json)} chars)...")
        start = time.time()

        prompt = f"""You are a data entry specialist. Map this validated input data into the EXACT SpeedTestData schema.

INPUT DATA:
{validated_json}

INSTRUCTIONS:
1. Map input keys to the required schema keys (e.g., "Download Mbps" -> "download_mbps").
2. Ensure all values are numeric.
3. Handle standard variations (e.g., "Ping" -> "ping_ms").

REQUIRED OUTPUT SCHEMA (JSON only, no markdown):
{{
    "download_mbps": <float or null>,
    "upload_mbps": <float or null>,
    "ping_ms": <float or null>,
    "jitter_ms": <float or null>
}}"""

        json_str = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        if json_str:
            self.log(f"[FILL]   AI response: {len(json_str)} chars ({elapsed:.1f}s)")
            result = self._try_direct_parse(json_str, SpeedTestData)
            if result:
                self.log(f"[FILL] ✓ Speed schema filled ({elapsed:.1f}s)")
                return result

        self.log(f"[FILL] ✗ Could not fill speed test schema ({elapsed:.1f}s)")
        return None

    def fill_video(self, validated_json: str, provider: LLMProvider) -> Optional[VideoTestData]:
        """Fill VideoTestData schema using AI Reasoning."""
        self.log(f"[FILL] Filling VideoTestData (input: {len(validated_json)} chars)...")
        start = time.time()

        prompt = f"""You are a data entry specialist. Map this validated input data into the EXACT VideoTestData schema.

INPUT DATA:
{validated_json}

INSTRUCTIONS:
1. Map input keys to schema keys (e.g., "MAX RESOLUTION" -> "max_resolution").
2. Ensure format compliance.

REQUIRED OUTPUT SCHEMA (JSON only, no markdown):
{{
    "max_resolution": "<string: 360p|480p|720p|1080p|1440p|2160p|4K>",
    "load_time_ms": <float or null>,
    "buffering_percentage": <float or null>
}}"""

        json_str = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        if json_str:
            self.log(f"[FILL]   AI response: {len(json_str)} chars ({elapsed:.1f}s)")
            result = self._try_direct_parse(json_str, VideoTestData)
            if result:
                self.log(f"[FILL] ✓ Video schema filled ({elapsed:.1f}s)")
                return result

        self.log(f"[FILL] ✗ Could not fill video test schema ({elapsed:.1f}s)")
        return None

    def fill_voice(self, validated_json: str, provider: LLMProvider) -> Optional[VoiceCallData]:
        """Fill VoiceCallData schema using AI Reasoning."""
        self.log(f"[FILL] Filling VoiceCallData (input: {len(validated_json)} chars)...")
        start = time.time()

        prompt = f"""You are a data entry specialist. Map this validated input data into the EXACT VoiceCallData schema.

INPUT DATA:
{validated_json}

INSTRUCTIONS:
1. Map input keys to schema keys.
2. Ensure format compliance.

REQUIRED OUTPUT SCHEMA (JSON only, no markdown):
{{
    "phone_number": "<string, format: (xxx) xxx-xxxx>",
    "call_duration_seconds": <float or null>,
    "call_status": "<string: Connected|Completed|Failed|Ringing|Dialing>",
    "time": "<string, MM:SS format>"
}}"""

        json_str = self.api.call_reasoning(prompt, provider)
        elapsed = time.time() - start
        if json_str:
            self.log(f"[FILL]   AI response: {len(json_str)} chars ({elapsed:.1f}s)")
            result = self._try_direct_parse(json_str, VoiceCallData)
            if result:
                self.log(f"[FILL] ✓ Voice schema filled ({elapsed:.1f}s)")
                return result

        self.log(f"[FILL] ✗ Could not fill voice call schema ({elapsed:.1f}s)")
        return None
