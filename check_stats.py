import json
from pathlib import Path
import os
from datetime import datetime

history_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'history.json'
analytics_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'analytics.json'

print(f"Checking {history_file}")
if history_file.exists():
    with open(history_file, 'r') as f:
        history = json.load(f)
        print(f"History size: {len(history)} sessions")
        # Print last few entries of the most recent session
        if history:
            latest_id = list(history.keys())[0] # Usually first is most recent in dict? No, check timestamps.
            # Find the one with the latest timestamp in its entries
            latest_session = None
            max_time = 0
            for session_id, entries in history.items():
                for entry in entries:
                    ts = entry.get('timestamp') or 0
                    if ts > max_time:
                        max_time = ts
                        latest_session = session_id
            
            if latest_session:
                print(f"Latest session: {latest_session}")
                last_entry = history[latest_session][-1]
                print(f"Last entry: {last_entry}")
                dt = datetime.fromtimestamp(last_entry['timestamp'])
                print(f"Updated at: {dt}")

print(f"\nChecking {analytics_file}")
if analytics_file.exists():
    with open(analytics_file, 'r') as f:
        analytics = json.load(f)
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"Today's stats: {analytics.get('daily', {}).get(today)}")
