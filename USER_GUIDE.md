# Context Monitor - User Guide

This guide provides comprehensive instructions for installing, using, and troubleshooting the Context Monitor widget.

## 🚀 Getting Started

### Installation

1. **Clone the Repository**:

    ```bash
    git clone https://github.com/SamDeiter/context-monitor.git
    cd context-monitor
    ```

2. **Launch the Application**:
    * **Method 1 (Recommended)**: Double-click `launch.bat` file in the folder.
    * **Method 2 (PowerShell)**: Run `.\Launch-Monitor.ps1` in PowerShell.
    * **Method 3 (Python)**: Run `python context_monitor.py` (requires Python 3.8+).

## 🛠️ Usage

### Display Modes

* **Full Mode (Default)**: Shows tokens remaining, percentage used, active project name, and status messages.
* **Mini Mode**: A compact circular gauge showing only the percentage.
* **Toggle**: Press `M` or right-click and select **Toggle Mini Mode**.
* **Dashboard**: Press `D` to open the Analytics Dashboard.
* **Export**: Press `E` to export token history to CSV.

### Transparency

* **Make more transparent**: Press `-` (minus key).
* **Make less transparent**: Press `+` (plus key).

### Drag & Drop

* Click and drag anywhere on the widget to move it around your screen. It stays on top of other windows.

### Analytics & Budgeting (New)

The monitor now includes powerful tools to track your usage:

* **Dashboard (D)**: Displays daily token usage, cost estimates, and history graphs.
* **Daily Budget**: Set a token limit (e.g., 2,000,000) in the dashboard.
  * You get a notification at **75%** usage.
  * You get a critical alert at **90%** usage.
* **CSV Export (E)**: Download your usage history for spreadsheet analysis.

### Session Archiving

To save disk space without losing history:

1. Right-click and select **📦 Archive Old Sessions**.
2. This compresses sessions older than 3 days into `.pb.gz` files.
3. Archived sessions **still appear** in the "Switch Session" menu and unarchive automatically when selected.

### Right-Click Menu

Right-click the widget to access:

* **Show Diagnostics**: Check system health and memory usage.
* **Advanced Token Stats**: View detailed breakdown of input/output tokens.
* **Clean Old Conversations**: Free up disk space by deleting large, old session files.
* **Restart Antigravity**: One-click restart for your IDE.
* **Exit**: Properly close the widget and cleanup processes.

## 💡 Best Practices

1. **Monitor Colors**:
    * 🟢 **Green** (<60%): Safe to continue working.
    * 🟡 **Yellow** (60-80%): Plan to finish your current task.
    * 🔴 **Red** (>80%): **Critical!** Wrap up immediately. The widget will automatically copy a "handoff" prompt to your clipboard.

2. **Handoff**: When you hit 80% usage, paste the clipboard content into a new session to continue seamlessly.

3. **Performance**: The widget refreshes every 15 seconds to save battery/CPU. If you need an instant update, press `R`.

## ❓ Troubleshooting

### Widget is stuck or blank

* Press `R` to force a refresh.
* Right-click and select **Restart Antigravity** if the IDE is unresponsive.

### "Python not found" error

* Ensure Python 3.8 or higher is installed and added to your system PATH.

### Project name isn't updating

* The widget checks `brain/` folder metadata for project names, which is much faster and more accurate than before.
* Switching projects is instant, but the file scan happens in the background.

### High Memory Usage

* Right-click -> **Show Diagnostics**.
* It will list any processes consuming excessive RAM. Follow the on-screen recommendations.

## 📁 File Structure

* `context_monitor.py`: Main application code.
* `Launch-Monitor.ps1`: Launch script (prevents console window).
* `settings.json`: Stores your preferences (auto-generated in `~/.gemini/antigravity`).
