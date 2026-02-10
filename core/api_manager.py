"""
api_manager.py — Single source for all external API calls.
Two methods only: call_paddleocr() and call_reasoning().
"""

import base64
import json
import re
import time
import requests
from pathlib import Path
from typing import Optional

from .constants import OCR_URL, API_BASE
from .config import LLMProvider


class APIManager:
    """Handles all external API interactions."""

    def __init__(self, api_key: str, logger=None):
        self.api_key = api_key
        self.log = logger or (lambda msg: print(msg))

    # ─── PaddleOCR ───
    def call_paddleocr(self, image_path: str) -> Optional[str]:
        """
        Send image to PaddleOCR API, return extracted text as a single string.
        Returns None on failure.
        """
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            self.log(f"[OCR] Cannot read {image_path}: {e}")
            return None

        if len(image_b64) >= 180_000:
            self.log(f"[OCR] Image too large for PaddleOCR: {Path(image_path).name}")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        payload = {
            "input": [{
                "type": "image_url",
                "url": f"data:image/png;base64,{image_b64}",
            }]
        }

        # Two attempts with increasing timeout
        for attempt, timeout in enumerate([60, 120], 1):
            try:
                resp = requests.post(OCR_URL, headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()

                texts = []
                if "data" in data:
                    for item in data["data"]:
                        if "text_detections" in item:
                            for detection in item["text_detections"]:
                                if "text_prediction" in detection:
                                    text = detection["text_prediction"].get("text", "")
                                    if text:
                                        texts.append(text)

                if texts:
                    return "\n".join(texts)
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < 2:
                    self.log(f"[OCR] Timeout attempt {attempt}, retrying...")
                    time.sleep(2)
                    continue
                self.log(f"[OCR] Failed after retries: {e}")
                return None
            except requests.exceptions.HTTPError as e:
                self.log(f"[OCR] HTTP Error: {e}")
                return None
            except Exception as e:
                self.log(f"[OCR] Unexpected error: {e}")
                return None

        return None

    # ─── Reasoning LLM ───
    def call_reasoning(self, prompt: str, provider: LLMProvider) -> Optional[str]:
        """
        Send text prompt to reasoning model, return the extracted JSON string.
        Returns raw JSON string on success, None on failure.
        """
        url = f"{provider.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
        }

        for attempt, timeout in enumerate([60, 120], 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()

                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    return self._extract_json(content)
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < 2:
                    self.log(f"[REASONING] Timeout attempt {attempt}, retrying...")
                    time.sleep(2)
                    continue
                self.log(f"[REASONING] Failed after retries: {e}")
                return None
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    self.log(f"[REASONING] Client error {e.response.status_code}: {e}")
                    return None
                if attempt < 2:
                    time.sleep(2)
                    continue
                self.log(f"[REASONING] HTTP Error: {e}")
                return None
            except Exception as e:
                self.log(f"[REASONING] Unexpected error: {e}")
                return None

        return None

    def _extract_json(self, content: str) -> str:
        """Extract JSON object from model response content."""
        if not content:
            return "{}"

        # Try to find a JSON block {...}
        match = re.search(r'(\{.*\})', content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find a JSON array [...]
        match = re.search(r'(\[.*\])', content, re.DOTALL)
        if match:
            return match.group(1).strip()

        return content.strip()
