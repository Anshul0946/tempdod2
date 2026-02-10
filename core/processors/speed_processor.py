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
        Process a single speed test image through the full pipeline.
        """
        img_name = Path(image_path).stem
        process_start = time.time()
        self.log(f"\n{'─'*40}")
        self.log(f"[SPEED] ▶ Processing: {img_name}")
        self.log(f"[SPEED]   Path: {image_path}")
        self.log(f"{'─'*40}")

        # Step 1: OCR
        step_start = time.time()
        self.log(f"[SPEED] Step 1/4: OCR...")
        ocr_text = self.api.call_paddleocr(image_path)
        step_time = time.time() - step_start
        if not ocr_text:
            self.log(f"[SPEED] ✗ Step 1 FAILED: No OCR text from {img_name} ({step_time:.1f}s)")
            return None
        self.log(f"[SPEED] ✓ Step 1: OCR got {len(ocr_text)} chars ({step_time:.1f}s)")
        self.log(f"[SPEED]   OCR Preview: {ocr_text[:150]}...")

        # Step 2: Filter
        step_start = time.time()
        self.log(f"[SPEED] Step 2/4: Filtering...")
        filtered = self.filtration.filter_speed_text(ocr_text, provider)
        step_time = time.time() - step_start
        if not filtered:
            self.log(f"[SPEED] ✗ Step 2 FAILED: Filtration returned nothing ({step_time:.1f}s)")
            return None
        self.log(f"[SPEED] ✓ Step 2: Filtered {len(filtered)} chars ({step_time:.1f}s)")
        self.log(f"[SPEED]   Filtered: {filtered[:200]}")

        # Step 3: Validate
        step_start = time.time()
        self.log(f"[SPEED] Step 3/4: Validating...")
        validated = self.validation.validate_speed(filtered, provider)
        step_time = time.time() - step_start
        if not validated:
            self.log(f"[SPEED] ✗ Step 3 FAILED: Validation returned nothing ({step_time:.1f}s)")
            return None
        self.log(f"[SPEED] ✓ Step 3: Validated {len(validated)} chars ({step_time:.1f}s)")
        self.log(f"[SPEED]   Validated: {validated[:200]}")

        # Step 4: Fill schema
        step_start = time.time()
        self.log(f"[SPEED] Step 4/4: Filling schema...")
        result = self.filling.fill_speed(validated, provider)
        step_time = time.time() - step_start
        total_time = time.time() - process_start
        if result:
            self.log(f"[SPEED] ✓ Step 4: Schema filled ({step_time:.1f}s)")
            self.log(f"[SPEED]   Result: DL={result.download_mbps} UL={result.upload_mbps} Ping={result.ping_ms} Jitter={result.jitter_ms}")
            self.log(f"[SPEED] ✅ {img_name} COMPLETE in {total_time:.1f}s")
        else:
            self.log(f"[SPEED] ✗ Step 4 FAILED: Schema filling failed ({step_time:.1f}s)")
            self.log(f"[SPEED] ❌ {img_name} FAILED after {total_time:.1f}s")

        return result
