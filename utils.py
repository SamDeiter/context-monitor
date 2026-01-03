"""
Utilities for Context Monitor
Includes protobuf parsing, system memory detection, and token extraction logic.
"""
import ctypes
import platform
import re
from pathlib import Path

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
    Extract accurate token count from protobuf conversation file.
    Uses model preset as context window (reliable) and extracts tokens_remaining from protobuf.
    """
    try:
        with open(pb_file_path, 'rb') as f:
            data = f.read()
        
        file_size = len(data)
        
        # For small files (< 50KB), use simple estimation - protobuf metadata is unreliable
        if file_size < 50000:
            estimated_tokens = file_size // 4
            return {
                'tokens_used': estimated_tokens,
                'context_window': default_context_window,
                'tokens_remaining': default_context_window - estimated_tokens,
                'method': 'estimation'
            }
        
        # For larger files, scan for token metadata in the tail
        search_region = data[-50000:]
        
        candidates = []
        offset = 0
        while offset < len(search_region) - 5:
            num, new_offset = parse_varint(search_region, offset)
            if num is not None and 1000 < num < 30000000:
                candidates.append({'value': num, 'position': offset})
            offset += 1
        
        if not candidates:
            estimated = file_size // 4
            return {
                'tokens_used': estimated,
                'context_window': default_context_window,
                'tokens_remaining': default_context_window - estimated,
                'method': 'fallback'
            }
        
        candidates.sort(key=lambda x: x['position'])
        recent = candidates[-10:]  # Look at more candidates
        
        # Strategy: Find a value close to the model's context window
        # The protobuf should contain both the context_window and tokens_remaining
        tokens_remaining = None
        
        for c in reversed(recent):
            val = c['value']
            # If we find a value that looks like "remaining tokens" (< context window, reasonable size)
            if val < default_context_window and val > 10000:
                tokens_remaining = val
                break
        
        if tokens_remaining is None:
            # Fallback: use smallest recent value as remaining
            sorted_vals = sorted([c['value'] for c in recent])
            tokens_remaining = sorted_vals[0] if sorted_vals else default_context_window // 2
        
        # Always use model preset as context window (most reliable)
        context_window = default_context_window
        tokens_used = context_window - tokens_remaining
        
        # CRITICAL SANITY CHECK: tokens_used should be proportional to file size
        # A typical token is ~4 bytes, so max plausible tokens = file_size / 3
        max_plausible_tokens = file_size // 3
        if tokens_used < 0 or tokens_used > max_plausible_tokens:
            # Extraction failed, use file-size estimation
            tokens_used = file_size // 4
            tokens_remaining = context_window - tokens_used
        
        project_name = None
        try:
            project_match = re.search(rb'GitHub[/\\]([A-Za-z0-9_-]+)', data)
            if project_match:
                project_name = project_match.group(1).decode('utf-8', errors='ignore')
        except:
            pass

        return {
            'tokens_used': tokens_used,
            'context_window': context_window,
            'tokens_remaining': tokens_remaining,
            'project_name': project_name,
            'method': 'protobuf'
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
