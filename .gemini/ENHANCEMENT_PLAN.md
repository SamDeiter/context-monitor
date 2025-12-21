# Context Monitor Enhancement Plan

**Created:** 2025-12-21  
**Status:** In Progress (Sprint 1 complete)  
**Priority Legend:** 🔴 High | 🟡 Medium | 🟢 Low

---

## Phase 1: Performance Improvements
*Goal: Make the widget faster and more responsive*

### 1.1 Lazy File Parsing 🔴 ✅

- [x] Only read the last 20KB of `.pb` files for project detection
- [x] Avoid loading entire conversation files into memory
- [x] **Estimated effort:** 30 min

### 1.2 Threaded Updates 🔴 (Partial)

- [x] Threading infrastructure added
- [ ] Move file scanning to a background thread (pending)
- [x] Prevent UI freezing during refresh
- [x] Use `threading.Thread` with queue for results
- [ ] **Estimated effort:** 1 hour

### 1.3 Cached History 🟡 ✅

- [x] Keep history data in memory after first load
- [x] Only write to disk, don't re-read on every refresh
- [x] Invalidate cache when session changes
- [x] **Estimated effort:** 30 min

### 1.4 Debounced Saves 🟡 ✅

- [x] Batch history writes to reduce disk I/O
- [x] Write at most once every 10 seconds
- [x] Flush on app close
- [x] **Estimated effort:** 20 min

---

## Phase 2: New Features
*Goal: Add useful functionality*

### 2.1 Session Picker Dropdown 🔴
- [ ] Add dropdown/combobox to switch between active conversations
- [ ] Show project name and last modified time
- [ ] Persist selection across refreshes
- [ ] **Estimated effort:** 45 min

### 2.2 Token Alerts / Desktop Notifications 🔴
- [ ] Windows toast notification at 60% threshold (warning)
- [ ] Windows toast notification at 80% threshold (critical)
- [ ] Auto-copy handoff on 80% (already implemented)
- [ ] Option to mute notifications
- [ ] **Estimated effort:** 1 hour

### 2.3 Estimated Time Remaining 🔴
- [ ] Calculate token burn rate from history (tokens/minute)
- [ ] Display "~X min remaining" in UI
- [ ] Update on each refresh
- [ ] Handle edge cases (no history, flat usage)
- [ ] **Estimated effort:** 45 min

### 2.4 Export History to CSV 🟡
- [ ] Add "Export" option in context menu
- [ ] Export all sessions or current session
- [ ] Include: timestamp, tokens, delta, project
- [ ] Save to Downloads folder
- [ ] **Estimated effort:** 30 min

### 2.5 Session Timeline 🟡
- [ ] Visual timeline showing context resets
- [ ] Mark when new sessions started
- [ ] Clickable to switch sessions
- [ ] **Estimated effort:** 1.5 hours

### 2.6 Global Hotkey (Win+Shift+T) 🟢
- [ ] Register global hotkey to show/hide widget
- [ ] Use `keyboard` or `pynput` library
- [ ] Configurable keybinding
- [ ] **Estimated effort:** 1 hour

### 2.7 Multi-Monitor Support 🟢
- [ ] Detect which monitor widget is on
- [ ] Remember position per monitor
- [ ] Handle monitor disconnect gracefully
- [ ] **Estimated effort:** 1 hour

### 2.8 Dark/Light Theme Toggle 🟢
- [ ] Add light theme color palette
- [ ] Toggle in settings/context menu
- [ ] Persist preference
- [ ] **Estimated effort:** 45 min

---

## Phase 3: UI/UX Improvements
*Goal: Make the widget more polished and delightful*

### 3.1 Animated Gauge 🔴
- [ ] Smooth transition when percentage changes
- [ ] Ease-in-out animation over 300ms
- [ ] Use `after()` for frame updates
- [ ] **Estimated effort:** 1 hour

### 3.2 Compact Sparkline Graph 🟡
- [ ] Replace RECENT numbers with mini sparkline
- [ ] Show last 10 deltas as visual graph
- [ ] Color gradient based on magnitude
- [ ] **Estimated effort:** 1 hour

