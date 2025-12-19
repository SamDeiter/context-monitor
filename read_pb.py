from pathlib import Path

path = Path(r"C:\Users\Sam Deiter\.gemini\antigravity\conversations\b7c3e35e-733b-46de-8787-a0cc5df95bf4.pb")
try:
    content = path.read_bytes()[:2000]
    text = content.decode('utf-8', errors='ignore')
    print("--- RAW TEXT START ---")
    print(text)
    print("--- RAW TEXT END ---")
except Exception as e:
    print(e)
