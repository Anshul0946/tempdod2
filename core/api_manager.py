"""
api_manager.py — Single source for all external API calls.
Two methods only: call_paddleocr() and call_reasoning().
Includes global rate limiting and detailed diagnostic logging.
"""

import base64
import json
import re
import time
import requests
import os
from pathlib import Path
from typing import Optional

from .constants import OCR_URL, API_BASE
from .config import LLMProvider


class APIManager:
    """Handles all external API interactions with global rate limiting."""

    # Global rate limiter: minimum seconds between ANY API call
    MIN_DELAY_SECONDS = 3

    def __init__(self, api_key: str, logger=None):
        self.api_key = api_key
        self.log = logger or (lambda msg: print(msg))
        self._last_call_time = 0.0  # Timestamp of last API call
        # ─── Diagnostic counters ───
        self._total_ocr_calls = 0
        self._total_reasoning_calls = 0
        self._total_retries = 0
        self._total_429s = 0
        self._total_api_time = 0.0

    def get_stats(self) -> dict:
        """Return diagnostic stats for the entire run."""
        return {
            "ocr_calls": self._total_ocr_calls,
            "reasoning_calls": self._total_reasoning_calls,
            "total_api_calls": self._total_ocr_calls + self._total_reasoning_calls,
            "total_retries": self._total_retries,
            "total_429_errors": self._total_429s,
            "total_api_time_seconds": round(self._total_api_time, 2),
        }

    def _wait_for_rate_limit(self):
        """
        Enforce a minimum delay between API calls.
        Prevents burst requests that trigger NVIDIA's 429 rate limits.
        """
        now = time.time()
        elapsed = now - self._last_call_time
        wait = self.MIN_DELAY_SECONDS - elapsed
        if wait > 0:
            self.log(f"[RATE LIMIT] Waiting {wait:.1f}s before next API call...")
            time.sleep(wait)
        self._last_call_time = time.time()

    def _resize_image(self, image_path: str, max_dim: int = 1024) -> Optional[str]:
        """
        Resize image to fit within max_dim, return base64 string.
        Helps prevent 'Image too large' errors from PaddleOCR.
        """
        try:
            from PIL import Image
            import io
            
            with Image.open(image_path) as img:
                original_size = img.size
                original_mode = img.mode
                
                # Convert to RGB if needed
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    self.log(f"[OCR] Converted {Path(image_path).name} from {original_mode} to RGB")
                
                # Resize if too large
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    self.log(f"[OCR] Resized {Path(image_path).name}: {original_size} → {new_size}")
                
                # Save to buffer
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
                self.log(f"[OCR] Image {Path(image_path).name}: {original_size}, base64 size: {len(b64_data)} chars")
                return b64_data
        except Exception as e:
            self.log(f"[OCR] ✗ Error resizing image {Path(image_path).name}: {type(e).__name__}: {e}")
            return None

    # ─── PaddleOCR ───
    def call_paddleocr(self, image_path: str) -> Optional[str]:
        """
        Send image to PaddleOCR API, return extracted text as a single string.
        Returns None on failure.
        """
        self._total_ocr_calls += 1
        call_num = self._total_ocr_calls
        img_name = Path(image_path).name
        file_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
        
        self.log(f"[OCR #{call_num}] Starting OCR for: {img_name} (file size: {file_size:,} bytes)")
        self._wait_for_rate_limit()
        
        call_start = time.time()
        image_b64 = self._resize_image(image_path)
        if not image_b64:
            self.log(f"[OCR #{call_num}] ✗ FAILED: Could not encode image {img_name}")
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
                self.log(f"[OCR #{call_num}] Sending request (attempt {attempt}/{max_retries})...")
                request_start = time.time()
                resp = requests.post(OCR_URL, headers=headers, json=payload, timeout=60)
                request_time = time.time() - request_start
                
                self.log(f"[OCR #{call_num}] Response: HTTP {resp.status_code} in {request_time:.1f}s")
                
                # Handle 429 explicitly
                if resp.status_code == 429:
                    self._total_429s += 1
                    self._total_retries += 1
                    wait = base_delay * (2 ** (attempt - 1))
                    self.log(f"[OCR #{call_num}] ⚠ Rate limit hit (429 #{self._total_429s}). Retrying in {wait}s...")
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

                total_time = time.time() - call_start
                self._total_api_time += total_time
                
                if texts:
                    result = "\n".join(texts)
                    self.log(f"[OCR #{call_num}] ✓ Success: {len(texts)} text blocks, {len(result)} total chars in {total_time:.1f}s")
                    self.log(f"[OCR #{call_num}] Preview: {result[:150]}...")
                    return result
                
                self.log(f"[OCR #{call_num}] ✗ No text detected in image {img_name} (response had no text_detections)")
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                self._total_retries += 1
                self.log(f"[OCR #{call_num}] ⚠ Connection error: {type(e).__name__}: {e}")
                self.log(f"[OCR #{call_num}] Retrying ({attempt}/{max_retries})...")
                time.sleep(2)
                continue
            except requests.exceptions.HTTPError as e:
                self.log(f"[OCR #{call_num}] ✗ HTTP Error {resp.status_code}: {e}")
                if resp.status_code != 429: 
                    try:
                        self.log(f"[OCR #{call_num}] Response body: {resp.text[:300]}")
                    except:
                        pass
                    return None
            except Exception as e:
                self.log(f"[OCR #{call_num}] ✗ Unexpected error: {type(e).__name__}: {e}")
                return None

        total_time = time.time() - call_start
        self._total_api_time += total_time
        self.log(f"[OCR #{call_num}] ✗ FAILED after {max_retries} retries ({total_time:.1f}s total)")
        return None

    # ─── Reasoning LLM ───
    def call_reasoning(self, prompt: str, provider: LLMProvider) -> Optional[str]:
        """
        Send text prompt to reasoning model, return the extracted JSON string.
        Returns raw JSON string on success, None on failure.
        """
        self._total_reasoning_calls += 1
        call_num = self._total_reasoning_calls
        prompt_len = len(prompt)
        
        self.log(f"[REASONING #{call_num}] Starting (model: {provider.model}, prompt: {prompt_len:,} chars)")
        self._wait_for_rate_limit()
        
        call_start = time.time()
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
                self.log(f"[REASONING #{call_num}] Sending request (attempt {attempt}/{max_retries})...")
                request_start = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                request_time = time.time() - request_start

                self.log(f"[REASONING #{call_num}] Response: HTTP {resp.status_code} in {request_time:.1f}s")

                # Handle 429 explicitly
                if resp.status_code == 429:
                    self._total_429s += 1
                    self._total_retries += 1
                    wait = base_delay * (2 ** (attempt - 1))
                    self.log(f"[REASONING #{call_num}] ⚠ Rate limit hit (429 #{self._total_429s}). Retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                total_time = time.time() - call_start
                self._total_api_time += total_time

                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    result = self._extract_json(content)
                    self.log(f"[REASONING #{call_num}] ✓ Success: {len(result)} chars in {total_time:.1f}s")
                    self.log(f"[REASONING #{call_num}] Preview: {result[:200]}...")
                    return result
                
                self.log(f"[REASONING #{call_num}] ✗ No choices in response")
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                self._total_retries += 1
                self.log(f"[REASONING #{call_num}] ⚠ Connection error: {type(e).__name__}: {e}")
                self.log(f"[REASONING #{call_num}] Retrying ({attempt}/{max_retries})...")
                time.sleep(2)
                continue
            except requests.exceptions.HTTPError as e:
                self.log(f"[REASONING #{call_num}] ✗ HTTP Error {resp.status_code}: {e}")
                if resp.status_code != 429:
                    try:
                        self.log(f"[REASONING #{call_num}] Response body: {resp.text[:300]}")
                    except:
                        pass
                    return None
            except Exception as e:
                self.log(f"[REASONING #{call_num}] ✗ Unexpected error: {type(e).__name__}: {e}")
                return None

        total_time = time.time() - call_start
        self._total_api_time += total_time
        self.log(f"[REASONING #{call_num}] ✗ FAILED after {max_retries} retries ({total_time:.1f}s total)")
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
