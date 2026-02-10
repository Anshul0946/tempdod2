"""
service_processor.py — Handles service images (image 1 & 2 per sector).
Pipeline: OCR each image → Filter each → Combine → Validate → Fill schema.
"""

import time
from typing import List, Optional
from pathlib import Path

from ..config import LLMProvider, ServiceData
from ..api_manager import APIManager
from ..agents.filtration_agent import FiltrationAgent
from ..agents.validation_agent import ValidationAgent
from ..agents.filling_agent import FillingAgent


class ServiceProcessor:
    """
    Processes service images for a single sector.
    Images 1 and 2 are OCR'd and filtered individually, then combined
    before validation and schema filling.
    """

    def __init__(self, api: APIManager, log_fn=None):
        self.api = api
        self.log = log_fn or (lambda msg: None)
        self.filtration = FiltrationAgent(api, log_fn)
        self.validation = ValidationAgent(api, log_fn)
        self.filling = FillingAgent(api, log_fn)

    def process(self, image_paths: List[str], provider: LLMProvider) -> Optional[ServiceData]:
        """
        Process service images for one sector.
        
        Args:
            image_paths: List of service image paths (typically 2 images)
            provider: LLM provider for reasoning model
            
        Returns:
            Filled ServiceData schema or None on failure
        """
        if not image_paths:
            self.log("[SERVICE] No service images provided")
            return None

        sector_name = Path(image_paths[0]).stem.split("_")[0]
        self.log(f"\n{'='*40}")
        self.log(f"[SERVICE] Processing {sector_name.upper()} service ({len(image_paths)} images)")
        self.log(f"{'='*40}")

        # Step 1: OCR each image individually
        ocr_texts = []
        for img_path in image_paths:
            img_name = Path(img_path).stem
            self.log(f"[SERVICE] OCR: {img_name}")
            text = self.api.call_paddleocr(img_path)
            if text:
                self.log(f"[SERVICE] OCR got {len(text)} chars from {img_name}")
                ocr_texts.append(text)
            else:
                self.log(f"[SERVICE] WARNING: No OCR text from {img_name}")
            time.sleep(0.5)  # Rate limit between OCR calls

        if not ocr_texts:
            self.log("[SERVICE] ERROR: No OCR text from any service image")
            return None

        # Step 2: Filter each image's OCR output individually
        filtered_results = []
        for i, ocr_text in enumerate(ocr_texts):
            self.log(f"[SERVICE] Filtering image {i+1} text...")
            filtered = self.filtration.filter_service_text(ocr_text, provider)
            if filtered:
                filtered_results.append(filtered)
                self.log(f"[SERVICE] Image {i+1} filtered successfully")
            else:
                self.log(f"[SERVICE] WARNING: Filtration returned nothing for image {i+1}")
            time.sleep(0.5)

        if not filtered_results:
            self.log("[SERVICE] ERROR: No filtered results from any image")
            return None

        # Step 3: Combine filtered results
        if len(filtered_results) == 1:
            combined = filtered_results[0]
        else:
            # Combine by merging the JSON strings into one prompt
            combined = "COMBINED FROM MULTIPLE IMAGES:\n"
            for i, fr in enumerate(filtered_results):
                combined += f"Image {i+1}: {fr}\n"
            self.log(f"[SERVICE] Combined {len(filtered_results)} filtered results")

        # Step 4: Validate combined data
        self.log("[SERVICE] Validating combined service data...")
        validated = self.validation.validate_service(combined, provider)
        if not validated:
            self.log("[SERVICE] ERROR: Validation failed")
            return None
        time.sleep(0.5)

        # Step 5: Fill schema
        self.log("[SERVICE] Filling ServiceData schema...")
        result = self.filling.fill_service(validated, provider)
        if result:
            self.log(f"[SERVICE] ✓ {sector_name.upper()} service data complete")
        else:
            self.log(f"[SERVICE] ERROR: Schema filling failed for {sector_name}")

        return result
