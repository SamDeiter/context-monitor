/**
 * Context Compass - Antigravity Token Tracker
 * A floating widget to monitor token usage and generate handoff prompts
 */

class ContextCompass {
    constructor() {
        this.elements = {
            widget: document.getElementById('widget'),
            dragHandle: document.getElementById('dragHandle'),
            minimizeBtn: document.getElementById('minimizeBtn'),
            widgetContent: document.getElementById('widgetContent'),
            tokensLeft: document.getElementById('tokensLeft'),
            contextWindow: document.getElementById('contextWindow'),
            gaugeFill: document.getElementById('gaugeFill'),
            gaugePercent: document.getElementById('gaugePercent'),
            warningBanner: document.getElementById('warningBanner'),
            contextNotes: document.getElementById('contextNotes'),
            conversationId: document.getElementById('conversationId'),
            handoffSection: document.getElementById('handoffSection'),
            handoffOutput: document.getElementById('handoffOutput'),
            generateBtn: document.getElementById('generateBtn'),
            clearBtn: document.getElementById('clearBtn'),
            copyBtn: document.getElementById('copyBtn')
        };

        this.circumference = 2 * Math.PI * 50; // Circle radius = 50
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.lastAlertTime = 0;
        this.alertCooldown = 30000; // 30 seconds between alerts
        this.audioContext = null;

        this.init();
    }

