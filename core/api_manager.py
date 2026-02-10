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

    def _resize_image(self, image_path: str, max_dim: int = 1024) -> Optional[str]:
        """
        Resize image to fit within max_dim, return base64 string.
        Helps prevent 'Image too large' errors from PaddleOCR.
        """
        try:
            from PIL import Image
            import io
            
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Resize if too large
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    self.log(f"[OCR] Resized large image {Path(image_path).name} to {new_size}")
                
                # Save to buffer
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            self.log(f"[OCR] Error resizing image: {e}")
            return None

    # ─── PaddleOCR ───
    def call_paddleocr(self, image_path: str) -> Optional[str]:
        """
        Send image to PaddleOCR API, return extracted text as a single string.
        Returns None on failure.
        """
        image_b64 = self._resize_image(image_path)
        if not image_b64:
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

        # Exponential backoff for 429s
        max_retries = 5
        base_delay = 2

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(OCR_URL, headers=headers, json=payload, timeout=60)
                
                # Handle 429 explicitly
                if resp.status_code == 429:
                    wait = base_delay * (2 ** (attempt - 1))
                    self.log(f"[OCR] Rate limit hit (429). Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                
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
                self.log(f"[OCR] Connection error: {e}. Retrying ({attempt}/{max_retries})...")
                time.sleep(2)
                continue
            except requests.exceptions.HTTPError as e:
                self.log(f"[OCR] HTTP Error: {e}")
                if resp.status_code != 429: 
                    return None
            except Exception as e:
                self.log(f"[OCR] Unexpected error: {e}")
                return None

        self.log(f"[OCR] Failed after {max_retries} retries.")
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

        # Exponential backoff for 429s
        max_retries = 5
        base_delay = 2

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)

                # Handle 429 explicitly
                if resp.status_code == 429:
                    wait = base_delay * (2 ** (attempt - 1))
                    self.log(f"[REASONING] Rate limit hit (429). Retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    return self._extract_json(content)
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                self.log(f"[REASONING] Connection error: {e}. Retrying ({attempt}/{max_retries})...")
                time.sleep(2)
                continue
            except requests.exceptions.HTTPError as e:
                self.log(f"[REASONING] HTTP Error: {e}")
                if resp.status_code != 429:
                    return None
            except Exception as e:
                self.log(f"[REASONING] Unexpected error: {e}")
                return None

        self.log(f"[REASONING] Failed after {max_retries} retries.")
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
