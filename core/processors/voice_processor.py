"""
voice_processor.py — Handles voice test images (from voicetest column).
Pipeline: OCR → Filter → Validate → Fill schema.
Uses PaddleOCR (NOT vision model).
"""

import time
from typing import Optional
from pathlib import Path

from ..config import LLMProvider, VoiceCallData
from ..api_manager import APIManager
from ..agents.filtration_agent import FiltrationAgent
from ..agents.validation_agent import ValidationAgent
from ..agents.filling_agent import FillingAgent


class VoiceProcessor:
    """
    Processes a single voice test image.
    Uses PaddleOCR for text extraction (no vision model).
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)
        self.filtration = FiltrationAgent(api, log_fn)
        self.validation = ValidationAgent(api, log_fn)
        self.filling = FillingAgent(api, log_fn)

    def process(self, image_path: str, provider: LLMProvider) -> Optional[VoiceCallData]:
        """
        Process a single voice call screenshot through the full pipeline.
        """
        img_name = Path(image_path).stem
        process_start = time.time()
        self.log(f"\n{'─'*40}")
        self.log(f"[VOICE] ▶ Processing: {img_name}")
        self.log(f"[VOICE]   Path: {image_path}")
        self.log(f"{'─'*40}")

        # Step 1: OCR (PaddleOCR, not vision model)
        step_start = time.time()
        self.log(f"[VOICE] Step 1/4: OCR (PaddleOCR)...")
        ocr_text = self.api.call_paddleocr(image_path)
        step_time = time.time() - step_start
        if not ocr_text:
            self.log(f"[VOICE] ✗ Step 1 FAILED: No OCR text from {img_name} ({step_time:.1f}s)")
            return None
        self.log(f"[VOICE] ✓ Step 1: OCR got {len(ocr_text)} chars ({step_time:.1f}s)")
        self.log(f"[VOICE]   OCR Preview: {ocr_text[:150]}...")

        # Step 2: Filter
        step_start = time.time()
        self.log(f"[VOICE] Step 2/4: Filtering...")
        filtered = self.filtration.filter_voice_text(ocr_text, provider)
        step_time = time.time() - step_start
        if not filtered:
            self.log(f"[VOICE] ✗ Step 2 FAILED: Filtration returned nothing ({step_time:.1f}s)")
            return None
        self.log(f"[VOICE] ✓ Step 2: Filtered {len(filtered)} chars ({step_time:.1f}s)")
        self.log(f"[VOICE]   Filtered: {filtered[:200]}")

        # Step 3: Validate
        step_start = time.time()
        self.log(f"[VOICE] Step 3/4: Validating...")
        validated = self.validation.validate_voice(filtered, provider)
        step_time = time.time() - step_start
        if not validated:
            self.log(f"[VOICE] ✗ Step 3 FAILED: Validation returned nothing ({step_time:.1f}s)")
            return None
        self.log(f"[VOICE] ✓ Step 3: Validated {len(validated)} chars ({step_time:.1f}s)")
        self.log(f"[VOICE]   Validated: {validated[:200]}")

        # Step 4: Fill schema
        step_start = time.time()
        self.log(f"[VOICE] Step 4/4: Filling schema...")
        result = self.filling.fill_voice(validated, provider)
        step_time = time.time() - step_start
        total_time = time.time() - process_start
        if result:
            self.log(f"[VOICE] ✓ Step 4: Schema filled ({step_time:.1f}s)")
            self.log(f"[VOICE]   Result: Phone={result.phone_number} Duration={result.call_duration_seconds}s Status={result.call_status}")
            self.log(f"[VOICE] ✅ {img_name} COMPLETE in {total_time:.1f}s")
        else:
            self.log(f"[VOICE] ✗ Step 4 FAILED: Schema filling failed ({step_time:.1f}s)")
            self.log(f"[VOICE] ❌ {img_name} FAILED after {total_time:.1f}s")

        return result
