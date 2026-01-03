# Task: Run and Stabilize Context Monitor

The goal is to ensure the Context Monitor is running correctly, provide accurate token usage data ("useful tokens"), and fix the recurring "logs" directory error.

## Steps

1. [X] **Investigate "logs" directory usage**: Identified hardcoded paths and missing directory creation as root causes.
2. [X] **Verify Token Accuracy**: Refined `extract_pb_tokens` threshold (100k -> 100) to ensure accurate parsing for all session sizes.
3. [X] **Fix Directory Errors**: Implemented `ensure_logs_dir()` to proactively create the `.system_generated/logs` path.
4. [X] **Run and Verify**: Application launched and verified via `output.log` and `check_stats.py`.
5. [ ] **Improve Readability**: Increase font sizes for "Recent" deltas and main token labels.
6. [ ] **Update Documentation**: Note changes in `TECH_STACK.md`.
