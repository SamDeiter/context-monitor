# Implementation Plan - Context Monitor Stabilization

## 1. Problem Statement

The user reported that the application often fails when trying to access a `logs` directory that doesn't exist. Additionally, they emphasized that "tokens need to be useful," implying the current extraction/estimation might be inaccurate or the UI isn't displaying them effectively.

## 2. Proposed Changes

### 2.1 Directory Resilience

- Search for all hardcoded or dynamically generated paths that might point to a `logs` folder.
- Add `os.makedirs(path, exist_ok=True)` at startup for any required directories.
- Add error handling around directory listing/scanning to prevent crashes if a target folder is missing.

### 2.2 Token Extraction Accuracy ("Useful Tokens")

- Refine `extract_pb_tokens` in `context_monitor.pyw`.
- The current heuristic searches for varints in the tail of the `.pb` file. I will verify if there's a more reliable way to identify the "tokens_used" and "context_window" fields in the protobuf stream without a full schema.
- Ensure the "fallback" estimation (file size / 40) is clearly marked as an estimate in the UI if protobuf parsing fails.

### 2.3 UI/UX Enhancements

- Ensure the "delta" tracking is clear so the user knows how much a specific turn "cost" in tokens.
- Add a refresh status indicator that shows when the last successful parse occurred.

## 3. Verification Plan

- **Pre-check**: Run a script to find and create missing directories.
- **Dry Run**: Run the app in a terminal where stdout/stderr can be captured.
- **Live Test**: Verify the UI updates correctly when I (the agent) send messages (which updates the `.pb` file).
- **Log Review**: Check `error.log` and `output.log` for any new issues.

## 4. Risks

- Protobuf format changes in Antigravity could break the heuristic parser.
- Windows file locking might prevent reading the `.pb` file while Antigravity is writing it.
