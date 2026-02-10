"""
video_processor.py — Handles video test images (image 8 per sector).
Pipeline: OCR → Filter → Validate → Fill schema.
"""

import time
from typing import Optional
from pathlib import Path

from ..config import LLMProvider, VideoTestData
from ..api_manager import APIManager
from ..agents.filtration_agent import FiltrationAgent
from ..agents.validation_agent import ValidationAgent
from ..agents.filling_agent import FillingAgent


class VideoProcessor:
    """
    Processes a single video test image.
    One video test image per sector (image 8).
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)
        self.filtration = FiltrationAgent(api, log_fn)
        self.validation = ValidationAgent(api, log_fn)
        self.filling = FillingAgent(api, log_fn)

    def process(self, image_path: str, provider: LLMProvider) -> Optional[VideoTestData]:
        """
        Process a single video test image.
        
        Args:
            image_path: Path to video test screenshot
            provider: LLM provider for reasoning model
            
        Returns:
            Filled VideoTestData schema or None on failure
        """
        img_name = Path(image_path).stem
        self.log(f"\n--- VIDEO: {img_name} ---")

        # Step 1: OCR
        self.log(f"[VIDEO] OCR: {img_name}")
        ocr_text = self.api.call_paddleocr(image_path)
        if not ocr_text:
            self.log(f"[VIDEO] ERROR: No OCR text from {img_name}")
            return None
        self.log(f"[VIDEO] OCR got {len(ocr_text)} chars")
        time.sleep(0.5)

        # Step 2: Filter
        self.log(f"[VIDEO] Filtering...")
        filtered = self.filtration.filter_video_text(ocr_text, provider)
        if not filtered:
            self.log(f"[VIDEO] ERROR: Filtration failed for {img_name}")
            return None
        time.sleep(0.5)

        # Step 3: Validate
        self.log(f"[VIDEO] Validating...")
        validated = self.validation.validate_video(filtered, provider)
        if not validated:
            self.log(f"[VIDEO] ERROR: Validation failed for {img_name}")
            return None
        time.sleep(0.5)

        # Step 4: Fill schema
        self.log(f"[VIDEO] Filling schema...")
        result = self.filling.fill_video(validated, provider)
        if result:
            self.log(f"[VIDEO] ✓ {img_name} complete")
        else:
            self.log(f"[VIDEO] ERROR: Schema filling failed for {img_name}")

        return result
