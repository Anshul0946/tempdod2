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
        """
        if not image_paths:
            self.log("[SERVICE] No service images provided")
            return None

        sector_name = Path(image_paths[0]).stem.split("_")[0]
        process_start = time.time()
        self.log(f"\n{'='*40}")
        self.log(f"[SERVICE] ▶ Processing {sector_name.upper()} service ({len(image_paths)} images)")
        for ip in image_paths:
            self.log(f"[SERVICE]   Image: {Path(ip).name}")
        self.log(f"{'='*40}")

        # Step 1: OCR each image individually
        self.log(f"[SERVICE] Step 1/5: OCR ({len(image_paths)} images)...")
        ocr_texts = []
        for i, img_path in enumerate(image_paths, 1):
            img_name = Path(img_path).stem
            step_start = time.time()
            self.log(f"[SERVICE]   OCR image {i}/{len(image_paths)}: {img_name}")
            text = self.api.call_paddleocr(img_path)
            step_time = time.time() - step_start
            if text:
                self.log(f"[SERVICE]   ✓ OCR {img_name}: {len(text)} chars ({step_time:.1f}s)")
                self.log(f"[SERVICE]   Preview: {text[:100]}...")
                ocr_texts.append(text)
            else:
                self.log(f"[SERVICE]   ✗ OCR {img_name}: No text returned ({step_time:.1f}s)")

        if not ocr_texts:
            self.log("[SERVICE] ✗ Step 1 FAILED: No OCR text from any service image")
            return None
        self.log(f"[SERVICE] ✓ Step 1: OCR got text from {len(ocr_texts)}/{len(image_paths)} images")

        # Step 2: Filter each image's OCR output individually
        self.log(f"[SERVICE] Step 2/5: Filtering ({len(ocr_texts)} texts)...")
        filtered_results = []
        for i, ocr_text in enumerate(ocr_texts, 1):
            step_start = time.time()
            self.log(f"[SERVICE]   Filtering text {i}/{len(ocr_texts)}...")
            filtered = self.filtration.filter_service_text(ocr_text, provider)
            step_time = time.time() - step_start
            if filtered:
                filtered_results.append(filtered)
                self.log(f"[SERVICE]   ✓ Filter {i}: {len(filtered)} chars ({step_time:.1f}s)")
                self.log(f"[SERVICE]   Filtered: {filtered[:150]}...")
            else:
                self.log(f"[SERVICE]   ✗ Filter {i}: Returned nothing ({step_time:.1f}s)")

        if not filtered_results:
            self.log("[SERVICE] ✗ Step 2 FAILED: No filtered results from any image")
            return None
        self.log(f"[SERVICE] ✓ Step 2: Filtered {len(filtered_results)}/{len(ocr_texts)} texts")

        # Step 3: Combine filtered results
        self.log(f"[SERVICE] Step 3/5: Combining filtered results...")
        if len(filtered_results) == 1:
            combined = filtered_results[0]
            self.log(f"[SERVICE] ✓ Step 3: Single result, no combining needed ({len(combined)} chars)")
        else:
            combined = "COMBINED FROM MULTIPLE IMAGES:\n"
            for i, fr in enumerate(filtered_results):
                combined += f"Image {i+1}: {fr}\n"
            self.log(f"[SERVICE] ✓ Step 3: Combined {len(filtered_results)} results → {len(combined)} chars")
        self.log(f"[SERVICE]   Combined: {combined[:200]}...")

        # Step 4: Validate combined data
        step_start = time.time()
        self.log(f"[SERVICE] Step 4/5: Validating...")
        validated = self.validation.validate_service(combined, provider)
        step_time = time.time() - step_start
        if not validated:
            self.log(f"[SERVICE] ✗ Step 4 FAILED: Validation returned nothing ({step_time:.1f}s)")
            return None
        self.log(f"[SERVICE] ✓ Step 4: Validated {len(validated)} chars ({step_time:.1f}s)")
        self.log(f"[SERVICE]   Validated: {validated[:200]}...")

        # Step 5: Fill schema
        step_start = time.time()
        self.log(f"[SERVICE] Step 5/5: Filling ServiceData schema...")
        result = self.filling.fill_service(validated, provider)
        step_time = time.time() - step_start
        total_time = time.time() - process_start
        if result:
            self.log(f"[SERVICE] ✓ Step 5: Schema filled ({step_time:.1f}s)")
            self.log(f"[SERVICE]   NR: band={result.nr_band} arfcn={result.nr_arfcn} pci={result.nr_pci} rsrp={result.nr5g_rsrp}")
            self.log(f"[SERVICE]   LTE: band={result.lte_band} earfcn={result.lte_earfcn} pci={result.lte_pci} rsrp={result.lte_rsrp}")
            self.log(f"[SERVICE] ✅ {sector_name.upper()} COMPLETE in {total_time:.1f}s")
        else:
            self.log(f"[SERVICE] ✗ Step 5 FAILED: Schema filling failed ({step_time:.1f}s)")
            self.log(f"[SERVICE] ❌ {sector_name.upper()} FAILED after {total_time:.1f}s")

        return result
