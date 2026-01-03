# Implementation Plan - Context Monitor Stabilization

## 1. Problem Statement

The user reported that the application often fails when trying to access a `logs` directory that doesn't exist. Additionally, they emphasized that "tokens need to be useful," implying the current extraction/estimation might be inaccurate or the UI isn't displaying them effectively. Recently, the user also noted that the "recent tokens" display is hard to read.

## 2. Proposed Changes

### 2.1 Directory Resilience

- Search for all hardcoded or dynamically generated paths that might point to a `logs` folder.
- Added `ensure_logs_dir()` to proactively create required directories at startup.
- Add error handling around directory listing/scanning to prevent crashes if a target folder is missing.

### 2.2 Token Extraction Accuracy ("Useful Tokens")

- Refined `extract_pb_tokens` in `context_monitor.pyw` with a lower threshold (100 tokens) to catch smaller sessions.
- Ensured `Path.home()` is used for all user-specific paths to avoid hardcoded user names.

### 2.3 UI/UX Enhancements & Readability

- **Font Size Bump**: Increase "tokens remaining" font size from 14 to 18.
- **Recent List**: Increase "RECENT" delta list font size from 8 to 11.
- **Bold Deltas**: Make the latest delta in the history panel bold for better visibility.
- **Contrast**: Ensure colors are distinct for different token magnitudes.

## 3. Verification Plan

- **Pre-check**: Run a script to find and create missing directories.
- **Dry Run**: Run the app in a terminal where stdout/stderr can be captured.
- **Live Test**: Verify the UI updates correctly when new tokens are added.
- **Log Review**: Check `error.log` and `output.log` for any new issues.

## 4. Risks

- Protobuf format changes in Antigravity could break the heuristic parser.
- Windows file locking might prevent reading the `.pb` file while Antigravity is writing it.
