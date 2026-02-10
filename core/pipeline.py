"""
pipeline.py — Main orchestrator for the 5G DOD processing workflow.
Replaces evaluator.py. Wires together file handling, processors, and mapping.
"""

from pathlib import Path
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
        self.api = APIManager(api_key)
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
        self.context.log("=" * 50)
        self.context.log("STARTING PIPELINE")
        self.context.log(f"Reasoning Model: {reasoning_model}")
        self.context.log("=" * 50)

        # Provider config
        provider = LLMProvider(
            name="Reasoning",
            api_key=self.api.api_key,
            model=reasoning_model
        )

        # 1. Extract & Classify
        self.context.log("\n[PHASE 1] Extracting Images...")
        classified = self.file_handler.extract_and_classify(xlsx_path)

        # 2. Process Sectors (Alpha, Beta, Gamma)
        self.context.log("\n[PHASE 2] Processing Sectors...")
        
        for sector in ["alpha", "beta", "gamma"]:
            if sector not in classified:
                continue

            # A. Service Images
            service_imgs = classified[sector].get("service", [])
            if service_imgs:
                data = self.service_processor.process(service_imgs, provider)
                if data:
                    self.context.set_service(sector, data)

            # B. Speed Tests
            speed_imgs = classified[sector].get("speed_test", [])
            for img_path in speed_imgs:
                name = Path(img_path).stem
                data = self.speed_processor.process(img_path, provider)
                if data:
                    self.context.add_speed(sector, name, data)

            # C. Video Tests
            video_imgs = classified[sector].get("video_test", [])
            for img_path in video_imgs:
                name = Path(img_path).stem
                data = self.video_processor.process(img_path, provider)
                if data:
                    self.context.add_video(sector, name, data)

        # 3. Process Voice Tests
        self.context.log("\n[PHASE 3] Processing Voice Tests...")
        voice_imgs = classified.get("voicetest", {}).get("voice", [])
        for img_path in voice_imgs:
            name = Path(img_path).stem
            data = self.voice_processor.process(img_path, provider)
            if data:
                self.context.add_voice(name, data)

        # 4. Map to Excel
        self.context.log("\n[PHASE 4] Mapping to Excel...")
        self.mapper.map_to_excel(xlsx_path)

        self.context.log("=" * 50)
        self.context.log("PIPELINE COMPLETE")
        self.context.log("=" * 50)

        return xlsx_path
