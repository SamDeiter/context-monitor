"""
Protobuf Token Extractor v2 - Enhanced Analysis
Extracts token usage from Antigravity conversation .pb files
"""

import struct
import sys
from pathlib import Path
import json

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

def extract_token_metadata(pb_file):
    """
    Extract token usage from .pb file.
    
    Strategy:
    1. Look for large numbers (1M-10M range) near end of file
    2. These represent context window usage snapshots
    3. The LAST occurrence is likely the most recent token count
    """
    with open(pb_file, 'rb') as f:
        data = f.read()
    
    file_size = len(data)
    
    # Search last 50KB for token metadata
    search_region = data[-50000:] if len(data) > 50000 else data
    
    # Extract all varint numbers
    candidates = []
    offset = 0
    while offset < len(search_region) - 10:
        num, new_offset = parse_varint(search_region, offset)
        if num and 100000 < num < 20000000:  # 100K to 20M tokens
            # Store with position (later = more recent)
            candidates.append({
                'value': num,
                'position': offset,
                'from_end': len(search_region) - offset
            })
        offset += 1
    
    if not candidates:
        return None
    
    # Sort by position (most recent last)
    candidates.sort(key=lambda x: x['position'])
    
    # The last few entries are likely the most recent token counts
    recent = candidates[-5:]
    
    # Look for the pattern: larger number followed by smaller number
    # (total context window, then tokens used)
    result = {
        'file_size': file_size,
        'estimated_tokens_old_method': file_size // 40,
        'candidates': recent,
        'likely_tokens_remaining': None,
        'likely_context_window': None
    }
    
    # Heuristic: Look for pairs where first > second
    for i in range(len(recent) - 1):
        curr = recent[i]['value']
        next_val = recent[i + 1]['value']
        
        # If we have a large number followed by smaller, that's likely window/used pattern
        if curr > next_val and curr > 1000000:
            result['likely_context_window'] = curr
            result['likely_tokens_remaining'] = next_val
            break
    
    # Fallback: use the largest number as context window
    if not result['likely_context_window']:
        result['likely_context_window'] = max(c['value'] for c in recent)
        # Use second-largest as remaining
        sorted_vals = sorted([c['value'] for c in recent], reverse=True)
        if len(sorted_vals) > 1:
            result['likely_tokens_remaining'] = sorted_vals[1]
    
    return result

def analyze_conversation(conv_id):
    """Analyze a specific conversation file."""
    conv_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'
    
    # Try .pb first, then .pb.gz
    pb_file = conv_dir / f'{conv_id}.pb'
    if not pb_file.exists():
        pb_file = conv_dir / f'{conv_id}.pb.gz'
        if not pb_file.exists():
            return None
    
    return extract_token_metadata(pb_file)

if __name__ == '__main__':
    # Test with current conversation
    current_id = '8ee9beb4-324c-4885-b8e0-8b9e7080e818'
    
    print(f"Analyzing conversation: {current_id}\n")
    result = analyze_conversation(current_id)
    
    if result:
        print(f"File size: {result['file_size']:,} bytes")
        print(f"Old estimation method: {result['estimated_tokens_old_method']:,} tokens")
        print(f"\n=== Token Metadata Extraction ===")
        
        if result['likely_context_window']:
            tokens_used = result['likely_context_window'] - result['likely_tokens_remaining']
            percent = (tokens_used / result['likely_context_window']) * 100
            
            print(f"Context Window: {result['likely_context_window']:,} tokens")
            print(f"Tokens Remaining: {result['likely_tokens_remaining']:,} tokens")
            print(f"Tokens Used: {tokens_used:,} tokens")
            print(f"Usage: {percent:.1f}%")
            
            print(f"\n=== Accuracy Comparison ===")
            old_estimate = result['estimated_tokens_old_method']
            error = abs(tokens_used - old_estimate)
            error_pct = (error / tokens_used) * 100
            print(f"Old method error: {error:,} tokens ({error_pct:.1f}% off)")
        else:
            print("Could not determine token usage")
            print(f"\nCandidates found: {len(result['candidates'])}")
            for c in result['candidates']:
                print(f"  {c['value']:,} (from end: {c['from_end']} bytes)")
    else:
        print("Conversation file not found")
