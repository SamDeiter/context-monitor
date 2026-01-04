"""
Configuration for Context Monitor
All hardcoded values, colors, model definitions, and default settings.
"""
from pathlib import Path

# === PATHS ===
BASE_DIR = Path.home() / '.gemini' / 'antigravity'
SCRATCH_DIR = BASE_DIR / 'scratch' / 'token-widget'
CONVERSATIONS_DIR = BASE_DIR / 'conversations'
BRAIN_DIR = BASE_DIR / 'brain'
GITHUB_DIR = Path.home() / 'Documents' / 'GitHub'

SETTINGS_FILE = SCRATCH_DIR / 'settings.json'
HISTORY_FILE = SCRATCH_DIR / 'history.json'
ANALYTICS_FILE = SCRATCH_DIR / 'analytics.json'

# === THEME COLORS (GitHub Dark) ===
COLORS = {
    'bg': '#0d1117',
    'bg2': '#161b22',
    'bg3': '#21262d',
    'text': '#e6edf3',
    'text2': '#8b949e',
    'muted': '#484f58',
    'green': '#3fb950',
    'yellow': '#d29922',
    'red': '#f85149',
    'blue': '#58a6ff'
}

# === AI MODELS ===
# Context windows are estimates - Antigravity doesn't publish official limits
MODELS = {
    # --- Core Reasoning Models ---
    "Gemini 3 Pro (High)": 1_000_000,
    "Gemini 3 Pro (Deep Think)": 1_000_000,
    "Gemini 3 Flash": 1_000_000,
    "Claude Sonnet 4.5": 200_000,
    "Claude Sonnet 4.5 (Thinking)": 200_000,
    "Claude Opus 4.5": 200_000,
    "Claude Opus 4.5 (Thinking)": 200_000,
    "GPT-OSS": 128_000,
    
    # --- Auxiliary/Agent Models ---
    "Nano Banana Pro": 32_000,  # Image generation
    "Gemini 2.5 Pro UI Checkpoint": 1_000_000,  # Browser control
    "Gemini 2.5 Flash": 1_000_000,  # Background tasks
    "Gemini 2.5 Flash Lite": 500_000,  # Lite variant
    
    # --- Custom ---
    "Custom": None
}


# === DEFAULT SETTINGS ===
DEFAULT_SETTINGS = {
    'alpha': 0.95,
    'display_mode': 'compact',
    'polling_interval': 10_000,  # ms
    'daily_budget': 1_000_000,
    'context_window': 1_000_000,
    'model': 'Gemini 3 Flash',
    'window_x': 50,
    'window_y': 50,
    'window_w': 480,
    'window_h': 240,
    'full_w': 650,
    'full_h': 650
}

# === UI CONSTANTS ===
MIN_WINDOW_WIDTH = 400
MIN_WINDOW_HEIGHT = 200
HISTORY_CACHE_TTL = 5  # seconds
ANALYTICS_SAVE_THROTTLE = 60  # seconds (increased from 30 for less disk I/O)
VSCODE_CACHE_TTL = 10  # seconds - cache VS Code detection result
MAX_HISTORY_POINTS = 200
TOKEN_ESTIMATION_BYTES = 4
DEFAULT_CONTEXT_WINDOW = 1_000_000

# === FONT DEFINITIONS ===
FONTS = {
    'title': ('Segoe UI', 10, 'bold'),
    'header': ('Segoe UI', 10),
    'body': ('Segoe UI', 9),
    'small': ('Segoe UI', 8),
    'mono': ('Consolas', 11),
    'mono_bold': ('Consolas', 11, 'bold'),
    'large_tokens': ('Consolas', 22, 'bold'),
    'percent': ('Segoe UI', 24, 'bold')
}
