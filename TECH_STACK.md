# Tech Stack Documentation

## Overview

Context Monitor is a lightweight desktop widget built entirely in Python using the standard library, with no external dependencies required.

## Technology Stack

### Core Language

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.8+ |
| GUI Framework | Tkinter | Built-in |
| Platform | Windows | 10/11 |

### Python Standard Library Modules

| Module | Purpose |
|--------|---------|
| `tkinter` | GUI framework and widget rendering |
| `tkinter.messagebox` | Dialog popups for diagnostics and confirmations |
| `pathlib` | Cross-platform file path handling |
| `datetime` | Timestamp operations |
| `json` | Settings persistence and configuration |
| `re` | Regular expressions for project name extraction |
| `subprocess` | External process management (tasklist, VS Code detection) |
| `os` | Operating system interface |
| `ctypes` | Windows API access for memory detection |
| `platform` | OS detection for platform-specific code |

## Architecture

### Class Structure

```
ContextMonitor (Main Application)
├── __init__()           # Initialize window, settings, hardware scan
├── setup_ui()           # Build UI (full/mini mode)
├── draw_gauge()         # Render circular progress gauge
├── load_session()       # Load current conversation data
├── get_project_name()   # Multi-strategy project detection
├── show_context_menu()  # Right-click menu
├── show_advanced_stats()# Detailed token breakdown
├── show_analytics_dashboard() # Usage history and budget
├── show_diagnostics()   # System health check
├── archive_old_sessions() # Gzip compression for old files
└── run()                # Main event loop

ToolTip (Helper Class)
├── schedule()           # Delay before showing
├── show()               # Display tooltip
└── hide()               # Destroy tooltip
```

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    File System                          │
│  ~/.gemini/antigravity/conversations/*.pb               │
│  ~/.gemini/antigravity/conversations/*.pb               │
│  ~/.gemini/antigravity/conversations/*.pb.gz            │
│  ~/.gemini/antigravity/brain/<session>/*.md             │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Context Monitor                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Session   │  │   Project   │  │  Hardware   │     │
│  │   Scanner   │→ │  Detector   │→ │   Monitor   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│         │                │                │             │
│         ▼                ▼                ▼             │
│  ┌─────────────────────────────────────────────────┐   │
│  │              UI Renderer (Tkinter)              │   │
│  │  • Gauge Canvas  • Labels  • Status Bar         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Key Algorithms

### Token Estimation

```python
# Estimate tokens from file size (approximate)
estimated_tokens = file_size_bytes // 4
tokens_used = estimated_tokens // 10
context_window = 200_000
percent_used = (tokens_used / context_window) * 100
```

### Project Detection Strategy

1. **Brain Folder Metadata** - Check `brain/{id}/*.md` for project context
2. **VS Code Window Title** - Extract from active VS Code window (fallback)
3. **Recently Modified GitHub** - Check `.git/index` timestamps (fallback)
4. **Fallback** - Truncated session ID

### Hardware-Adaptive Thresholds

```python
# Thresholds scale with system RAM
proc_warn = max(500, int(ram_mb * 0.015))   # 1.5% of RAM
proc_crit = max(1000, int(ram_mb * 0.04))   # 4% of RAM
total_warn = max(2000, int(ram_mb * 0.10))  # 10% of RAM
total_crit = max(3000, int(ram_mb * 0.15))  # 15% of RAM
```

## File Structure

```
context-monitor/
├── context_monitor.py      # Main application (900+ lines)
├── Launch-ContextMonitor.ps1  # PowerShell launcher
├── settings.json           # Local settings (auto-generated)
├── README.md               # Project documentation
├── TECH_STACK.md           # This file
├── LICENSE                 # MIT License
└── .gitignore              # Git ignore rules
```

## Performance Considerations

### Optimizations

- **Cached project names** - 30-60 second TTL to reduce file I/O
- **Fast process detection** - Uses `tasklist` instead of slow WMI
- **Minimal redraws** - Only gauge elements are updated, not full canvas
- **Transparency color** - Uses `#010101` for efficient transparency

### Resource Usage

- **Memory**: ~20-30 MB typical
- **CPU**: < 1% (polling every 5 seconds)
- **Disk I/O**: Minimal (reads conversation file size only)

## Platform-Specific Code

### Windows APIs (via ctypes)

```python
# Memory detection using GlobalMemoryStatusEx
kernel32.GlobalMemoryStatusEx(MEMORYSTATUSEX)

# Process enumeration using tasklist
tasklist /FI "IMAGENAME eq Antigravity.exe" /FO CSV
```

### Tkinter Features

- `overrideredirect(True)` - Borderless window
- `attributes('-topmost', True)` - Always on top
- `attributes('-transparentcolor', color)` - Transparency masking
- `attributes('-alpha', value)` - Window opacity

## Future Considerations

### Potential Enhancements

- Cross-platform support (macOS, Linux)
- Custom themes/color schemes
- Multiple session tracking
- Historical usage graphs
- System tray integration

### Known Limitations

- Windows-only (ctypes/tasklist dependencies)
- Token estimation is approximate (no protobuf parsing)
- Project detection requires VS Code or GitHub folder structure

---

*Last Updated: December 2024*
