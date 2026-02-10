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
        Process a single voice call screenshot.
        
        Args:
            image_path: Path to voice call screenshot
            provider: LLM provider for reasoning model
            
        Returns:
            Filled VoiceCallData schema or None on failure
        """
        img_name = Path(image_path).stem
        self.log(f"\n--- VOICE: {img_name} ---")

        # Step 1: OCR (PaddleOCR, not vision model)
        self.log(f"[VOICE] OCR: {img_name}")
        ocr_text = self.api.call_paddleocr(image_path)
        if not ocr_text:
            self.log(f"[VOICE] ERROR: No OCR text from {img_name}")
            return None
        self.log(f"[VOICE] OCR got {len(ocr_text)} chars")
        time.sleep(0.5)

        # Step 2: Filter
        self.log(f"[VOICE] Filtering...")
        filtered = self.filtration.filter_voice_text(ocr_text, provider)
        if not filtered:
            self.log(f"[VOICE] ERROR: Filtration failed for {img_name}")
            return None
        time.sleep(0.5)

        # Step 3: Validate
        self.log(f"[VOICE] Validating...")
        validated = self.validation.validate_voice(filtered, provider)
        if not validated:
            self.log(f"[VOICE] ERROR: Validation failed for {img_name}")
            return None
        time.sleep(0.5)

        # Step 4: Fill schema
        self.log(f"[VOICE] Filling schema...")
        result = self.filling.fill_voice(validated, provider)
        if result:
            self.log(f"[VOICE] ✓ {img_name} complete")
        else:
            self.log(f"[VOICE] ERROR: Schema filling failed for {img_name}")

        return result
