"""
Utilities for Context Monitor
Includes protobuf parsing, system memory detection, and token extraction logic.
"""
import ctypes
import platform
import re
# Path objects passed from callers, no import needed

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

def extract_pb_tokens(pb_file_path, default_context_window=1000000):
    """
    Extract token count from protobuf conversation file.
    Uses file-size estimation (~4 bytes per token) which is more reliable than
    protobuf metadata parsing which often grabbed unrelated values (timestamps, offsets).
    """
    try:
        with open(pb_file_path, 'rb') as f:
            data = f.read()
        
        file_size = len(data)
        
        # File-size estimation: ~4 bytes per token (conservative, accounts for overhead)
        estimated_tokens = file_size // 4
        
        # Extract project name from file content
        project_name = None
        try:
            project_match = re.search(rb'GitHub[/\\]([A-Za-z0-9_-]+)', data)
            if project_match:
                project_name = project_match.group(1).decode('utf-8', errors='ignore')
        except:
            pass

        return {
            'tokens_used': estimated_tokens,
            'context_window': default_context_window,
            'tokens_remaining': default_context_window - estimated_tokens,
            'project_name': project_name,
            'method': 'estimation'
        }
    except Exception as e:
        print(f"[Token Extraction] Error: {e}")
        estimated = pb_file_path.stat().st_size // 4
        return {
            'tokens_used': estimated,
            'context_window': default_context_window,
            'tokens_remaining': default_context_window - estimated,
            'method': 'fallback'
        }
