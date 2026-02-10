"""
constants.py — All fixed, never-changing values for the 5G DOD processor.
Column ranges, image indices, sector names, parameter metadata, OCR label mappings.
"""

# ─── API Endpoints ───
API_BASE = "https://integrate.api.nvidia.com/v1"
OCR_URL = "https://ai.api.nvidia.com/v1/cv/baidu/paddleocr"
REASONING_MODEL_DEFAULT = "deepseek-ai/deepseek-v3.2"

# ─── Sector Definitions ───
SECTORS = ["alpha", "beta", "gamma"]

# Column ranges for sector classification (Excel column index, 0-based)
SECTOR_COLUMN_RANGES = {
    "alpha":     (0, 3),    # Columns A-D
    "beta":      (4, 7),    # Columns E-H
    "gamma":     (8, 11),   # Columns I-L
    "voicetest": (12, 17),  # Columns M-R
}

# ─── Image Classification by suffix number ───
# For each sector (alpha/beta/gamma), images are numbered 1-8
IMAGE_ROLES = {
    1: "service",
    2: "service",
    3: "speed_test",
    4: "speed_test",
    5: "speed_test",
    6: "speed_test",
    7: "speed_test",
    8: "video_test",
}

# Service images that must be combined before validation
SERVICE_IMAGE_NUMBERS = [1, 2]

# ─── Parameter Metadata for Validation Agent ───

SERVICE_PARAMS = {
    "nr_arfcn": {
        "type": "int",
        "range": (0, 3279165),
        "unit": None,
        "desc": "NR Absolute Radio Frequency Channel Number",
        "sample": 632736,
    },
    "nr_band": {
        "type": "int",
        "range": (1, 999),
        "unit": None,
        "desc": "NR frequency band number",
        "sample": 977,
    },
    "nr_pci": {
        "type": "int",
        "range": (0, 1007),
        "unit": None,
        "desc": "NR Physical Cell ID",
        "sample": 966,
    },
    "nr_bw": {
        "type": "int",
        "range": (5, 100),
        "unit": "MHz",
        "desc": "NR channel bandwidth",
        "sample": 70,
    },
    "nr5g_rsrp": {
        "type": "float",
        "range": (-156, -31),
        "unit": "dBm",
        "desc": "NR Reference Signal Received Power (always negative)",
        "sample": -93,
    },
    "nr5g_rsrq": {
        "type": "float",
        "range": (-43, 20),
        "unit": "dB",
        "desc": "NR Reference Signal Received Quality (usually negative)",
        "sample": -11,
    },
    "nr5g_sinr": {
        "type": "float",
        "range": (-23, 400),
        "unit": "dB",
        "desc": "NR Signal to Interference plus Noise Ratio",
        "sample": 230,
    },
    "lte_band": {
        "type": "int",
        "range": (1, 88),
        "unit": None,
        "desc": "LTE frequency band number (often shown as 'T2' meaning Band 2)",
        "sample": 2,
    },
    "lte_earfcn": {
        "type": "int",
        "range": (0, 262143),
        "unit": None,
        "desc": "LTE E-UTRA Absolute Radio Frequency Channel Number",
        "sample": 5110,
    },
    "lte_pci": {
        "type": "int",
        "range": (0, 503),
        "unit": None,
        "desc": "LTE Physical Cell ID",
        "sample": 320,
    },
    "lte_bw": {
        "type": "int",
        "range": (1, 20),
        "unit": "MHz",
        "desc": "LTE channel bandwidth",
        "sample": 10,
    },
    "lte_rsrp": {
        "type": "float",
        "range": (-140, -44),
        "unit": "dBm",
        "desc": "LTE Reference Signal Received Power (always negative)",
        "sample": -73,
    },
    "lte_rsrq": {
        "type": "float",
        "range": (-34, 3),
        "unit": "dB",
        "desc": "LTE Reference Signal Received Quality (usually negative)",
        "sample": -12,
    },
    "lte_sinr": {
        "type": "float",
        "range": (-23, 40),
        "unit": "dB",
        "desc": "LTE Signal to Noise and Interference Ratio",
        "sample": 106,
    },
}

SPEED_TEST_PARAMS = {
    "download_mbps": {
        "type": "float",
        "range": (0, 10000),
        "unit": "Mbps",
        "desc": "Download speed in megabits per second",
        "sample": 382,
    },
    "upload_mbps": {
        "type": "float",
        "range": (0, 5000),
        "unit": "Mbps",
        "desc": "Upload speed in megabits per second",
        "sample": 95.2,
    },
    "ping_ms": {
        "type": "float",
        "range": (0, 3000),
        "unit": "ms",
        "desc": "Round-trip latency in milliseconds",
        "sample": 44,
    },
    "jitter_ms": {
        "type": "float",
        "range": (0, 500),
        "unit": "ms",
        "desc": "Latency variation in milliseconds",
        "sample": 7,
    },
}

