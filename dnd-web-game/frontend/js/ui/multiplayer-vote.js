/**
 * D&D Combat Engine - Multiplayer Voting UI
 * Real-time voting interface for multiplayer choices
 *
 * Features:
 * - Show voting options with live vote counts
 * - Display who has voted
 * - Countdown timer for timeout
 * - Results animation
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { CONFIG } from '../config.js';

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
 * Multiplayer Vote UI
 */
class MultiplayerVote {
    constructor() {
        this.container = null;
        this.isVisible = false;
        this.currentSession = null;
        this.ws = null;
        this.playerId = null;
        this.sessionId = null;
        this.myVote = null;
        this.timerInterval = null;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'multiplayer-vote';
        this.container.className = 'multiplayer-vote hidden';
        this.container.innerHTML = `
            <div class="vote-backdrop"></div>
            <div class="vote-modal">
                <div class="vote-header">
                    <h3 class="vote-title">Party Decision</h3>
                    <div class="vote-timer">
                        <span class="timer-icon">⏱️</span>
                        <span class="timer-value">60</span>s
                    </div>
                </div>

                <div class="vote-question"></div>

                <div class="vote-options"></div>

                <div class="vote-status">
                    <div class="status-text">Waiting for votes...</div>
                    <div class="voters-list"></div>
                </div>

                <div class="vote-result hidden">
                    <div class="result-icon">✅</div>
                    <div class="result-text">Decision made!</div>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Listen for vote events from WebSocket
        eventBus.on('multiplayer:choice_started', (data) => this.showVote(data));
        eventBus.on('multiplayer:vote_update', (data) => this.updateVotes(data));
        eventBus.on('multiplayer:choice_resolved', (data) => this.showResult(data));
    }

    // =========================================================================
    // WEBSOCKET CONNECTION
    // =========================================================================

    connect(sessionId, playerId) {
        this.sessionId = sessionId;
        this.playerId = playerId;

        const wsUrl = `${CONFIG.WS_BASE_URL}/api/multiplayer/ws/${sessionId}/${playerId}`;
        console.log('[MultiplayerVote] Connecting to:', wsUrl);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('[MultiplayerVote] WebSocket connected');
            eventBus.emit('multiplayer:connected', { sessionId, playerId });
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onclose = () => {
            console.log('[MultiplayerVote] WebSocket disconnected');
            eventBus.emit('multiplayer:disconnected');
        };

        this.ws.onerror = (error) => {
            console.error('[MultiplayerVote] WebSocket error:', error);
        };
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    handleMessage(data) {
        switch (data.type) {
            case 'choice_started':
                eventBus.emit('multiplayer:choice_started', data);
                break;

            case 'vote_update':
                eventBus.emit('multiplayer:vote_update', data);
                break;

            case 'choice_resolved':
                eventBus.emit('multiplayer:choice_resolved', data);
                break;

            case 'player_joined':
                eventBus.emit('multiplayer:player_joined', data);
                break;

            case 'player_left':
                eventBus.emit('multiplayer:player_left', data);
                break;

            case 'pong':
                // Heartbeat response
                break;

            default:
                console.log('[MultiplayerVote] Unknown message type:', data.type);
        }
    }

    // =========================================================================
    // VOTE DISPLAY
    // =========================================================================

    showVote(data) {
        const session = data.session;
        this.currentSession = session;
        this.myVote = null;

        // Set question
        this.container.querySelector('.vote-question').textContent =
            session.choice_text || 'What should we do?';

        // Create option buttons
        const optionsContainer = this.container.querySelector('.vote-options');
        optionsContainer.innerHTML = session.options.map(opt => `
            <button class="vote-option" data-choice-id="${escapeHtml(opt.id)}">
                <span class="option-text">${escapeHtml(opt.text)}</span>
                <span class="option-votes">0</span>
            </button>
        `).join('');

        // Add click handlers
        optionsContainer.querySelectorAll('.vote-option').forEach(btn => {
            btn.addEventListener('click', () => this.castVote(btn.dataset.choiceId));
        });

        // Reset status
        this.container.querySelector('.vote-status').classList.remove('hidden');
        this.container.querySelector('.vote-result').classList.add('hidden');
        this.updateVotersList(session.required_players, session.votes || {});

        // Start timer
        this.startTimer(session.timeout_seconds);

        // Show modal
        this.container.classList.remove('hidden');
        this.isVisible = true;
    }

    castVote(choiceId) {
        if (!this.currentSession) return;

        // Update local UI immediately
        this.myVote = choiceId;
        this.highlightMyVote(choiceId);

        // Send vote via WebSocket
        this.send({
            type: 'vote',
            choice_session_id: this.currentSession.id,
            choice_id: choiceId,
        });
    }

    highlightMyVote(choiceId) {
        this.container.querySelectorAll('.vote-option').forEach(btn => {
            btn.classList.toggle('selected', btn.dataset.choiceId === choiceId);
        });
    }

    updateVotes(data) {
        if (!this.currentSession) return;

        const result = data.result;

        // Update vote counts on options
        this.container.querySelectorAll('.vote-option').forEach(btn => {
            const choiceId = btn.dataset.choiceId;
            const count = result.current_votes[choiceId] || 0;
            btn.querySelector('.option-votes').textContent = count;
        });

        // Update voters list
        this.container.querySelector('.status-text').textContent =
            `${result.total_votes}/${result.required_votes} votes cast`;

        // Show who hasn't voted
        if (result.missing_voters && result.missing_voters.length > 0) {
            this.container.querySelector('.voters-list').textContent =
                `Waiting for: ${result.missing_voters.join(', ')}`;
        } else {
            this.container.querySelector('.voters-list').textContent = 'All votes in!';
        }
    }

    updateVotersList(requiredPlayers, votes) {
        const voted = Object.keys(votes);
        const waiting = requiredPlayers.filter(p => !voted.includes(p));

        this.container.querySelector('.status-text').textContent =
            `${voted.length}/${requiredPlayers.length} votes cast`;

        if (waiting.length > 0) {
            this.container.querySelector('.voters-list').textContent =
                `Waiting for: ${waiting.join(', ')}`;
        }
    }

    showResult(data) {
        // Stop timer
        this.stopTimer();

        // Highlight winning option
        this.container.querySelectorAll('.vote-option').forEach(btn => {
            btn.classList.toggle('winner', btn.dataset.choiceId === data.winning_choice);
            btn.disabled = true;
        });

        // Show result message
        const resultEl = this.container.querySelector('.vote-result');
        resultEl.classList.remove('hidden');

        if (data.tie) {
            resultEl.querySelector('.result-text').textContent = 'Tie resolved by leader!';
        } else {
            resultEl.querySelector('.result-text').textContent = 'Decision made!';
        }

        // Hide status
        this.container.querySelector('.vote-status').classList.add('hidden');

        // Auto-hide after delay
        setTimeout(() => this.hide(), 3000);
    }

    // =========================================================================
    // TIMER
    // =========================================================================

    startTimer(seconds) {
        this.stopTimer();

        let remaining = seconds;
        const timerEl = this.container.querySelector('.timer-value');
        timerEl.textContent = remaining;

        this.timerInterval = setInterval(() => {
            remaining--;
            timerEl.textContent = remaining;

            if (remaining <= 10) {
                timerEl.classList.add('urgent');
            }

            if (remaining <= 0) {
                this.stopTimer();
            }
        }, 1000);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.container.querySelector('.timer-value').classList.remove('urgent');
    }

    // =========================================================================
    // VISIBILITY
    // =========================================================================

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
        this.currentSession = null;
        this.myVote = null;
        this.stopTimer();
    }
}

// Add styles dynamically
const styles = `
.multiplayer-vote {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1002;
    display: flex;
    align-items: center;
    justify-content: center;
}

.multiplayer-vote.hidden {
    display: none;
}

.vote-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
}

.vote-modal {
    position: relative;
    width: 90%;
    max-width: 500px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid #9b59b6;
    border-radius: 12px;
    padding: 24px;
    animation: voteSlideIn 0.3s ease-out;
}

@keyframes voteSlideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.vote-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.vote-title {
    margin: 0;
    color: #9b59b6;
    font-size: 1.3rem;
}

.vote-timer {
    display: flex;
    align-items: center;
    gap: 4px;
    color: #888;
    font-size: 0.9rem;
}

.timer-value {
    color: #e8d5b7;
    font-weight: bold;
}

.timer-value.urgent {
    color: #e74c3c;
    animation: pulse 0.5s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.vote-question {
    color: #e8d5b7;
    font-size: 1.1rem;
    text-align: center;
    margin-bottom: 24px;
    line-height: 1.5;
}

.vote-options {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 24px;
}

.vote-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 18px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    color: #c8c8c8;
    cursor: pointer;
    transition: all 0.2s;
}

.vote-option:hover:not(:disabled) {
    background: rgba(155, 89, 182, 0.15);
    border-color: #9b59b6;
}

.vote-option.selected {
    background: rgba(155, 89, 182, 0.25);
    border-color: #9b59b6;
    color: #e8e8e8;
}

.vote-option.winner {
    background: rgba(46, 204, 113, 0.2);
    border-color: #2ecc71;
    color: #2ecc71;
}

.vote-option:disabled {
    cursor: default;
    opacity: 0.7;
}

.option-text {
    flex: 1;
    text-align: left;
}

.option-votes {
    background: rgba(0, 0, 0, 0.3);
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.85rem;
    min-width: 24px;
    text-align: center;
}

.vote-status {
    text-align: center;
    color: #888;
    font-size: 0.9rem;
}

.vote-status.hidden {
    display: none;
}

.status-text {
    margin-bottom: 8px;
}

.voters-list {
    font-size: 0.8rem;
    color: #666;
}

.vote-result {
    text-align: center;
    padding: 16px;
    animation: fadeIn 0.3s ease-out;
}

.vote-result.hidden {
    display: none;
}

.result-icon {
    font-size: 2.5rem;
    margin-bottom: 8px;
}

.result-text {
    color: #2ecc71;
    font-size: 1.1rem;
    font-weight: 600;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const multiplayerVote = new MultiplayerVote();
export default multiplayerVote;
