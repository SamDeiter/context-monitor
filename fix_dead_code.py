"""
Dead Code Cleanup Script for Context Monitor
Fixes identified by pyflakes:
1. Remove unused imports
2. Remove duplicate function definitions (keep the enhanced versions)
3. Fix undefined variable bug
"""

import re
import shutil
from pathlib import Path

# Backup first
src = Path('context_monitor.pyw')
backup = Path('context_monitor.pyw.backup')
shutil.copy(src, backup)
print(f"✓ Backed up to {backup}")

# Read the file
content = src.read_text(encoding='utf-8')
lines = content.split('\n')
original_line_count = len(lines)

# Track changes
changes = []

# === FIX 1: Remove unused imports from top of file ===
# Line 21: functools.partial
# Line 22: collections.OrderedDict  
# Line 23: utils.parse_varint

lines_to_remove = []

# Find and mark import lines to remove
for i, line in enumerate(lines[:30]):
    if 'from functools import partial' in line:
        lines_to_remove.append(i)
        changes.append(f"Line {i+1}: Removed unused import 'functools.partial'")
    if 'from collections import OrderedDict' in line:
        lines_to_remove.append(i)
        changes.append(f"Line {i+1}: Removed unused import 'collections.OrderedDict'")
    # Parse varint is in a multi-import line, need to handle differently
    if 'from utils import' in line and 'parse_varint' in line:
        # Remove just parse_varint from the import list
        new_line = re.sub(r'parse_varint,?\s*', '', line)
        new_line = re.sub(r',\s*$', '', new_line)  # Clean trailing comma
        new_line = re.sub(r'\s+,', ',', new_line)  # Clean double commas
        if new_line != line:
            lines[i] = new_line
            changes.append(f"Line {i+1}: Removed 'parse_varint' from utils import")

# === FIX 2: Remove duplicate functions (keep the later, more complete versions) ===

# Function 1: set_polling_speed - remove lines 1190-1194 (keep 1662-1668)
# Function 2: copy_handoff - remove lines 1119-1156 (keep 1670-1718)  
# Function 3: check_budget_notification - remove lines 2010-2016 (keep 2018-2033)

# Find exact line ranges for each duplicate function to remove
# We need to identify the function boundaries

def find_function_range(lines, start_line_idx, func_name):
    """Find the exact line range of a function starting at start_line_idx"""
    if f'def {func_name}' not in lines[start_line_idx]:
        return None, None
    
    start = start_line_idx
    end = start_line_idx
    
    # Find the end of this function (next def at same indentation or less, or end of class)
    base_indent = len(lines[start_line_idx]) - len(lines[start_line_idx].lstrip())
    
    for i in range(start_line_idx + 1, min(start_line_idx + 100, len(lines))):
        line = lines[i]
        if not line.strip():  # Empty line
            end = i
            continue
        current_indent = len(line) - len(line.lstrip())
        # If we hit a new def at same or less indentation, stop before it
        if line.strip().startswith('def ') and current_indent <= base_indent:
            break
        end = i
    
    return start, end

# Find the first occurrence of each duplicate function
# set_polling_speed at line 1190 (0-indexed: 1189)
s1_start = 1189
s1_end = 1194  # Through line 1195

# copy_handoff at line 1119 (0-indexed: 1118)
c1_start = 1118
c1_end = 1156  # Through line 1157

# check_budget_notification at line 2010 (0-indexed: 2009) 
b1_start = 2009
b1_end = 2016  # Through line 2017

# Add these ranges to removal list (in reverse order to preserve indices)
removal_ranges = [
    (b1_start, b1_end, 'check_budget_notification'),
    (s1_start, s1_end, 'set_polling_speed'),
    (c1_start, c1_end, 'copy_handoff'),
]

# Sort by start line in reverse order so we remove from end first
removal_ranges.sort(key=lambda x: x[0], reverse=True)

for start, end, name in removal_ranges:
    changes.append(f"Lines {start+1}-{end+1}: Removed duplicate function '{name}'")
    lines_to_remove.extend(range(start, end + 1))

# Also check for unused local import on line 1814 (timedelta in archive_old_sessions)
# This is a local import inside a function which is actually needed, pyflakes is confused
# because datetime.timedelta is already imported at top. But let's verify...
# Line 1814: from datetime import datetime, timedelta
# This is inside archive_old_sessions which uses timedelta on line 1834

# === FIX 3: Fix undefined 'tokens_left' on line 1572 ===
# Looking at context, tokens_left should be calculated from tokens_used and context_limit
# Line 1572 uses tokens_left but it's not defined. Need to add calculation after line 1550-1552

for i, line in enumerate(lines):
    if i == 1571 and 'tokens_left' in line and 'Tokens Remaining' in line:  # 0-indexed for line 1572
        # Need to add tokens_left calculation. Let's find where we can add it
        # Looking at context, context_limit is defined on 1551
        pass  # We'll handle this specially below
    # Also fix the unused import line at 1814 - actually it's fine, it's inside a function

# Apply removals (reverse order to preserve indices)
lines_to_remove = sorted(set(lines_to_remove), reverse=True)
for idx in lines_to_remove:
    del lines[idx]

# Now fix the tokens_left bug - need to find the new line number after deletions
# The render_token_stats_inline function is around line 1544-1590 originally
# After removing ~52 lines before it, we need to recalculate

# Let's find the function and fix it
new_content = '\n'.join(lines)
fixed_content = new_content

# Fix tokens_left by adding its calculation
old_pattern = r"(context_limit = self\._context_window\s*\n\s*percent_used = min\(100, \(tokens_used / context_limit\) \* 100\))"
replacement = r"\1\n        tokens_left = max(0, context_limit - tokens_used)"
fixed_content = re.sub(old_pattern, replacement, fixed_content)

if old_pattern in new_content or re.search(old_pattern, new_content):
    changes.append("Line ~1493 (after cleanup): Added missing 'tokens_left' calculation")

# Write the fixed file
src.write_text(fixed_content, encoding='utf-8')

print(f"\n{'='*60}")
print(f"DEAD CODE CLEANUP COMPLETE")
print(f"{'='*60}")
print(f"Original lines: {original_line_count}")
print(f"New lines: {len(fixed_content.split(chr(10)))}")
print(f"Lines removed: {original_line_count - len(fixed_content.split(chr(10)))}")
print(f"\nChanges made:")
for c in changes:
    print(f"  • {c}")
print(f"\nBackup saved to: {backup}")
