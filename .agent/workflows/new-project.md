---
description: Initialize a new project with standardized agent config from the central agent-workflows repo
---

# New Project Setup

Invoke with `/new-project` when creating or onboarding a new project.

// turbo-all

## Steps

1. **Scaffold the project** (framework-specific init, folder structure, etc.)

2. **Deploy agent config** — Run the installer from the central repo:
   ```powershell
   & "C:\Users\Sam Deiter\Documents\GitHub\agent-workflows\install.ps1" "<project-path>"
   ```

3. **Create `AGENTS.md`** in the project root with:
   - Project description and tech stack
   - Key files and architecture overview
   - Development patterns and conventions
   - Common issues and gotchas

4. **Initialize Git** (if not already):
   ```powershell
   git init
   git add -A
   git commit -m "feat: initial project setup with standardized agent config"
   ```

5. **Confirm** to the user:
   - `.agent/workflows/` deployed (4 shared workflows)
   - `.agent/rules/` deployed (2 shared rules)
   - Global skills available (`/code_review`, `/debug_issue`, etc.)
   - `AGENTS.md` created
