"""
pipeline.py — Main orchestrator for the 5G DOD processing workflow.
Replaces evaluator.py. Wires together file handling, processors, and mapping.
Includes detailed diagnostic logging for timing, progress, and error tracking.
"""

from pathlib import Path
import time
from .config import ProcessingContext, LLMProvider
from .api_manager import APIManager
from .file_handler import FileHandler
from .mapper import Mapper
from .processors.service_processor import ServiceProcessor
from .processors.speed_processor import SpeedProcessor
from .processors.video_processor import VideoProcessor
from .processors.voice_processor import VoiceProcessor


class Pipeline:
    """
    Orchestrates the linear processing flow:
    1. Extract & Classify Images
    2. Process Service Images (Alpha, Beta, Gamma)
    3. Process Speed Tests
    4. Process Video Tests
    5. Process Voice Tests
    6. Map Results to Excel
    """

    def __init__(self, context: ProcessingContext, api_key: str):
        self.context = context
        self.api = APIManager(api_key, context.log)
        self.file_handler = FileHandler(context)
        self.mapper = Mapper(context)

        # Initialize processors
        self.service_processor = ServiceProcessor(self.api, context.log)
        self.speed_processor = SpeedProcessor(self.api, context.log)
        self.video_processor = VideoProcessor(self.api, context.log)
        self.voice_processor = VoiceProcessor(self.api, context.log)

    def run(self, xlsx_path: str, reasoning_model: str) -> str:
        """
        Run the full processing pipeline.
        Returns the path to the processed Excel file.
        """
        pipeline_start = time.time()

        self.context.log("=" * 60)
        self.context.log("🚀 STARTING PIPELINE")
        self.context.log(f"   File: {Path(xlsx_path).name}")
        self.context.log(f"   Reasoning Model: {reasoning_model}")
        self.context.log(f"   Rate Limit: {self.api.MIN_DELAY_SECONDS}s between API calls")
        self.context.log("=" * 60)

        # Provider config
        provider = LLMProvider(
            name="Reasoning",
            api_key=self.api.api_key,
            model=reasoning_model
        )

        # ─── PHASE 1: Extract & Classify ───
        phase1_start = time.time()
        self.context.log("\n[PHASE 1] Extracting & Classifying Images...")
        classified = self.file_handler.extract_and_classify(xlsx_path)
        phase1_time = time.time() - phase1_start

        # Log classification summary
        total_images = 0
        self.context.log(f"\n[PHASE 1] ✓ Complete in {phase1_time:.1f}s — Classification Summary:")
        for sector, types in classified.items():
            for img_type, imgs in types.items():
                count = len(imgs) if isinstance(imgs, list) else 0
                total_images += count
                if count > 0:
                    self.context.log(f"   {sector}/{img_type}: {count} images")
                    for img in imgs:
                        self.context.log(f"      → {Path(img).name}")
        self.context.log(f"   TOTAL: {total_images} images to process")

        # ─── Counters for summary ───
        results_summary = {
            "service_ok": 0, "service_fail": 0,
            "speed_ok": 0, "speed_fail": 0,
            "video_ok": 0, "video_fail": 0,
            "voice_ok": 0, "voice_fail": 0,
        }

        # ─── PHASE 2: Process Sectors ───
        phase2_start = time.time()
        self.context.log(f"\n{'='*60}")
        self.context.log("[PHASE 2] Processing Sectors (Alpha, Beta, Gamma)...")
        self.context.log(f"{'='*60}")
        
        for sector in ["alpha", "beta", "gamma"]:
            if sector not in classified:
                self.context.log(f"\n[PHASE 2] Skipping {sector.upper()} — no images found")
                continue

            sector_start = time.time()
            self.context.log(f"\n{'─'*50}")
            self.context.log(f"[SECTOR] ▶ {sector.upper()}")
            self.context.log(f"{'─'*50}")

            # A. Service Images
            service_imgs = classified[sector].get("service", [])
            if service_imgs:
                self.context.log(f"\n[{sector.upper()}] Processing {len(service_imgs)} service images...")
                svc_start = time.time()
                data = self.service_processor.process(service_imgs, provider)
                svc_time = time.time() - svc_start
                if data:
                    self.context.set_service(sector, data)
                    results_summary["service_ok"] += 1
                    self.context.log(f"[{sector.upper()}] ✓ Service data saved ({svc_time:.1f}s)")
                else:
                    results_summary["service_fail"] += 1
                    self.context.log(f"[{sector.upper()}] ✗ Service processing FAILED ({svc_time:.1f}s)")
            else:
                self.context.log(f"[{sector.upper()}] No service images")

            # B. Speed Tests
            speed_imgs = classified[sector].get("speed_test", [])
            if speed_imgs:
                self.context.log(f"\n[{sector.upper()}] Processing {len(speed_imgs)} speed test images...")
            for i, img_path in enumerate(speed_imgs, 1):
                name = Path(img_path).stem
                self.context.log(f"\n[{sector.upper()}] Speed test {i}/{len(speed_imgs)}: {name}")
                spd_start = time.time()
                data = self.speed_processor.process(img_path, provider)
                spd_time = time.time() - spd_start
                if data:
                    self.context.add_speed(sector, name, data)
                    results_summary["speed_ok"] += 1
                    self.context.log(f"[{sector.upper()}] ✓ Speed {name} saved ({spd_time:.1f}s)")
                else:
                    results_summary["speed_fail"] += 1
                    self.context.log(f"[{sector.upper()}] ✗ Speed {name} FAILED ({spd_time:.1f}s)")

            # C. Video Tests
            video_imgs = classified[sector].get("video_test", [])
            if video_imgs:
                self.context.log(f"\n[{sector.upper()}] Processing {len(video_imgs)} video test images...")
            for i, img_path in enumerate(video_imgs, 1):
                name = Path(img_path).stem
                self.context.log(f"\n[{sector.upper()}] Video test {i}/{len(video_imgs)}: {name}")
                vid_start = time.time()
                data = self.video_processor.process(img_path, provider)
                vid_time = time.time() - vid_start
                if data:
                    self.context.add_video(sector, name, data)
                    results_summary["video_ok"] += 1
                    self.context.log(f"[{sector.upper()}] ✓ Video {name} saved ({vid_time:.1f}s)")
                else:
                    results_summary["video_fail"] += 1
                    self.context.log(f"[{sector.upper()}] ✗ Video {name} FAILED ({vid_time:.1f}s)")

            sector_time = time.time() - sector_start
            self.context.log(f"\n[SECTOR] ◀ {sector.upper()} complete in {sector_time:.1f}s")

        phase2_time = time.time() - phase2_start

        # ─── PHASE 3: Voice Tests ───
        phase3_start = time.time()
        self.context.log(f"\n{'='*60}")
        self.context.log("[PHASE 3] Processing Voice Tests...")
        self.context.log(f"{'='*60}")
        voice_imgs = classified.get("voicetest", {}).get("voice", [])
        if voice_imgs:
            self.context.log(f"[PHASE 3] Found {len(voice_imgs)} voice test images")
        else:
            self.context.log("[PHASE 3] No voice test images found")
        for i, img_path in enumerate(voice_imgs, 1):
            name = Path(img_path).stem
            self.context.log(f"\n[VOICE] Voice test {i}/{len(voice_imgs)}: {name}")
            voc_start = time.time()
            data = self.voice_processor.process(img_path, provider)
            voc_time = time.time() - voc_start
            if data:
                self.context.add_voice(name, data)
                results_summary["voice_ok"] += 1
                self.context.log(f"[VOICE] ✓ Voice {name} saved ({voc_time:.1f}s)")
            else:
                results_summary["voice_fail"] += 1
                self.context.log(f"[VOICE] ✗ Voice {name} FAILED ({voc_time:.1f}s)")
        phase3_time = time.time() - phase3_start

        # ─── PHASE 4: Map to Excel ───
        phase4_start = time.time()
        self.context.log(f"\n{'='*60}")
        self.context.log("[PHASE 4] Mapping Results to Excel...")
        self.context.log(f"{'='*60}")
        self.mapper.map_to_excel(xlsx_path)
        phase4_time = time.time() - phase4_start

        # ─── FINAL SUMMARY ───
        total_time = time.time() - pipeline_start
        api_stats = self.api.get_stats()

        total_ok = sum(v for k, v in results_summary.items() if k.endswith("_ok"))
        total_fail = sum(v for k, v in results_summary.items() if k.endswith("_fail"))

        self.context.log(f"\n{'='*60}")
        self.context.log("🏁 PIPELINE COMPLETE — SUMMARY")
        self.context.log(f"{'='*60}")
        self.context.log(f"")
        self.context.log(f"   ⏱  Total Time:     {total_time:.1f}s ({total_time/60:.1f} min)")
        self.context.log(f"   📊 Phase Timing:")
        self.context.log(f"      Phase 1 (Extract):  {phase1_time:.1f}s")
        self.context.log(f"      Phase 2 (Sectors):  {phase2_time:.1f}s")
        self.context.log(f"      Phase 3 (Voice):    {phase3_time:.1f}s")
        self.context.log(f"      Phase 4 (Mapping):  {phase4_time:.1f}s")
        self.context.log(f"")
        self.context.log(f"   📈 Processing Results:")
        self.context.log(f"      Service: {results_summary['service_ok']} ok / {results_summary['service_fail']} failed")
        self.context.log(f"      Speed:   {results_summary['speed_ok']} ok / {results_summary['speed_fail']} failed")
        self.context.log(f"      Video:   {results_summary['video_ok']} ok / {results_summary['video_fail']} failed")
        self.context.log(f"      Voice:   {results_summary['voice_ok']} ok / {results_summary['voice_fail']} failed")
        self.context.log(f"      TOTAL:   {total_ok} ok / {total_fail} failed")
        self.context.log(f"")
        self.context.log(f"   🌐 API Stats:")
        self.context.log(f"      OCR calls:       {api_stats['ocr_calls']}")
        self.context.log(f"      Reasoning calls: {api_stats['reasoning_calls']}")
        self.context.log(f"      Total API calls: {api_stats['total_api_calls']}")
        self.context.log(f"      Total retries:   {api_stats['total_retries']}")
        self.context.log(f"      Total 429 errors:{api_stats['total_429_errors']}")
        self.context.log(f"      API time:        {api_stats['total_api_time_seconds']}s")
        self.context.log(f"{'='*60}")

        return xlsx_path
