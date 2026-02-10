"""
mapper.py — Maps extracted data to Excel cells using BOLD+RED expressions.
"""

import re
import json
import openpyxl
from typing import Any, List
from .config import ProcessingContext


class Mapper:
    def __init__(self, context: ProcessingContext):
        self.context = context

    def _normalize_name(self, s: str) -> str:
        return re.sub(r"[^0-9a-zA-Z]", "", s).lower()

    def resolve_expression(self, expr: str) -> Any:
        # Simple resolution logic similar to original, but using context dict
        data_map = self.context.to_dict()

        expr = expr.strip()
        m = re.match(r"^([A-Za-z_]\w*)(.*)$", expr)
        if not m:
            return None

        base_raw = m.group(1)
        rest = m.group(2) or ""

        # Normalize base key lookup
        base_key = None
        norm_map = {self._normalize_name(k): k for k in data_map.keys()}
        base_key = norm_map.get(self._normalize_name(base_raw))

        if not base_key:
            return None

        current_obj = data_map[base_key]

        # Parse brackets: ['key'] or ["key"]
        keys = re.findall(r"\[['\"]([^'\"]+)['\"]\]", rest)

        for k in keys:
            if isinstance(current_obj, dict):
                # Case insensitive lookup
                found = None
                for real_k in current_obj.keys():
                    if self._normalize_name(real_k) == self._normalize_name(k):
                        found = real_k
                        break
                if found:
                    current_obj = current_obj[found]
                else:
                    return None
            else:
                return None

        return current_obj

    def map_to_excel(self, xlsx_path: str):
        self.context.log("[MAPPER] Scanning workbook for BOLD+RED expressions...")
        try:
            wb = openpyxl.load_workbook(xlsx_path)
            sheet = wb.active

            cells_to_update = []

            # Limit scan range for performance
            # Assuming template won't exceed 20 columns or 200 rows for mapping references
            for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=1, max_col=20):
                for cell in row:
                    val = cell.value
                    if not val or not isinstance(val, str):
                        continue

                    # Check for Red Bold
                    # Standard Red is FF0000. Some Excel versions might vary slightly, but this is the tempdod1 standard.
                    font = cell.font
                    if not font or not font.bold:
                        continue
                    col = font.color
                    # Check RGB or theme color if applicable (mostly RGB for custom RED)
                    # We look for "FF0000" at the end of the hex string (ignoring alpha channel if present)
                    if not col or not col.rgb or (isinstance(col.rgb, str) and str(col.rgb).upper()[-6:] != "FF0000"):
                        # Double check if it's strictly red
                        continue

                    # Clean expression
                    expr = val.strip()
                    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
                        expr = expr[1:-1].strip()

                    # Resolve
                    resolved_val = self.resolve_expression(expr)

                    if resolved_val is not None:
                        cells_to_update.append((cell, resolved_val))
                    else:
                        # If resolution fails, we previously set to NULL.
                        # Now we just leave it or set to "NULL" string to indicate missing data.
                        cell.value = "NULL"
            
            # Apply updates
            count = 0
            for cell, val in cells_to_update:
                if isinstance(val, (dict, list)):
                    cell.value = json.dumps(val)
                else:
                    cell.value = val
                count += 1

            # Remove ALL images from the sheet to produce a clean data-only file
            # This is often desired in final reports to reduce file size
            sheet._images = []

            wb.save(xlsx_path)
            self.context.log(f"[MAPPER] Updated {count} cells in {xlsx_path}")

        except Exception as e:
            self.context.log(f"[ERROR] Mapping failed: {e}")
