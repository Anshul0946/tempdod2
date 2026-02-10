"""
filling_agent.py — Maps validated key-value pairs into exact Pydantic schemas.
Takes corrected data from the validation agent and produces schema-ready JSON.
"""

import json
import re
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
                return None

            # Clean numeric values
            cleaned = {}
            string_fields = {"max_resolution", "call_status", "phone_number", "time"}
            for key, value in data.items():
                if key in string_fields:
                    cleaned[key] = str(value) if value is not None else None
                else:
                    cleaned[key] = self._clean_number(value)

            return schema_cls(**cleaned)
        except Exception:
            return None

    def fill_service(self, validated_json: str, provider: LLMProvider) -> Optional[ServiceData]:
        """Fill ServiceData schema from validated data."""
        self.log("[FILL] Filling service data schema...")

        # Try direct parse first (fast path)
        result = self._try_direct_parse(validated_json, ServiceData)
        if result:
            nulls = [k for k, v in result.model_dump().items() if v is None]
            if nulls:
                self.log(f"[FILL] WARNING: Service has null fields: {nulls}")
            else:
                self.log(f"[FILL] Service schema filled successfully (all fields populated)")
            return result

        # Fallback: use reasoning model
        self.log("[FILL] Direct parse failed, using reasoning model...")
        prompt = f"""Convert this validated telecom data into the exact ServiceData schema.

VALIDATED DATA:
{validated_json}

REQUIRED OUTPUT SCHEMA (all values must be numbers, no nulls):
{{
    "nr_arfcn": <int>,
    "nr_band": <int>,
    "nr_pci": <int>,
    "nr_bw": <int>,
    "nr5g_rsrp": <float, negative>,
    "nr5g_rsrq": <float, usually negative>,
    "nr5g_sinr": <float>,
    "lte_band": <int>,
    "lte_earfcn": <int>,
    "lte_pci": <int>,
    "lte_bw": <int>,
    "lte_rsrp": <float, negative>,
    "lte_rsrq": <float, usually negative>,
    "lte_sinr": <float>
}}

Return ONLY the JSON object with numeric values."""

        json_str = self.api.call_reasoning(prompt, provider)
        if json_str:
            result = self._try_direct_parse(json_str, ServiceData)
            if result:
                self.log("[FILL] Service schema filled via reasoning model")
                return result

        self.log("[FILL] ERROR: Could not fill service schema")
        return None

    def fill_speed(self, validated_json: str, provider: LLMProvider) -> Optional[SpeedTestData]:
        """Fill SpeedTestData schema from validated data."""
        self.log("[FILL] Filling speed test schema...")

        result = self._try_direct_parse(validated_json, SpeedTestData)
        if result:
            nulls = [k for k, v in result.model_dump().items() if v is None]
            if nulls:
                self.log(f"[FILL] WARNING: Speed test has null fields: {nulls}")
            else:
                self.log(f"[FILL] Speed test schema filled successfully")
            return result

        # Fallback
        self.log("[FILL] Direct parse failed, using reasoning model...")
        prompt = f"""Convert this validated speed test data into the exact SpeedTestData schema.

VALIDATED DATA:
{validated_json}

REQUIRED OUTPUT SCHEMA (all values must be positive numbers):
{{
    "download_mbps": <float>,
    "upload_mbps": <float>,
    "ping_ms": <float>,
    "jitter_ms": <float>
}}

Return ONLY the JSON object with numeric values."""

        json_str = self.api.call_reasoning(prompt, provider)
        if json_str:
            result = self._try_direct_parse(json_str, SpeedTestData)
            if result:
                self.log("[FILL] Speed test schema filled via reasoning model")
                return result

        self.log("[FILL] ERROR: Could not fill speed test schema")
        return None

    def fill_video(self, validated_json: str, provider: LLMProvider) -> Optional[VideoTestData]:
        """Fill VideoTestData schema from validated data."""
        self.log("[FILL] Filling video test schema...")

        result = self._try_direct_parse(validated_json, VideoTestData)
        if result:
            nulls = [k for k, v in result.model_dump().items() if v is None]
            if nulls:
                self.log(f"[FILL] WARNING: Video test has null fields: {nulls}")
            else:
                self.log(f"[FILL] Video test schema filled successfully")
            return result

        # Fallback
        self.log("[FILL] Direct parse failed, using reasoning model...")
        prompt = f"""Convert this validated video test data into the exact VideoTestData schema.

VALIDATED DATA:
{validated_json}

REQUIRED OUTPUT SCHEMA:
{{
    "max_resolution": "<string: 360p|480p|720p|1080p|1440p|2160p|4K>",
    "load_time_ms": <float, positive>,
    "buffering_percentage": <float, 0-100>
}}

Return ONLY the JSON object."""

        json_str = self.api.call_reasoning(prompt, provider)
        if json_str:
            result = self._try_direct_parse(json_str, VideoTestData)
            if result:
                self.log("[FILL] Video test schema filled via reasoning model")
                return result

        self.log("[FILL] ERROR: Could not fill video test schema")
        return None

    def fill_voice(self, validated_json: str, provider: LLMProvider) -> Optional[VoiceCallData]:
        """Fill VoiceCallData schema from validated data."""
        self.log("[FILL] Filling voice call schema...")

        result = self._try_direct_parse(validated_json, VoiceCallData)
        if result:
            nulls = [k for k, v in result.model_dump().items() if v is None]
            if nulls:
                self.log(f"[FILL] WARNING: Voice call has null fields: {nulls}")
            else:
                self.log(f"[FILL] Voice call schema filled successfully")
            return result

        # Fallback
        self.log("[FILL] Direct parse failed, using reasoning model...")
        prompt = f"""Convert this validated voice call data into the exact VoiceCallData schema.

VALIDATED DATA:
{validated_json}

REQUIRED OUTPUT SCHEMA:
{{
    "phone_number": "<string, format: (xxx) xxx-xxxx>",
    "call_duration_seconds": <float, duration in seconds>,
    "call_status": "<string: Connected|Completed|Failed|Ringing|Dialing>",
    "time": "<string, MM:SS format>"
}}

Return ONLY the JSON object."""

        json_str = self.api.call_reasoning(prompt, provider)
        if json_str:
            result = self._try_direct_parse(json_str, VoiceCallData)
            if result:
                self.log("[FILL] Voice call schema filled via reasoning model")
                return result

        self.log("[FILL] ERROR: Could not fill voice call schema")
        return None