    initAudio() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
    }

    playAlert() {
        const now = Date.now();
        if (now - this.lastAlertTime < this.alertCooldown) return;
        this.lastAlertTime = now;

        this.initAudio();
        const ctx = this.audioContext;

        // Create a pleasant but attention-grabbing two-tone alert
        const playTone = (freq, startTime, duration) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.frequency.value = freq;
            osc.type = 'sine';
            
            gain.gain.setValueAtTime(0, startTime);
            gain.gain.linearRampToValueAtTime(0.3, startTime + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
            
            osc.start(startTime);
            osc.stop(startTime + duration);
        };

        const now2 = ctx.currentTime;
        // Three-note ascending chime
        playTone(523.25, now2, 0.15);        // C5
        playTone(659.25, now2 + 0.15, 0.15); // E5
        playTone(783.99, now2 + 0.30, 0.3);  // G5

        // Trigger shake animation
        this.elements.widget.classList.add('shake');
        setTimeout(() => {
            this.elements.widget.classList.remove('shake');
        }, 500);
    }

    init() {
        this.loadState();
        this.bindEvents();
        this.updateGauge();
    }

    bindEvents() {
        // Token input changes
        this.elements.tokensLeft.addEventListener('input', () => {
            this.updateGauge();
            this.saveState();
        });

        this.elements.contextWindow.addEventListener('change', () => {
            this.updateGauge();
            this.saveState();
        });

        // Notes auto-save
        this.elements.contextNotes.addEventListener('input', () => {
            this.saveState();
        });

        // Conversation ID auto-save
        this.elements.conversationId.addEventListener('input', () => {
            this.saveState();
        });

        // Minimize toggle
        this.elements.minimizeBtn.addEventListener('click', () => {
            this.elements.widget.classList.toggle('minimized');
            this.elements.minimizeBtn.textContent = 
                this.elements.widget.classList.contains('minimized') ? '+' : '−';
            this.saveState();
        });

        // Generate handoff
        this.elements.generateBtn.addEventListener('click', () => {
            this.generateHandoff();
        });

        // Clear all
        this.elements.clearBtn.addEventListener('click', () => {
            if (confirm('Clear all notes and reset?')) {
                this.elements.contextNotes.value = '';
                this.elements.tokensLeft.value = '';
                this.elements.handoffSection.classList.remove('visible');
                this.updateGauge();
                this.saveState();
            }
        });

        // Copy to clipboard
        this.elements.copyBtn.addEventListener('click', () => {
            this.copyToClipboard();
        });

        // Drag functionality
        this.elements.dragHandle.addEventListener('mousedown', (e) => this.startDrag(e));
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('mouseup', () => this.endDrag());

        // Touch support
        this.elements.dragHandle.addEventListener('touchstart', (e) => this.startDrag(e.touches[0]));
        document.addEventListener('touchmove', (e) => this.drag(e.touches[0]));
        document.addEventListener('touchend', () => this.endDrag());
    }

    updateGauge() {
        const tokensLeftStr = this.elements.tokensLeft.value.replace(/,/g, '');
        const tokensLeft = parseInt(tokensLeftStr) || 0;
        const contextWindow = parseInt(this.elements.contextWindow.value);

        const tokensUsed = contextWindow - tokensLeft;
        const percentUsed = tokensLeft > 0 ? Math.min(100, Math.max(0, (tokensUsed / contextWindow) * 100)) : 0;

        // Update gauge visual
        const offset = this.circumference - (percentUsed / 100) * this.circumference;
        this.elements.gaugeFill.style.strokeDashoffset = offset;

        // Update color based on threshold
        this.elements.gaugeFill.classList.remove('warning', 'danger');
        this.elements.widget.classList.remove('warning-state', 'danger-state');
        
        if (percentUsed >= 80) {
            this.elements.gaugeFill.classList.add('danger');
            this.elements.widget.classList.add('danger-state');
            this.elements.warningBanner.classList.add('visible');
            // Play alert when crossing into danger zone
            if (tokensLeft > 0) {
                this.playAlert();
            }
        } else if (percentUsed >= 60) {
            this.elements.gaugeFill.classList.add('warning');
            this.elements.widget.classList.add('warning-state');
            this.elements.warningBanner.classList.remove('visible');
        } else {
            this.elements.warningBanner.classList.remove('visible');
        }

        // Update percentage text
        this.elements.gaugePercent.textContent = `${Math.round(percentUsed)}%`;
    }

    generateHandoff() {
        const tokensLeftStr = this.elements.tokensLeft.value.replace(/,/g, '');
        const tokensLeft = parseInt(tokensLeftStr) || 0;
        const contextWindow = parseInt(this.elements.contextWindow.value);
        const tokensUsed = contextWindow - tokensLeft;
        const percentUsed = Math.round((tokensUsed / contextWindow) * 100);

        const notes = this.elements.contextNotes.value.trim();
        const conversationId = this.elements.conversationId.value.trim() || 'Not specified';
        const timestamp = new Date().toLocaleString();

        // Parse notes to extract structured info
        const parsed = this.parseNotes(notes);

        const handoff = `## 🧭 Context Handoff
**Generated:** ${timestamp}
**Conversation ID:** ${conversationId}
**Session Usage:** ${tokensUsed.toLocaleString()} / ${contextWindow.toLocaleString()} tokens (${percentUsed}% used)

---

### Current Task
${parsed.task || 'Not specified'}

### Progress
${parsed.progress || 'No progress noted'}

### Key Files
${parsed.files || 'No files mentioned'}

### Decisions Made
${parsed.decisions || 'No decisions recorded'}

### Next Steps
${parsed.nextSteps || 'No next steps defined'}

### Additional Context
${parsed.other || 'None'}

---
*Handoff generated by Context Compass*`;

        this.elements.handoffOutput.textContent = handoff;
        this.elements.handoffSection.classList.add('visible');
    }

    parseNotes(notes) {
        const result = {
            task: '',
            progress: '',
            files: '',
            decisions: '',
            nextSteps: '',
            other: ''
        };

        if (!notes) return result;

        const lines = notes.split('\n');
        let currentSection = 'other';

        for (const line of lines) {
            const lower = line.toLowerCase();
            
            if (lower.includes('task:') || lower.includes('objective:') || lower.includes('goal:')) {
                currentSection = 'task';
                result.task += line.replace(/^[•\-\*]\s*/, '').replace(/task:|objective:|goal:/i, '').trim() + '\n';
            } else if (lower.includes('progress:') || lower.includes('done:') || lower.includes('completed:')) {
                currentSection = 'progress';
                result.progress += line.replace(/^[•\-\*]\s*/, '').replace(/progress:|done:|completed:/i, '').trim() + '\n';
            } else if (lower.includes('file:') || lower.includes('files:') || lower.includes('modified:')) {
                currentSection = 'files';
                result.files += line.replace(/^[•\-\*]\s*/, '').replace(/files?:|modified:/i, '').trim() + '\n';
            } else if (lower.includes('decision:') || lower.includes('decided:') || lower.includes('choice:')) {
                currentSection = 'decisions';
                result.decisions += line.replace(/^[•\-\*]\s*/, '').replace(/decisions?:|decided:|choice:/i, '').trim() + '\n';
            } else if (lower.includes('next:') || lower.includes('todo:') || lower.includes('next step')) {
                currentSection = 'nextSteps';
                result.nextSteps += line.replace(/^[•\-\*]\s*/, '').replace(/next:|todo:|next steps?:/i, '').trim() + '\n';
            } else if (line.trim()) {
                result[currentSection] += line.replace(/^[•\-\*]\s*/, '') + '\n';
            }
        }

        // Trim all sections
        for (const key in result) {
            result[key] = result[key].trim();
        }

        return result;
    }

    async copyToClipboard() {
        const text = this.elements.handoffOutput.textContent;
        try {
            await navigator.clipboard.writeText(text);
            this.elements.copyBtn.classList.add('copied');
            this.elements.copyBtn.textContent = '✓ Copied!';
            setTimeout(() => {
                this.elements.copyBtn.classList.remove('copied');
                this.elements.copyBtn.textContent = '📋 Copy to Clipboard';
            }, 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    }

    // Drag functionality
    startDrag(e) {
        this.isDragging = true;
        const rect = this.elements.widget.getBoundingClientRect();
        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
        this.elements.widget.style.transition = 'none';
    }

    drag(e) {
        if (!this.isDragging) return;
        
        const x = e.clientX - this.dragOffset.x;
        const y = e.clientY - this.dragOffset.y;

        // Keep widget within viewport
        const maxX = window.innerWidth - this.elements.widget.offsetWidth;
        const maxY = window.innerHeight - this.elements.widget.offsetHeight;

        this.elements.widget.style.left = `${Math.max(0, Math.min(x, maxX))}px`;
        this.elements.widget.style.top = `${Math.max(0, Math.min(y, maxY))}px`;
        this.elements.widget.style.right = 'auto';
    }

    endDrag() {
        if (this.isDragging) {
            this.isDragging = false;
            this.elements.widget.style.transition = '';
            this.saveState();
        }
    }

    // Persistence
    saveState() {
        const state = {
            tokensLeft: this.elements.tokensLeft.value,
            contextWindow: this.elements.contextWindow.value,
            notes: this.elements.contextNotes.value,
            conversationId: this.elements.conversationId.value,
            minimized: this.elements.widget.classList.contains('minimized'),
            position: {
                left: this.elements.widget.style.left,
                top: this.elements.widget.style.top
            }
        };
        localStorage.setItem('contextCompass', JSON.stringify(state));
    }

    loadState() {
        try {
            const saved = localStorage.getItem('contextCompass');
            if (saved) {
                const state = JSON.parse(saved);
                
                if (state.tokensLeft) {
                    this.elements.tokensLeft.value = state.tokensLeft;
                }
                if (state.contextWindow) {
                    this.elements.contextWindow.value = state.contextWindow;
                }
                if (state.notes) {
                    this.elements.contextNotes.value = state.notes;
                }
                if (state.conversationId) {
                    this.elements.conversationId.value = state.conversationId;
                }
                if (state.minimized) {
                    this.elements.widget.classList.add('minimized');
                    this.elements.minimizeBtn.textContent = '+';
                }
                if (state.position?.left) {
                    this.elements.widget.style.left = state.position.left;
                    this.elements.widget.style.top = state.position.top;
                    this.elements.widget.style.right = 'auto';
                }
            }
        } catch (err) {
            console.error('Failed to load state:', err);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.contextCompass = new ContextCompass();
});
