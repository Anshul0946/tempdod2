"""
config.py — Pydantic schemas and processing state management.
All constants live in constants.py. This file is schemas + state only.
"""

import time
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


# ─── Provider Config ───
class LLMProvider(BaseModel):
    name: str = "Default"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    api_key: str
    model: str


# ─── Data Schemas ───
# Strict Pydantic models for each test type

class ServiceData(BaseModel):
    nr_arfcn: Optional[float] = None
    nr_band: Optional[float] = None
    nr_pci: Optional[float] = None
    nr_bw: Optional[float] = None
    nr5g_rsrp: Optional[float] = None
    nr5g_rsrq: Optional[float] = None
    nr5g_sinr: Optional[float] = None
    lte_band: Optional[float] = None
    lte_earfcn: Optional[float] = None
    lte_pci: Optional[float] = None
    lte_bw: Optional[float] = None
    lte_rsrp: Optional[float] = None
    lte_rsrq: Optional[float] = None
    lte_sinr: Optional[float] = None


class SpeedTestData(BaseModel):
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    ping_ms: Optional[float] = None
    jitter_ms: Optional[float] = None


class VideoTestData(BaseModel):
    max_resolution: Optional[str] = None
    load_time_ms: Optional[float] = None
    buffering_percentage: Optional[float] = None


class VoiceCallData(BaseModel):
    phone_number: Optional[str] = None
    call_duration_seconds: Optional[float] = None
    call_status: Optional[str] = None
    time: Optional[str] = None


# ─── State Management ───
class ProcessingContext:
    """
    Holds the state for a single processing run.
    Replaces global variables.
    """
    def __init__(self):
        # Service Data by Sector
        self.alpha_service: ServiceData = ServiceData()
        self.beta_service: ServiceData = ServiceData()
        self.gamma_service: ServiceData = ServiceData()

        # Speed Tests (keyed by image name)
        self.alpha_speedtest: Dict[str, SpeedTestData] = {}
        self.beta_speedtest: Dict[str, SpeedTestData] = {}
        self.gamma_speedtest: Dict[str, SpeedTestData] = {}

        # Video Tests (keyed by image name)
        self.alpha_video: Dict[str, VideoTestData] = {}
        self.beta_video: Dict[str, VideoTestData] = {}
        self.gamma_video: Dict[str, VideoTestData] = {}

        # Voice Tests (keyed by image name)
        self.voice_test: Dict[str, VoiceCallData] = {}

        # Derived Data
        self.average: Dict[str, Dict[str, Optional[float]]] = {}

        # Operational State
        self.logs: List[str] = []
        self.temp_dir: str = ""

    def log(self, message: str):
        """Append to internal log list with timestamp."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(f"[{ts}] {message}")

    def set_service(self, sector: str, data: ServiceData):
        """Set service data for a sector."""
        setattr(self, f"{sector}_service", data)

    def add_speed(self, sector: str, image_name: str, data: SpeedTestData):
        """Add speed test result for a sector."""
        getattr(self, f"{sector}_speedtest")[image_name] = data

    def add_video(self, sector: str, image_name: str, data: VideoTestData):
        """Add video test result for a sector."""
        getattr(self, f"{sector}_video")[image_name] = data

    def add_voice(self, image_name: str, data: VoiceCallData):
        """Add voice test result."""
        self.voice_test[image_name] = data

    def to_dict(self):
        """Serialize entire context for expression resolution in mapper."""
        return {
            "alpha_service": self.alpha_service.model_dump(),
            "beta_service": self.beta_service.model_dump(),
            "gamma_service": self.gamma_service.model_dump(),
            "alpha_speedtest": {k: v.model_dump() for k, v in self.alpha_speedtest.items()},
            "beta_speedtest": {k: v.model_dump() for k, v in self.beta_speedtest.items()},
            "gamma_speedtest": {k: v.model_dump() for k, v in self.gamma_speedtest.items()},
            "alpha_video": {k: v.model_dump() for k, v in self.alpha_video.items()},
            "beta_video": {k: v.model_dump() for k, v in self.beta_video.items()},
            "gamma_video": {k: v.model_dump() for k, v in self.gamma_video.items()},
            "voice_test": {k: v.model_dump() for k, v in self.voice_test.items()},
            "average": self.average,
        }
