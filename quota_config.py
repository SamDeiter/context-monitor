"""
Quota Configuration
Definitions for Antigravity tiers and their limits.
"""
from pathlib import Path

TIERS = {
    "Free": {
        "label": "Free (Individual)",
        "limit": 50,
        "window_seconds": 7 * 24 * 3600, # 7 Days
        "ancillary_limit": 100, # Flow/Whisk Credits
        "reset_type": "rolling" 
    },
    "Pro": {
        "label": "Google AI Pro",
        "limit": 100, # Estimated "High"
        "window_seconds": 5 * 3600, # 5 Hours
        "ancillary_limit": 1000,
        "reset_type": "rolling"
    },
    "Ultra": {
        "label": "Google AI Ultra",
        "limit": 500, # Estimated "Max"
        "window_seconds": 5 * 3600, # 5 Hours
        "ancillary_limit": 25000,
        "reset_type": "rolling"
    }
}

DEFAULT_TIER = "Free"
USAGE_COSTS = {
    "standard": 1,
    "agentic": 5
}

# === AGENT LOGGING CONFIG ===
AUDIT_LOG_FILE = Path.home() / '.gemini' / 'antigravity' / 'audit_log.jsonl'

ACTION_TYPES = [
    "model_inference",
    "code_edit",
    "terminal_command",
    "browser_action",
    "artifact_generation"
]
