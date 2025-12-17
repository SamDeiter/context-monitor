/**
 * Session Fuel - Simple token tracker
 * Auto-loads most recent session, shows gauge and status
 */

class SessionFuel {
    constructor() {
        this.elements = {
            widget: document.getElementById('widget'),
            minimizeBtn: document.getElementById('minimizeBtn'),
            gaugeFill: document.getElementById('gaugeFill'),
            gaugePercent: document.getElementById('gaugePercent'),
            tokensLeft: document.getElementById('tokensLeft'),
            sessionId: document.getElementById('sessionId'),
            statusBar: document.getElementById('statusBar'),
            statusText: document.getElementById('statusText'),
            handoffBtn: document.getElementById('handoffBtn'),
            handoffSection: document.getElementById('handoffSection'),
            handoffOutput: document.getElementById('handoffOutput'),
            copyBtn: document.getElementById('copyBtn')
        };

        this.circumference = 2 * Math.PI * 50;
        this.session = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSession();
        // Auto-refresh every 30 seconds
        setInterval(() => this.loadSession(), 30000);
    }

    bindEvents() {
        this.elements.minimizeBtn.addEventListener('click', () => {
            this.elements.widget.classList.toggle('minimized');
            this.elements.minimizeBtn.textContent = 
                this.elements.widget.classList.contains('minimized') ? '+' : '−';
        });

        this.elements.handoffBtn.addEventListener('click', () => this.generateHandoff());
        this.elements.copyBtn.addEventListener('click', () => this.copyHandoff());
    }

    async loadSession() {
        try {
            const response = await fetch('/api/sessions');
            const data = await response.json();
            
            if (data.activeSession) {
                this.session = data.activeSession;
                this.updateDisplay();
            }
        } catch (err) {
            this.elements.statusText.textContent = 'Server not running';
            this.elements.statusBar.className = 'status-bar warning';
        }
    }

    updateDisplay() {
        const contextWindow = 200000; // 200K default
        const tokensUsed = Math.round(this.session.estimatedTokens / 10);
        const tokensLeft = Math.max(0, contextWindow - tokensUsed);
        const percentUsed = Math.min(100, Math.round((tokensUsed / contextWindow) * 100));

        // Update gauge
        const offset = this.circumference - (percentUsed / 100) * this.circumference;
        this.elements.gaugeFill.style.strokeDashoffset = offset;
        this.elements.gaugePercent.textContent = percentUsed + '%';

        // Update gauge color
        this.elements.gaugeFill.classList.remove('warning', 'danger');
        if (percentUsed >= 80) {
            this.elements.gaugeFill.classList.add('danger');
        } else if (percentUsed >= 60) {
            this.elements.gaugeFill.classList.add('warning');
        }

        // Update info
        this.elements.tokensLeft.textContent = tokensLeft.toLocaleString();
        this.elements.sessionId.textContent = this.session.id.slice(0, 18) + '...';

        // Update status
        this.updateStatus(percentUsed);
    }

    updateStatus(percent) {
        const bar = this.elements.statusBar;
        const text = this.elements.statusText;
        const icon = bar.querySelector('.status-icon');

        bar.classList.remove('warning', 'danger');

        if (percent >= 80) {
            bar.classList.add('danger');
            icon.textContent = '⚠️';
            text.textContent = 'Generate handoff now!';
        } else if (percent >= 60) {
            bar.classList.add('warning');
            icon.textContent = '⚡';
            text.textContent = 'Approaching limit';
        } else {
            icon.textContent = '✓';
            text.textContent = 'Plenty of fuel';
        }
    }

    generateHandoff() {
        if (!this.session) return;

        const contextWindow = 200000;
        const tokensUsed = Math.round(this.session.estimatedTokens / 10);
        const tokensLeft = Math.max(0, contextWindow - tokensUsed);
        const percentUsed = Math.round((tokensUsed / contextWindow) * 100);

        const handoff = `## Session Handoff
**Session:** ${this.session.id}
**Usage:** ${percentUsed}% (${tokensLeft.toLocaleString()} tokens left)
**Generated:** ${new Date().toLocaleString()}

Continue from this session. Key context was preserved.`;

        this.elements.handoffOutput.textContent = handoff;
        this.elements.handoffSection.classList.add('visible');
    }

    async copyHandoff() {
        try {
            await navigator.clipboard.writeText(this.elements.handoffOutput.textContent);
            this.elements.copyBtn.textContent = '✓ Copied!';
            setTimeout(() => {
                this.elements.copyBtn.textContent = '📋 Copy';
            }, 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.sessionFuel = new SessionFuel();
});
