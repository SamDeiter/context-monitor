"""
Update context window from hardcoded 200K to configurable 1M tokens
Based on R&D: Gemini 3 Pro / Antigravity supports 1M+ token context
"""
import re

def update_context_window():
    filepath = r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add configurable context window to settings/init
    old_budget = "self._daily_budget = self.settings.get('daily_budget', 500000)  # Default 500k tokens/day"
    new_budget = """self._daily_budget = self.settings.get('daily_budget', 500000)  # Default 500k tokens/day
        self._context_window = self.settings.get('context_window', 1000000)  # Default 1M tokens (Gemini 3 Pro)"""
    
    content = content.replace(old_budget, new_budget)
    
    # 2. Replace all hardcoded 200000 with self._context_window
    # First, handle the ones inside methods (use context_window variable)
    content = content.replace("context_window = 200000", "context_window = self._context_window")
    content = content.replace("max_tokens = 200000", "max_tokens = self._context_window")
    
    # Write updated file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Context window updated!")
    print("  - Changed from hardcoded 200K to configurable")
    print("  - Default is now 1,000,000 tokens (Gemini 3 Pro)")
    print("  - Can be configured via settings")

if __name__ == "__main__":
    update_context_window()
