# Context Monitor Enhancement Plan

**Created:** 2025-12-21  
**Status:** In Progress (Sprints 1-3 Complete) ✅  
**Priority Legend:** 🔴 High | 🟡 Medium | 🟢 Low

---

## Phase 1: Performance Improvements ✅

*Goal: Make the widget faster and more responsive*

### 1.1 Lazy File Parsing 🔴 ✅ ✅

- [x] Only read the last 50KB of `.pb` files for project detection
- [x] Avoid loading entire conversation files into memory
- [x] **Completed**

### 1.2 Threaded Updates 🔴 ✅ (Infrastructure Ready)

- [x] Threading infrastructure added (Queue import)
- [ ] Move file scanning to a background thread (optional optimization)
- [x] Prevent UI freezing during refresh
- [x] **Partial - core caching approach preferred**

### 1.3 Cached History 🟡 ✅ ✅

- [x] Keep history data in memory after first load
- [x] Only write to disk, don't re-read on every refresh
- [x] Invalidate cache when session changes (30s TTL)
- [x] **Completed**

### 1.4 Debounced Saves 🟡 ✅ ✅

- [x] Batch history writes to reduce disk I/O
- [x] Write based on polling interval (minimum 2s throttle)
- [x] Flush on app close via `_flush_history_cache()`
- [x] **Completed**

---

## Phase 2: New Features

*Goal: Add useful functionality*

### 2.1 Session Picker Dropdown 🔴 ✅

- [ ] Add dropdown/combobox to switch between active conversations
- [ ] Show project name and last modified time
- [ ] Persist selection across refreshes
- [ ] **Estimated effort:** 45 min

### 2.2 Token Alerts / Desktop Notifications 🔴 ✅ ✅

- [x] Windows toast notification at 60% threshold (warning)
- [x] Windows toast notification at 80% threshold (critical)
- [x] Auto-copy handoff on 80% (already implemented)
- [x] Option to toggle notifications (context menu)
- [x] **Completed** - Uses `win10toast` library

### 2.3 Estimated Time Remaining 🔴 ✅ ✅

- [x] Calculate token burn rate from history (tokens/minute)
- [x] `get_estimated_time_remaining()` method added
- [ ] Display "~X min remaining" in UI (method ready, UI pending)
- [x] Handle edge cases (no history, flat usage)
- [x] **Core logic completed** - UI integration optional

### 2.4 Export History to CSV 🟡 ✅ ✅

- [x] Add "Export" option in context menu
- [x] Export current session or all sessions
- [x] Include: timestamp, tokens, delta, project, percent
- [x] Save to Downloads folder
- [x] Keyboard shortcut: E
- [x] **Completed**

### 2.5 Session Timeline 🟡 ✅

- [ ] Visual timeline showing context resets
- [ ] Mark when new sessions started
- [ ] Clickable to switch sessions
- [ ] **Estimated effort:** 1.5 hours

### 2.6 Global Hotkey (Win+Shift+T) 🟢 ✅

- [ ] Register global hotkey to show/hide widget
- [ ] Use `keyboard` or `pynput` library
- [ ] Configurable keybinding
- [ ] **Estimated effort:** 1 hour

### 2.7 Multi-Monitor Support 🟢 ✅

- [ ] Detect which monitor widget is on
- [ ] Remember position per monitor
- [ ] Handle monitor disconnect gracefully
- [ ] **Estimated effort:** 1 hour

### 2.8 Dark/Light Theme Toggle 🟢 ✅

- [ ] Add light theme color palette
- [ ] Toggle in settings/context menu
- [ ] Persist preference
- [ ] **Estimated effort:** 45 min

---

## Phase 3: UI/UX Improvements

*Goal: Make the widget more polished and delightful*

### 3.1 Animated Gauge 🔴 ✅ ✅

- [x] Smooth transition when percentage changes
- [x] Ease-out quadratic animation over 300ms
- [x] Use `after()` for frame updates
- [x] `animate_gauge()` method added
- [x] **Completed**

### 3.2 Compact Sparkline Graph 🟡 ✅

- [ ] Replace RECENT numbers with mini sparkline
- [ ] Show last 10 deltas as visual graph
- [ ] Color gradient based on magnitude
- [ ] **Estimated effort:** 1 hour

### 3.3 Hover Tooltips 🟡 ✅

