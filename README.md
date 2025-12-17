# Context Monitor

A sleek, always-on-top desktop widget for tracking Antigravity IDE token usage and context window consumption in real-time.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

### Core Functionality

- **Real-time Token Tracking** - Monitor your context window usage with live updates
- **Dual Display Modes** - Switch between full dashboard and compact mini mode
- **Smart Project Detection** - Auto-detects active project from VS Code and GitHub folders
- **Auto-Handoff** - Automatically copies session handoff prompt at 80% usage

### User Interface

- **Borderless Design** - Clean, modern look with no window chrome
- **Always On Top** - Widget stays visible while you work
- **Transparency Control** - Adjust opacity with keyboard shortcuts
- **Drag Anywhere** - Reposition by dragging any part of the widget
- **Visual Alerts** - Color-coded gauges (green/yellow/red) and flash warnings

### Advanced Features

- **Right-Click Context Menu** - Quick access to all features
- **Advanced Token Statistics** - Detailed breakdown with visual progress bar
- **System Diagnostics** - Monitor Antigravity process memory usage
- **Conversation Cleanup** - Find and remove large conversation files
- **One-Click Restart** - Restart Antigravity IDE from the widget

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `M` | Toggle mini/full mode |
| `A` | Show advanced token stats |
| `R` | Force refresh project detection |
| `+` | Increase transparency |
| `-` | Decrease transparency |

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/SamDeiter/context-monitor.git
   ```

2. Run the widget:

   ```bash
   python context_monitor.py
   ```

   Or use the provided launcher:

   ```bash
   .\Launch-ContextMonitor.ps1
   ```

## Usage

### Quick Start

1. Launch the widget - it will appear in the corner of your screen
2. The gauge shows your current context usage percentage
3. **Right-click** anywhere for the full menu
4. **Double-click** in mini mode to expand

### Understanding the Gauge

- 🟢 **Green (0-59%)** - Plenty of context remaining
- 🟡 **Yellow (60-79%)** - Approaching limit, plan to wrap up
- 🔴 **Red (80-100%)** - Critical! Handoff automatically copied

### Mini Mode vs Full Mode

- **Mini Mode**: Compact circular gauge showing percentage only
- **Full Mode**: Full dashboard with tokens remaining, project name, and status

## Configuration

Settings are automatically saved to:

```
~/.gemini/antigravity/scratch/token-widget/settings.json
```

Configurable options:

- Window transparency (0.5 - 1.0)
- Display mode (mini/full)
- Window position

## Requirements

- Python 3.8+
- Windows 10/11
- Antigravity IDE

## Tech Stack

See [TECH_STACK.md](TECH_STACK.md) for detailed technical documentation.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Author

**Sam Deiter** - [GitHub](https://github.com/SamDeiter)

---

*Built for the Antigravity IDE ecosystem*
