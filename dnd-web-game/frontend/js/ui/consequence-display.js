/**
 * D&D Combat Engine - Consequence Display
 * Shows BG3-style consequence notifications
 *
 * Features:
 * - "Your choice will be remembered" messages
 * - NPC disposition change indicators
 * - Delayed consequence reveals
 * - Consequence history tracking
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

/**
 * Escape HTML special characters
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

/**
 * Consequence Display Manager
 */
class ConsequenceDisplay {
    constructor() {
        this.container = null;
        this.queue = [];
        this.isShowing = false;
        this.history = [];

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        // Main notification container
        this.container = document.createElement('div');
        this.container.id = 'consequence-display';
        this.container.className = 'consequence-display hidden';
        document.body.appendChild(this.container);

        // History panel (collapsible)
        this.historyPanel = document.createElement('div');
        this.historyPanel.id = 'consequence-history';
        this.historyPanel.className = 'consequence-history hidden';
        this.historyPanel.innerHTML = `
            <div class="history-header">
                <span class="history-title">Story Consequences</span>
                <button class="history-close">&times;</button>
            </div>
            <div class="history-content"></div>
        `;
        document.body.appendChild(this.historyPanel);

        // Close button handler
        this.historyPanel.querySelector('.history-close').addEventListener('click', () => {
            this.hideHistory();
        });
    }

    setupEventListeners() {
        // Listen for consequence events
        eventBus.on(EVENTS.CONSEQUENCE_TRIGGERED, (data) => {
            this.showConsequence(data);
        });

        eventBus.on(EVENTS.CHOICE_REMEMBERED, (data) => {
            this.showRemembered(data);
        });

        eventBus.on(EVENTS.NPC_DISPOSITION_CHANGED, (data) => {
            this.showDispositionChange(data);
        });

        // Keyboard shortcut to show history (H key)
        document.addEventListener('keydown', (e) => {
            if (e.key.toLowerCase() === 'h' && e.ctrlKey) {
                e.preventDefault();
                this.toggleHistory();
            }
        });
    }

    // =========================================================================
    // CONSEQUENCE NOTIFICATIONS
    // =========================================================================

    /**
     * Show a consequence notification (triggered consequence)
     */
    showConsequence(data) {
        const notification = {
            type: 'consequence',
            icon: '⚡',
            title: data.title || 'Consequence',
            text: data.text || 'Your past actions have caught up with you.',
            subtext: data.subtext || null,
            duration: data.duration || 5000,
        };

        this.addToHistory(notification);
        this.queueNotification(notification);
    }

    /**
     * Show "Your choice will be remembered" style message
     */
    showRemembered(data) {
        const notification = {
            type: 'remembered',
            icon: '📜',
            title: null,
            text: data.text || 'Your choice will be remembered.',
            subtext: data.npc ? `${escapeHtml(data.npc)} will remember this.` : null,
            duration: data.duration || 3500,
        };

        this.addToHistory(notification);
        this.queueNotification(notification);
    }

    /**
     * Show NPC disposition change
     */
    showDispositionChange(data) {
        const change = data.change || 0;
        const npcName = data.npcName || 'NPC';

        if (change === 0) return;

        const notification = {
            type: 'disposition',
            icon: change > 0 ? '💚' : '💔',
            title: null,
            text: `${escapeHtml(npcName)}'s disposition has ${change > 0 ? 'improved' : 'worsened'}.`,
            subtext: `${change > 0 ? '+' : ''}${change}`,
            subtextClass: change > 0 ? 'positive' : 'negative',
            duration: data.duration || 3000,
        };

        this.addToHistory(notification);
        this.queueNotification(notification);
    }

    // =========================================================================
    // NOTIFICATION QUEUE
    // =========================================================================

    queueNotification(notification) {
        this.queue.push(notification);
        if (!this.isShowing) {
            this.showNext();
        }
    }

    async showNext() {
        if (this.queue.length === 0) {
            this.isShowing = false;
            return;
        }

        this.isShowing = true;
        const notification = this.queue.shift();

        // Build notification HTML
        this.container.innerHTML = `
            <div class="consequence-toast ${notification.type}">
                <div class="consequence-icon">${notification.icon}</div>
                ${notification.title ? `<div class="consequence-title">${escapeHtml(notification.title)}</div>` : ''}
                <div class="consequence-text">${escapeHtml(notification.text)}</div>
                ${notification.subtext ? `
                    <div class="consequence-subtext ${notification.subtextClass || ''}">${notification.subtext}</div>
                ` : ''}
            </div>
        `;

        // Show with animation
        this.container.classList.remove('hidden');
        await this.wait(50);
        this.container.classList.add('visible');

        // Wait for duration
        await this.wait(notification.duration);

        // Hide with animation
        this.container.classList.remove('visible');
        await this.wait(400);
        this.container.classList.add('hidden');

        // Show next in queue
        this.showNext();
    }

    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // =========================================================================
    // HISTORY
    // =========================================================================