VIDEO_TEST_PARAMS = {
    "max_resolution": {
        "type": "str",
        "allowed": ["360p", "480p", "720p", "1080p", "1440p", "2160p", "4K"],
        "desc": "Maximum video resolution achieved",
        "sample": "2160p",
    },
    "load_time_ms": {
        "type": "float",
        "range": (0, 30000),
        "unit": "ms",
        "desc": "Video load/buffer time in milliseconds",
        "sample": 985,
    },
    "buffering_percentage": {
        "type": "float",
        "range": (0, 100),
        "unit": "%",
        "desc": "Buffering percentage during playback",
        "sample": 0,
    },
}

VOICE_TEST_PARAMS = {
    "phone_number": {
        "type": "str",
        "desc": "Phone number called, format: (xxx) xxx-xxxx",
        "sample": "(312) 774-3128",
    },
    "call_duration_seconds": {
        "type": "float",
        "range": (0, 36000),
        "unit": "seconds",
        "desc": "Call duration in seconds (OCR shows as MM:SS like 00:12 = 12 seconds)",
        "sample": 12,
    },
    "call_status": {
        "type": "str",
        "allowed": ["Connected", "Completed", "Failed", "Ringing", "Dialing"],
        "desc": "Call status",
        "sample": "Connected",
    },
    "time": {
        "type": "str",
        "desc": "Timestamp shown on call screen (HH:MM format)",
        "sample": "00:12",
    },
}

# ─── OCR Label → Schema Field Mapping ───
# Maps raw OCR parameter names to schema field names for service data
SERVICE_OCR_LABELS = {
    # NR (5G) parameters
    "NR_ARFCN": "nr_arfcn",
    "NR ARFCN": "nr_arfcn",
    "NR_BAND": "nr_band",
    "NR BAND": "nr_band",
    "NR_PCI": "nr_pci",
    "NR PCI": "nr_pci",
    "NR_BW": "nr_bw",
    "NR BW": "nr_bw",
    "NRSG_RSRP": "nr5g_rsrp",
    "NR_ANT MAX RSRP": "nr5g_rsrp",
    "NR_ANT MIN RSRP": "nr5g_rsrp",  # fallback if MAX not found
    "NRSG_RSRQ": "nr5g_rsrq",
    "NRSG_SINR": "nr5g_sinr",
    # LTE (4G) parameters
    "BAND": "lte_band",
    "EARFCN": "lte_earfcn",
    "PCI": "lte_pci",
    "BW": "lte_bw",
    "RSRP": "lte_rsrp",
    "RSRQ": "lte_rsrq",
    "SNR": "lte_sinr",
}

SPEED_OCR_LABELS = {
    "Download Mbps": "download_mbps",
    "Download": "download_mbps",
    "Upload Mbps": "upload_mbps",
    "Upload": "upload_mbps",
    "Ping": "ping_ms",
    "Jitter": "jitter_ms",
}

VIDEO_OCR_LABELS = {
    "MAX RESOLUTION": "max_resolution",
    "Max Resolution": "max_resolution",
    "Load Time": "load_time_ms",
    "Buffering": "buffering_percentage",
}

VOICE_OCR_LABELS = {
    # Voice test has no explicit labels in the OCR output
    # The phone number and duration are inferred from format
}

# ─── Common OCR Misread Patterns ───
OCR_CHAR_CORRECTIONS = {
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "S": "5",
    "s": "5",
    "B": "8",
    "g": "9",
    "G": "6",
    "Z": "2",
    "z": "2",
}

# ─── Sample OCR Output for Reference ───
# These are used by agents to understand expected data format

SAMPLE_SERVICE_OCR = """SCGF Type:
NR_BAND: 977
NR_LCDRX: Active
NR_DL Scheduling: 0.60
NR_BLER: 0.00
NR_BW: 70
NR_SB Status: LTE+NR
NR_ANT MAX RSRP: -89
NR_ANT MIN RSRP: -95
NRSG_RSRP: -93
NRSG_SINR: 230
NRSG_RSRQ: -11
NR_SSB index: 0
NR_ARFCN: 632736
NR_PCI: 966
BAND: T2
BW: 10
EARFCN: 5110
PCI: 320
RSRP: -73
RSRQ: -12
SNR: 106"""

SAMPLE_SPEED_OCR = """5:58
5G+
SPEEDTEST
Download Mbps: 382
Upload Mbps: 95.2
Ping: 44 ms
Jitter: 7 ms"""

SAMPLE_VIDEO_OCR = """6:00
5G+
SPEEDTEST
MAX RESOLUTION
2160p
Load Time: 985 ms
Buffering"""

SAMPLE_VOICE_OCR = """00:12
(312) 774-3128
Chicago, IL
Speaker
Mute
Keypad"""
