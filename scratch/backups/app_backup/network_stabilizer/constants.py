"""
Constants, schema versions, honest terminology, and allowlists for Network Stabilizer.
"""

import os
import re

FEATURE_NAME = "Network Stabilizer"
FEATURE_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"

# Single compact state file inside the existing data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_FILE_PATH = os.path.join(DATA_DIR, "network_stabilizer_state.json")

# ── Grounded & Honest Terminology ──────────────────────────────────────
TERM_OBJECTIVE = "Reduce network-induced micro-stutters"
TERM_RESTORE_RESULT = "The rollback engine restores recorded feature-managed values where the original adapter, registry key, and Windows configuration still exist."
TERM_IDLE_RESOURCE = "Near-zero idle resource usage"
TERM_BUFFERBLOAT_DISCLAIMER = "Application-defined guidance threshold"
TERM_WINSOCK_RECOVERY = "Winsock reset is a recovery action requiring restart / manual intervention."

# ── Configuration Modes ────────────────────────────────────────────────
DNS_MODE_AUTO = "auto"
DNS_MODE_MANUAL = "manual"

# Valid change record statuses
STATUS_PROPOSED = "proposed"
STATUS_APPLIED = "applied"
STATUS_VERIFIED = "verified"
STATUS_REVERTED = "reverted"
STATUS_ROLLBACK_FAILED = "rollback_failed"
STATUS_SKIPPED = "skipped"

# ── Probe Boundaries & Metrics ─────────────────────────────────────────
DEFAULT_PROBE_COUNT = 20
DETAILED_PROBE_COUNT = 60
PROBE_TIMEOUT_SEC = 1.0

# Metric key identifiers
METRIC_AVG = "avg_ms"
METRIC_MEDIAN = "median_ms"
METRIC_P95 = "p95_ms"
METRIC_MAX = "max_ms"
METRIC_JITTER = "adjacent_jitter_ms"
METRIC_LOSS = "loss_pct"
METRIC_TIMEOUTS = "timeout_count"

# Regex for validating complete Windows Power Scheme GUID
REGEX_POWER_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Host input validation regex: IPv4 or valid domain/hostname (RFC 1123)
REGEX_IPV4 = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
REGEX_HOSTNAME = re.compile(r"^(?![0-9]+$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$")

# ── Windows Registry Paths ─────────────────────────────────────────────
REG_TCPIP_PARAMS = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
REG_TCPIP_INTERFACES = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
REG_MULTIMEDIA_PROFILE = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
REG_GAME_CONFIG_STORE = r"System\GameConfigStore"
REG_GAME_DVR_USER = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"

# ── Power Schemes (Complete Standard GUIDs) ────────────────────────────
POWER_SCHEME_HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
POWER_SCHEME_ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
POWER_SCHEME_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"

# ── Recommended Safe DNS Providers ────────────────────────────────────
DNS_PRESETS = {
    "Cloudflare": {
        "primary": "1.1.1.1",
        "secondary": "1.0.0.1",
        "description": "Lowest average lookup latency worldwide, private, gaming-optimized."
    },
    "Google": {
        "primary": "8.8.8.8",
        "secondary": "8.8.4.4",
        "description": "Global resilient Anycast infrastructure."
    },
    "Quad9": {
        "primary": "9.9.9.9",
        "secondary": "149.112.112.112",
        "description": "Anycast routing with malicious host filtering."
    }
}

# ── Bounded Targets ───────────────────────────────────────────────────
DEFAULT_PING_TARGETS = [
    {"id": "gateway", "label": "Default Gateway", "host": None, "type": "local"},
    {"id": "cloudflare", "label": "Cloudflare (1.1.1.1)", "host": "1.1.1.1", "type": "public"},
    {"id": "google", "label": "Google (8.8.8.8)", "host": "8.8.8.8", "type": "public"},
    {"id": "game", "label": "Custom Target", "host": "dynamodb.us-east-1.amazonaws.com", "type": "game"},
]

# ── Bufferbloat Latency Delta Guidance Thresholds ─────────────────────
BUFFERBLOAT_GRADES = [
    {"grade": "A+", "min_delta": 0, "max_delta": 5, "rating": "Stable", "color": "#00ff9f", "summary": "Negligible latency elevation under load."},
    {"grade": "A",  "min_delta": 5, "max_delta": 15, "rating": "Good", "color": "#38bdf8", "summary": "Low queue delay under traffic load."},
    {"grade": "B",  "min_delta": 15, "max_delta": 30, "rating": "Moderate Jitter", "color": "#fbbf24", "summary": "Noticeable latency jump under concurrent streams."},
    {"grade": "C",  "min_delta": 30, "max_delta": 60, "rating": "Bufferbloat Suspected", "color": "#f97316", "summary": "Elevated queueing delay. Router SQM recommended."},
    {"grade": "F",  "min_delta": 60, "max_delta": 99999, "rating": "High Bufferbloat", "color": "#f43f5e", "summary": "Heavy packet queue delay during bandwidth use."},
]

# ── Structured Root-Cause Diagnoses ───────────────────────────────────
NETWORK_DIAGNOSES = {
    "LOCAL_LAN_INSTABILITY": "Local Wi-Fi/LAN instability detected",
    "PACKET_LOSS_DETECTED": "Packet loss detected on game route",
    "BUFFERBLOAT_SUSPECTED": "Bufferbloat suspected under load",
    "EXTERNAL_ROUTE_INSTABILITY": "External route instability detected",
    "NO_NETWORK_INSTABILITY": "No significant network instability detected"
}

RENDER_DIAGNOSES = {
    "FRAME_TIME_SPIKES": "Frame-time spikes suspected",
    "CPU_GPU_LIMITATION": "CPU/GPU limitation suspected",
    "SHADER_STREAMING_STUTTER": "Shader or asset streaming stutter suspected",
    "INSUFFICIENT_RENDER_DATA": "Insufficient render data"
}

# ── Stutter Comparison Data ───────────────────────────────────────────
STUTTER_TYPES = {
    "network": {
        "title": "Network Stutter (Bufferbloat, Jitter, Packet Loss)",
        "symptoms": [
            "Ping fluctuates wildly (e.g. jumps from 25ms to 180ms)",
            "Rubberbanding, delayed hit registration, warping players",
            "FPS counter and frame-time stay smooth while character teleports",
            "Worse when others stream video, download large files, or on Wi-Fi"
        ],
        "causes": "Home router queue overflow (bufferbloat), Wi-Fi channel interference, ISP routing congestion.",
        "primary_fix": "Configure router SQM (CAKE/fq_codel) or switch to wired Ethernet."
    },
    "render": {
        "title": "Render Stutter (Frame-time spikes, DWM drops)",
        "symptoms": [
            "Visual micro-freezes accompanied by sudden FPS dips",
            "Frame-time graph displays erratic 20ms+ spikes",
            "Audio crackles or inputs momentarily drop during heavy shader compiles",
            "Happens regardless of whether online or in offline practice range"
        ],
        "causes": "GPU driver shader compile stalls, GameDVR background recording, CPU core parking.",
        "primary_fix": "Apply High Performance power plan, disable GameDVR, cap FPS 3 below refresh rate."
    }
}