    addToHistory(notification) {
        this.history.push({
            ...notification,
            timestamp: Date.now(),
        });

        // Keep only last 50 items
        if (this.history.length > 50) {
            this.history.shift();
        }
    }

    showHistory() {
        const content = this.historyPanel.querySelector('.history-content');

        if (this.history.length === 0) {
            content.innerHTML = '<p class="history-empty">No consequences yet.</p>';
        } else {
            content.innerHTML = this.history
                .slice()
                .reverse()
                .map(item => `
                    <div class="history-item ${item.type}">
                        <span class="history-icon">${item.icon}</span>
                        <span class="history-text">${escapeHtml(item.text)}</span>
                    </div>
                `)
                .join('');
        }

        this.historyPanel.classList.remove('hidden');
    }

    hideHistory() {
        this.historyPanel.classList.add('hidden');
    }

    toggleHistory() {
        if (this.historyPanel.classList.contains('hidden')) {
            this.showHistory();
        } else {
            this.hideHistory();
        }
    }

    // =========================================================================
    // CONVENIENCE METHODS
    // =========================================================================

    /**
     * Show a simple "remembered" message
     */
    remembered(text = 'Your choice will be remembered.', npc = null) {
        eventBus.emit(EVENTS.CHOICE_REMEMBERED, { text, npc });
    }

    /**
     * Show a triggered consequence
     */
    trigger(title, text, subtext = null) {
        eventBus.emit(EVENTS.CONSEQUENCE_TRIGGERED, { title, text, subtext });
    }

    /**
     * Show NPC disposition change
     */
    disposition(npcName, change) {
        eventBus.emit(EVENTS.NPC_DISPOSITION_CHANGED, { npcName, change });
    }
}

// Add styles dynamically
const styles = `
.consequence-display {
    position: fixed;
    bottom: 100px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1001;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.4s ease;
}

.consequence-display.visible {
    opacity: 1;
}

.consequence-display.hidden {
    display: none;
}

.consequence-toast {
    background: rgba(26, 26, 46, 0.95);
    border: 1px solid #f4a460;
    border-radius: 8px;
    padding: 16px 24px;
    max-width: 400px;
    text-align: center;
    backdrop-filter: blur(8px);
    animation: consequenceSlideUp 0.4s ease-out;
}

.consequence-toast.remembered {
    border-color: #9b59b6;
}

.consequence-toast.disposition {
    border-color: #3498db;
}

.consequence-icon {
    font-size: 1.5rem;
    margin-bottom: 8px;
}

.consequence-title {
    color: #f4a460;
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
}

.consequence-text {
    color: #e8d5b7;
    font-size: 0.95rem;
    line-height: 1.4;
}

.consequence-subtext {
    color: #888;
    font-size: 0.8rem;
    margin-top: 8px;
    font-style: italic;
}

.consequence-subtext.positive {
    color: #81c784;
    font-weight: 600;
    font-style: normal;
}

.consequence-subtext.negative {
    color: #e57373;
    font-weight: 600;
    font-style: normal;
}

@keyframes consequenceSlideUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* History Panel */
.consequence-history {
    position: fixed;
    right: 20px;
    top: 80px;
    width: 300px;
    max-height: 400px;
    background: rgba(26, 26, 46, 0.95);
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    z-index: 999;
    display: flex;
    flex-direction: column;
    backdrop-filter: blur(8px);
}

.consequence-history.hidden {
    display: none;
}

.history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #3a3a5c;
}

.history-title {
    color: #e8d5b7;
    font-weight: 600;
}

.history-close {
    background: none;
    border: none;
    color: #888;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0;
    line-height: 1;
}

.history-close:hover {
    color: #e74c3c;
}

.history-content {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
}

.history-empty {
    color: #666;
    text-align: center;
    font-style: italic;
}

.history-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 8px;
    background: rgba(0, 0, 0, 0.2);
}

.history-item:last-child {
    margin-bottom: 0;
}

.history-icon {
    font-size: 1rem;
    flex-shrink: 0;
}

.history-text {
    color: #c8c8c8;
    font-size: 0.85rem;
    line-height: 1.4;
}
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const consequenceDisplay = new ConsequenceDisplay();
export default consequenceDisplay;
