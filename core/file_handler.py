"""
file_handler.py — Extracts images from Excel and classifies them by sector + type.
Returns a structured dictionary so downstream processors never mix images.
"""

import os
import io
import openpyxl
from PIL import Image
from typing import Dict, List

from .config import ProcessingContext
from .constants import SECTOR_COLUMN_RANGES, IMAGE_ROLES


class FileHandler:
    def __init__(self, context: ProcessingContext):
        self.context = context

    def setup_temp_dir(self, temp_dir: str):
        self.context.temp_dir = temp_dir
        os.makedirs(os.path.join(temp_dir, "images"), exist_ok=True)

    def extract_and_classify(self, xlsx_path: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Extract images from Excel and classify them into a structured dict:
        {
            "alpha": {
                "service": [path1, path2],
                "speed_test": [path3, path4, ...],
                "video_test": [path8],
            },
            "beta": { ... },
            "gamma": { ... },
            "voicetest": {
                "voice": [path1, ...]
            },
        }
        
        Classification is done at extraction time using column position + image number.
        This guarantees no downstream mixing.
        """
        self.context.log(f"Analyzing template file: {xlsx_path}")

        try:
            wb = openpyxl.load_workbook(xlsx_path)
            sheet = wb.active
        except Exception as e:
            self.context.log(f"[ERROR] Could not open Excel file: {e}")
            return {}

        images = getattr(sheet, "_images", [])
        if not images:
            self.context.log("[WARN] No images found in workbook.")
            return {}

        # Sort images by location (top-left to bottom-right)
        images_with_locations = []
        for image in images:
            try:
                row = image.anchor._from.row + 1
                col = image.anchor._from.col
            except Exception:
                row, col = 0, 0
            images_with_locations.append({"image": image, "row": row, "col": col})

        images_sorted = sorted(images_with_locations, key=lambda i: (i["row"], i["col"]))

        # Initialize classified structure
        classified = {
            "alpha": {"service": [], "speed_test": [], "video_test": []},
            "beta": {"service": [], "speed_test": [], "video_test": []},
            "gamma": {"service": [], "speed_test": [], "video_test": []},
            "voicetest": {"voice": []},
        }

        output_folder = os.path.join(self.context.temp_dir, "images")
        counters = {"alpha": 0, "beta": 0, "gamma": 0, "voicetest": 0, "unknown": 0}

        for itm in images_sorted:
            col_index = itm["col"]

            # Determine sector from column position
            sector = self._classify_sector(col_index)
            if sector == "unknown":
                counters["unknown"] += 1
                self.context.log(f"[WARN] Unknown sector for image at col {col_index}, skipping.")
                continue

            counters[sector] += 1
            img_number = counters[sector]

            # Determine image type
            if sector == "voicetest":
                image_type = "voice"
                filename = f"voicetest_voice_{img_number}.png"
            else:
                image_type = IMAGE_ROLES.get(img_number, "unknown")
                if image_type == "unknown":
                    self.context.log(f"[WARN] {sector} image #{img_number} has no defined role, skipping.")
                    continue
                filename = f"{sector}_{image_type}_{img_number}.png"

            out_path = os.path.join(output_folder, filename)

            # Save image
            try:
                img_data = itm["image"]._data()
                pil = Image.open(io.BytesIO(img_data))
                pil.save(out_path, "PNG")

                # Add to classified structure
                classified[sector][image_type].append(out_path)
                self.context.log(f"  ✓ {filename} → {sector}/{image_type}")

            except Exception as e:
                self.context.log(f"[ERROR] Failed to save {filename}: {e}")

        # Log summary
        for sector, types in classified.items():
            for itype, paths in types.items():
                if paths:
                    self.context.log(f"  [{sector.upper()}] {itype}: {len(paths)} images")

        return classified

    def _classify_sector(self, col_index: int) -> str:
        """Classify column index into sector name."""
        for sector, (lo, hi) in SECTOR_COLUMN_RANGES.items():
            if lo <= col_index <= hi:
                return sector
        return "unknown"

    def get_image_path(self, _):
        """Deprecated method stub to prevent crashes if called during refactor."""
        return None
