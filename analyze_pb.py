import os
from pathlib import Path

def parse_varint(data, offset):
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

pb_path = Path.home() / '.gemini' / 'antigravity' / 'conversations' / '90acf728-e38e-4b06-883a-ade28433323a.pb'

if not pb_path.exists():
    # Try current session ID
    current_session_id = '90acf728-e38e-4b06-883a-ade28433323a'
    pb_path = Path.home() / '.gemini' / 'antigravity' / 'conversations' / f"{current_session_id}.pb"

if pb_path.exists():
    print(f"Analyzing {pb_path}")
    with open(pb_path, 'rb') as f:
        data = f.read()
    
    # Analyze the last few KB
    search_region = data[-1000:]
    offset = 0
    found = []
    while offset < len(search_region):
        # We don't know where a varint starts, so we try every offset
        val, next_offset = parse_varint(search_region, offset)
        if val is not None and val > 100:
            found.append((offset, val))
        offset += 1
    
    # Deduplicate/Filter
    # Many offsets will return valid varints if they overlap
    print("Potential large numbers in tail:")
    for off, val in found:
        # Check if this val looks like a token count (e.g. 1M, or 10k-500k)
        if val > 1000:
             print(f"Offset {off}: {val}")
else:
    print(f"File {pb_path} not found")