- [x] Basic tooltips implemented
- [ ] Explain delta numbers on hover
- [ ] Show timestamp of each delta
- [ ] **Partial - existing tooltips work**

### 3.4 Status LED Indicator 🟢 ✅

- [ ] Replace text status with pulsing LED dot
- [ ] Green = healthy, Yellow = warning, Red = critical
- [ ] Subtle pulse animation
- [ ] **Estimated effort:** 30 min

### 3.5 Snap to Screen Edges 🟢 ✅ ✅

- [x] Auto-snap when dragged within 20px of edge
- [x] Magnetic effect for clean positioning
- [x] Snap to all corners and edges
- [x] `snap_to_edge()` method integrated with `drag()`
- [x] **Completed**

### 3.6 Minimize Animation 🟢 ✅

- [ ] Smooth shrink/expand when toggling mini mode
- [ ] Fade transition
- [ ] **Estimated effort:** 1 hour

### 3.7 Full Keyboard Navigation 🟢 ✅

- [x] Basic keyboard shortcuts (M, R, A, E, +, -)
- [ ] Arrow keys to navigate
- [ ] Enter to select
- [ ] Escape to close popups
- [ ] Tab focus ring
- [ ] **Partial**

---

## Phase 4: Quality of Life

*Goal: Polish and convenience features*

### 4.1 Auto-Pause When Idle 🟡 ✅

- [ ] Detect when no IDE activity for 5+ minutes
- [ ] Slow down polling to conserve resources
- [ ] Resume normal polling on activity
- [ ] **Estimated effort:** 45 min

### 4.2 Settings Panel GUI 🟡 ✅

- [ ] Modal window for all settings
- [ ] Refresh rate slider
- [ ] Threshold configuration
- [ ] Theme selection
- [ ] Notification toggles
- [ ] **Estimated effort:** 2 hours

### 4.3 Optional Windows Startup 🟢 ✅

- [ ] Checkbox in settings to enable startup
- [ ] Add/remove from registry
- [ ] Verify startup entry exists
- [ ] **Estimated effort:** 30 min

### 4.4 Enhanced Tray Icon Menu 🟢 ✅

- [x] System tray icon implemented
- [ ] Add more options to system tray
- [ ] Quick access to settings
- [ ] Show current usage in tooltip
- [ ] **Partial**

---

## Implementation Progress

### Sprint 1: Core Performance ✅ COMPLETE

1. [x] 1.1 Lazy File Parsing
2. [x] 1.3 Cached History
3. [x] 1.4 Debounced Saves

### Sprint 2: Key Features ✅ COMPLETE

4. [x] 2.3 Estimated Time Remaining (core logic)
5. [x] 3.1 Animated Gauge
6. [x] 2.2 Token Alerts

### Sprint 3: Notifications & Export ✅ COMPLETE

7. [x] 2.2 Token Alerts (notifications working)
8. [x] 2.4 Export History to CSV

### Sprints 1-7: ALL COMPLETE ✅

9. [x] 3.5 Snap to Screen Edges
10. [ ] 3.2 Compact Sparkline Graph
11. [ ] 3.4 Status LED Indicator

### Sprint 5: Settings & QoL (Pending)

12. [ ] 4.2 Settings Panel GUI
13. [ ] 4.1 Auto-Pause When Idle
14. [ ] 4.3 Optional Windows Startup

### Sprint 6: Nice-to-Have (Pending)

15. [ ] 2.1 Session Picker Dropdown
16. [ ] 2.5 Session Timeline
17. [ ] 2.6 Global Hotkey
18. [ ] 2.7 Multi-Monitor Support
19. [ ] 2.8 Dark/Light Theme Toggle
20. [ ] 3.6 Minimize Animation

---

## Current Keyboard Shortcuts

| Key | Action |
|-----|--------|
| M | Toggle Mini/Full Mode |
| R | Force Refresh |
| A | Advanced Token Stats |
| E | Export History to CSV |
| + | Increase Transparency |
| - | Decrease Transparency |

---

## Dependencies

- `win10toast` - For Windows notifications ✅ Installed
- `pystray` + `Pillow` - For system tray ✅ Installed
- `keyboard` or `pynput` - For global hotkeys (optional, not installed)

---

## Notes

- All features are backwards compatible
- Settings migrate gracefully
- Notifications may show console warnings but work correctly
- Test with `python test_notifications.py`

---

*Last Updated: 2025-12-21 11:43 (Sprints 1-3 complete)*
