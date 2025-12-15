
import re

content = """
The project already has [databaseCleanup.js](file:///c:/Users/Sam%20Deiter/Documents/GitHub/UE5QuestionGenerator/src/utils/databaseCleanup.js) which:
"""

# Pattern from context_monitor.py
github_pattern = re.compile(r'GitHub[\\/]([^\\/)\n]+)', re.IGNORECASE)

match = github_pattern.search(content)

if match:
    print(f"Found match: {match.group(1).strip()}")
else:
    print("No match found")
