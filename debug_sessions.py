import re
from pathlib import Path
import os
import time

conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'

def check_files():
    print(f"Checking {conversations_dir}")
    files = list(conversations_dir.glob('*.pb'))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    print(f"Found {len(files)} sessions")
    
    patterns = [
        r'CorpusName[:\s]+([A-Za-z0-9_-]+/[A-Za-z0-9_-]+)',
        r'GitHub[/\\]([A-Za-z0-9_-]+)',  # Generic GitHub folder
        r'Users[/\\][^/\\]+[/\\]Documents[/\\]GitHub[/\\]([A-Za-z0-9_-]+)', # Windows specific
        r'([A-Za-z0-9_-]+)[/\\]\.git', # Git folder
    ]
    
    for f in files[:5]:
        print(f"\nScanning: {f.name}")
        try:
            content = f.read_bytes()
            text = content.decode('utf-8', errors='ignore')
            
            print(f"  File size: {len(text)} chars")
            
            found = False
            for p in patterns:
                # Test re.search (First match) -> Original behavior
                match = re.search(p, text, re.IGNORECASE)
                if match:
                    print(f"  [Search-First] Match pattern '{p}': {match.group(1)}")
                    found = True
                
                # Test re.findall (All matches) -> My changed behavior
                matches = re.findall(p, text, re.IGNORECASE)
                if matches:
                    print(f"  [FindAll-Last] Last match pattern '{p}': {matches[-1]}")
                    if len(matches) > 1:
                        print(f"    (Total matches: {len(matches)})")
            
            if not found:
                print("  NO MATCHES FOUND")
                print(f"  Snippet (first 500 chars): {text[:500]}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_files()
