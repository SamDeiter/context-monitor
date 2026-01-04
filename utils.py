"""
Utilities for Context Monitor
Includes protobuf parsing, system memory detection, and token extraction logic.
"""
import ctypes
import platform
import re
# Path objects passed from callers, no import needed
import subprocess
from config import DEFAULT_CONTEXT_WINDOW, TOKEN_ESTIMATION_BYTES

def get_antigravity_processes():
    """Get memory/CPU usage of Antigravity processes (Fast fallback)"""
    # PowerShell/WMI is too slow on this user's machine (causing UI freeze)
    # We will iterate processes using tasklist which is faster, or just return empty for speed
    try:
         # Fast check using tasklist CSV format
        cmd = "tasklist /FI \"IMAGENAME eq Antigravity.exe\" /FO CSV /NH"
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        
        data = []
        if result.stdout:
            for line in result.stdout.splitlines():
                if 'Antigravity' in line:
                    parts = line.split('","')
                    if len(parts) >= 5:
                        pid = parts[1]
                        mem_str = parts[4].replace('"', '').replace(' K', '').replace(',', '')
                        mem_mb = int(mem_str) // 1024
                        data.append({
                            'Id': pid,
                            'Type': 'Process', # Detailed type requires slow WMI
                            'Mem': mem_mb,
                            'CPU': 0 # CPU requires slow PerfCounters
                        })
        return data
    except Exception as e:
        print(f"Error getting processes: {e}")
        return []

def parse_varint(data, offset):
    """Parse a protobuf varint from data at offset."""
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, offset
        shift += 7
    return None, offset

def get_total_memory():
    """Detect total system RAM in MB using ctypes"""
    try:
        if platform.system() == "Windows":
            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', c_ulonglong),
                    ('ullAvailPhys', c_ulonglong),
                    ('ullTotalPageFile', c_ulonglong),
                    ('ullAvailPageFile', c_ulonglong),
                    ('ullTotalVirtual', c_ulonglong),
                    ('ullAvailVirtual', c_ulonglong),
                    ('ullAvailExtendedVirtual', c_ulonglong),
                ]
            memoryStatus = MEMORYSTATUSEX()
            memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
            return int(memoryStatus.ullTotalPhys / (1024 * 1024))
        else:
            return 16384 # Fallback
    except Exception as e:
        print(f"Error detecting RAM: {e}")
        return 16384

def calculate_thresholds(ram_mb):
    """Calculate warnings based on system RAM"""
    return {
        'proc_warn': max(500, int(ram_mb * 0.015)),  # 1.5%
        'proc_crit': max(1000, int(ram_mb * 0.04)),  # 4%
        'total_warn': max(2000, int(ram_mb * 0.10)), # 10%
        'total_crit': max(3000, int(ram_mb * 0.15))  # 15%
    }

def extract_pb_tokens(pb_file_path, default_context_window=DEFAULT_CONTEXT_WINDOW):
    """
    Extract token count from protobuf conversation file.
    Uses file-size estimation (st_size // 4) for refined accuracy and stability.
    Only reads partial content for project detection to avoid race conditions.
    """
    try:
        # Ensure Path object
        if isinstance(pb_file_path, str):
            from pathlib import Path
            pb_file_path = Path(pb_file_path)
            
        # Use valid file stat for size (Atomic-ish)
        # If file is locked/writing, stat usually gives current size or 0
        try:
            stat = pb_file_path.stat()
            file_size = stat.st_size
        except OSError:
            # File might be locked or moving
            return None
        
        # Estimate: 4 bytes per token
        estimated_tokens = file_size // TOKEN_ESTIMATION_BYTES
        
        # Extract project name (Optimized: First 100KB only)
        project_name = None
        try:
            with open(pb_file_path, 'rb') as f:
                # Read header
                data = f.read(102400)
                project_match = re.search(rb'GitHub[/\\]([A-Za-z0-9_-]+)', data)
                if project_match:
                    project_name = project_match.group(1).decode('utf-8', errors='ignore')
        except:
            pass # Non-critical
            
        return {
            'tokens_used': estimated_tokens,
            'context_window': default_context_window,
            'tokens_remaining': default_context_window - estimated_tokens,
            'project_name': project_name,
            'method': 'stat_estimation'
        }
    except Exception as e:
        print(f"[Token Extraction] Error: {e}")
        return {
            'tokens_used': 0,
            'context_window': default_context_window,
            'tokens_remaining': default_context_window,
            'method': 'error'
        }

# ==== FILE MAINTENANCE ====
import glob
from pathlib import Path

def get_large_conversations(conversations_dir, min_size_mb=5):
    """Get conversation files larger than min_size_mb"""
    large_files = []
    try:
        if isinstance(conversations_dir, str):
            conversations_dir = Path(conversations_dir)
            
        for f in conversations_dir.glob('*.pb'):
            # Skip if file doesn't exist (race condition)
            if not f.exists(): continue
            
            size_mb = f.stat().st_size / (1024 * 1024)
            if size_mb >= min_size_mb:
                large_files.append({
                    'name': f.stem[:8] + '...',
                    'size_mb': round(size_mb, 1),
                    'path': f
                })
        large_files.sort(key=lambda x: x['size_mb'], reverse=True)
    except Exception as e:
        print(f"Error scanning files: {e}")
    return large_files[:5]

# ==== PROJECT DETECTION ====
import time
import os

def get_active_vscode_project():
    """Get active VS Code/Antigravity project using ctypes (Windows only)."""
    if platform.system() != "Windows":
        return None
        
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        window_title = buff.value
        
        # Check for VS Code: "filename - project - Visual Studio Code"
        if "Visual Studio Code" in window_title:
            parts = window_title.split(' - ')
            if len(parts) >= 2:
                return parts[-2].strip()
            return window_title.replace(" - Visual Studio Code", "").strip()
        
        # Check for Antigravity: "project - Antigravity - filename"
        elif "Antigravity" in window_title:
            parts = window_title.split(' - ')
            if len(parts) >= 1:
                # Project is the FIRST part in Antigravity
                return parts[0].strip()
            
    except Exception as e:
        print(f"Error getting active window: {e}")
    return None


def get_recently_modified_project(github_path):
    """Find the most recently modified project in GitHub folder."""
    try:
        github_dir = Path(github_path)
        if not github_dir.exists():
            return None
            
        projects = []
        for d in github_dir.iterdir():
            if d.is_dir() and not d.name.startswith('.'):
                try:
                    projects.append((d.name, d.stat().st_mtime))
                except OSError:
                    pass
        
        if projects:
            # Return newest
            projects.sort(key=lambda x: x[1], reverse=True)
            return projects[0][0]
    except Exception as e:
        print(f"Recent project detection error: {e}")
    return None

def get_project_name(session_id, github_path=None, skip_vscode=False):
    """
    Determine project name using multiple strategies:
    1. Check if session_id contains project name (legacy)
    2. Check active VS Code window (if enabled)
    3. Check most recently modified project folder
    """
    # 1. Legacy check (folder name in ID)
    if '\\' in session_id or '/' in session_id:
        return Path(session_id).parent.name
        
    # 2. VS Code Check
    if not skip_vscode:
        vscode_proj = get_active_vscode_project()
        if vscode_proj:
            return vscode_proj
            
    # 3. Recent Folder Check
    if github_path:
        recent = get_recently_modified_project(github_path)
        if recent:
            return recent
            
    return "Unknown Project"