### 3.3 Hover Tooltips 🟡
- [ ] Explain delta numbers on hover
- [ ] Show timestamp of each delta
- [ ] Improve existing tooltips
- [ ] **Estimated effort:** 30 min

### 3.4 Status LED Indicator 🟢
- [ ] Replace text status with pulsing LED dot
- [ ] Green = healthy, Yellow = warning, Red = critical
- [ ] Subtle pulse animation
- [ ] **Estimated effort:** 30 min

### 3.5 Snap to Screen Edges 🟢
- [ ] Auto-snap when dragged within 20px of edge
- [ ] Magnetic effect for clean positioning
- [ ] Snap to corners and edges
- [ ] **Estimated effort:** 45 min

### 3.6 Minimize Animation 🟢
- [ ] Smooth shrink/expand when toggling mini mode
- [ ] Fade transition
- [ ] **Estimated effort:** 1 hour

### 3.7 Full Keyboard Navigation 🟢
- [ ] Arrow keys to navigate
- [ ] Enter to select
- [ ] Escape to close popups
- [ ] Tab focus ring
- [ ] **Estimated effort:** 1 hour

---

## Phase 4: Quality of Life
*Goal: Polish and convenience features*

### 4.1 Auto-Pause When Idle 🟡
- [ ] Detect when no IDE activity for 5+ minutes
- [ ] Slow down polling to conserve resources
- [ ] Resume normal polling on activity
- [ ] **Estimated effort:** 45 min

### 4.2 Settings Panel GUI 🟡
- [ ] Modal window for all settings
- [ ] Refresh rate slider
- [ ] Threshold configuration
- [ ] Theme selection
- [ ] Notification toggles
- [ ] **Estimated effort:** 2 hours

### 4.3 Optional Windows Startup 🟢
- [ ] Checkbox in settings to enable startup
- [ ] Add/remove from registry
- [ ] Verify startup entry exists
- [ ] **Estimated effort:** 30 min

### 4.4 Enhanced Tray Icon Menu 🟢
- [ ] Add more options to system tray
- [ ] Quick access to settings
- [ ] Show current usage in tooltip
- [ ] **Estimated effort:** 30 min

---

## Implementation Order (Recommended)

### Sprint 1: Core Performance (2-3 hours) ✅

1. [x] 1.1 Lazy File Parsing
2. [x] 1.2 Threaded Updates (infrastructure)
3. [x] 1.3 Cached History

### Sprint 2: Key Features (3-4 hours)
4. [ ] 2.3 Estimated Time Remaining
5. [ ] 2.1 Session Picker Dropdown
6. [ ] 3.1 Animated Gauge

### Sprint 3: Notifications & Export (2 hours)
7. [ ] 2.2 Token Alerts
8. [ ] 2.4 Export History to CSV

### Sprint 4: UI Polish (3-4 hours)
9. [ ] 3.2 Compact Sparkline Graph
10. [ ] 3.5 Snap to Screen Edges
11. [ ] 3.4 Status LED Indicator

### Sprint 5: Settings & QoL (2-3 hours)
12. [ ] 4.2 Settings Panel GUI
13. [ ] 4.1 Auto-Pause When Idle
14. [ ] 4.3 Optional Windows Startup

### Sprint 6: Nice-to-Have (3+ hours)
15. [ ] 2.5 Session Timeline
16. [ ] 2.6 Global Hotkey
17. [ ] 2.7 Multi-Monitor Support
18. [ ] 2.8 Dark/Light Theme Toggle
19. [ ] 3.6 Minimize Animation
20. [ ] 3.7 Full Keyboard Navigation

---

## Total Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1: Performance | ~2.5 hours |
| Phase 2: Features | ~7 hours |
| Phase 3: UI/UX | ~5.5 hours |
| Phase 4: QoL | ~4 hours |
| **Total** | **~19 hours** |

---

## Dependencies

- `win10toast` or `plyer` - For Windows notifications
- `keyboard` or `pynput` - For global hotkeys (optional)
- No other new dependencies needed

---

## Notes

- All features should be backwards compatible
- Settings should migrate gracefully
- Focus on stability before adding new features
- Test each phase before moving to next

---

*Last Updated: 2025-12-21 (Sprint 1 complete)*
