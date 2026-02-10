"""
speed_processor.py — Handles speed test images (image 3-7 per sector).
Pipeline: OCR → Filter → Validate → Fill schema (each image independently).
"""

import time
from typing import Optional
from pathlib import Path

from ..config import LLMProvider, SpeedTestData
from ..api_manager import APIManager
from ..agents.filtration_agent import FiltrationAgent
from ..agents.validation_agent import ValidationAgent
from ..agents.filling_agent import FillingAgent


class SpeedProcessor:
    """
    Processes a single speed test image.
    Each speed test image is fully independent — no combining.
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)
        self.filtration = FiltrationAgent(api, log_fn)
        self.validation = ValidationAgent(api, log_fn)
        self.filling = FillingAgent(api, log_fn)

    def process(self, image_path: str, provider: LLMProvider) -> Optional[SpeedTestData]:
        """
        Process a single speed test image.
        
        Args:
            image_path: Path to speed test screenshot
            provider: LLM provider for reasoning model
            
        Returns:
            Filled SpeedTestData schema or None on failure
        """
        img_name = Path(image_path).stem
        self.log(f"\n--- SPEED: {img_name} ---")

        # Step 1: OCR
        self.log(f"[SPEED] OCR: {img_name}")
        ocr_text = self.api.call_paddleocr(image_path)
        if not ocr_text:
            self.log(f"[SPEED] ERROR: No OCR text from {img_name}")
            return None
        self.log(f"[SPEED] OCR got {len(ocr_text)} chars")
        time.sleep(0.5)

        # Step 2: Filter
        self.log(f"[SPEED] Filtering...")
        filtered = self.filtration.filter_speed_text(ocr_text, provider)
        if not filtered:
            self.log(f"[SPEED] ERROR: Filtration failed for {img_name}")
            return None
        time.sleep(0.5)

        # Step 3: Validate
        self.log(f"[SPEED] Validating...")
        validated = self.validation.validate_speed(filtered, provider)
        if not validated:
            self.log(f"[SPEED] ERROR: Validation failed for {img_name}")
            return None
        time.sleep(0.5)

        # Step 4: Fill schema
        self.log(f"[SPEED] Filling schema...")
        result = self.filling.fill_speed(validated, provider)
        if result:
            self.log(f"[SPEED] ✓ {img_name} complete")
        else:
            self.log(f"[SPEED] ERROR: Schema filling failed for {img_name}")

        return result
