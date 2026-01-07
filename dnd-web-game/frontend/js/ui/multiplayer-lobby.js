/**
 * D&D Combat Engine - Multiplayer Lobby
 * Create and join multiplayer sessions
 *
 * Features:
 * - Create new multiplayer sessions
 * - Join existing sessions via code
 * - Player list with ready status
 * - Session settings configuration
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import api from '../api/api-client.js';
import { toast } from './toast-notification.js';
import { multiplayerVote } from './multiplayer-vote.js';

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
 * Multiplayer Lobby UI
 */
class MultiplayerLobby {
    constructor() {
        this.container = null;
        this.isVisible = false;
        this.currentSession = null;
        this.players = [];
        this.isHost = false;
        this.playerId = null;
        this.playerName = '';

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
        this.loadPlayerInfo();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'multiplayer-lobby';
        this.container.className = 'multiplayer-lobby hidden';
        this.container.innerHTML = `
            <div class="lobby-backdrop"></div>
            <div class="lobby-modal">
                <div class="lobby-header">
                    <h2>Multiplayer</h2>
                    <button class="close-btn" id="lobby-close">&times;</button>
                </div>

                <!-- Main Menu View -->
                <div class="lobby-view" data-view="main">
                    <div class="lobby-options">
                        <button class="lobby-btn" id="btn-create-session">
                            <span class="btn-icon">🎲</span>
                            <span class="btn-text">Host Game</span>
                            <span class="btn-desc">Create a new multiplayer session</span>
                        </button>
                        <button class="lobby-btn" id="btn-join-session">
                            <span class="btn-icon">🔗</span>
                            <span class="btn-text">Join Game</span>
                            <span class="btn-desc">Join an existing session</span>
                        </button>
                    </div>

                    <div class="player-setup">
                        <label for="player-name">Your Name</label>
                        <input type="text" id="player-name" placeholder="Enter your name..." maxlength="20">
                    </div>
                </div>

                <!-- Create Session View -->
                <div class="lobby-view hidden" data-view="create">
                    <h3>Create Session</h3>

                    <div class="form-group">
                        <label>Decision Mode</label>
                        <select id="decision-mode">
                            <option value="voting">Voting - Majority wins</option>
                            <option value="leader_decides">Leader Decides - Host chooses</option>
                            <option value="rotating">Rotating - Take turns choosing</option>
                            <option value="consensus">Consensus - All must agree</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Vote Timeout (seconds)</label>
                        <input type="number" id="vote-timeout" value="60" min="15" max="300">
                    </div>

                    <div class="lobby-actions">
                        <button class="btn secondary" id="btn-back-create">Back</button>
                        <button class="btn primary" id="btn-confirm-create">Create</button>
                    </div>
                </div>

                <!-- Join Session View -->
                <div class="lobby-view hidden" data-view="join">
                    <h3>Join Session</h3>

                    <div class="form-group">
                        <label>Session Code</label>
                        <input type="text" id="session-code" placeholder="Enter session code..." maxlength="8">
                    </div>

                    <div class="lobby-actions">
                        <button class="btn secondary" id="btn-back-join">Back</button>
                        <button class="btn primary" id="btn-confirm-join">Join</button>
                    </div>
                </div>

                <!-- Waiting Room View -->
                <div class="lobby-view hidden" data-view="waiting">
                    <h3>Session Lobby</h3>

                    <div class="session-info">
                        <div class="session-code">
                            <label>Session Code</label>
                            <div class="code-display">
                                <span id="display-session-code">XXXX</span>
                                <button class="copy-btn" id="btn-copy-code" title="Copy code">📋</button>
                            </div>
                        </div>
                    </div>

                    <div class="players-list">
                        <h4>Players (<span id="player-count">0</span>/4)</h4>
                        <ul id="players-list"></ul>
                    </div>

                    <div class="lobby-actions">
                        <button class="btn secondary" id="btn-leave-session">Leave</button>
                        <button class="btn primary" id="btn-start-game" disabled>Start Game</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Close button
        this.container.querySelector('#lobby-close').addEventListener('click', () => this.hide());
        this.container.querySelector('.lobby-backdrop').addEventListener('click', () => this.hide());

        // Main menu buttons
        this.container.querySelector('#btn-create-session').addEventListener('click', () => {
            this.showView('create');
        });
        this.container.querySelector('#btn-join-session').addEventListener('click', () => {
            this.showView('join');
        });

        // Player name
        this.container.querySelector('#player-name').addEventListener('change', (e) => {
            this.playerName = e.target.value.trim();
            localStorage.setItem('dnd_player_name', this.playerName);
        });

        // Create session
        this.container.querySelector('#btn-back-create').addEventListener('click', () => {
            this.showView('main');
        });
        this.container.querySelector('#btn-confirm-create').addEventListener('click', () => {
            this.createSession();
        });

        // Join session
        this.container.querySelector('#btn-back-join').addEventListener('click', () => {
            this.showView('main');
        });
        this.container.querySelector('#btn-confirm-join').addEventListener('click', () => {
            this.joinSession();
        });

        // Waiting room
        this.container.querySelector('#btn-copy-code').addEventListener('click', () => {
            this.copySessionCode();
        });
        this.container.querySelector('#btn-leave-session').addEventListener('click', () => {
            this.leaveSession();
        });
        this.container.querySelector('#btn-start-game').addEventListener('click', () => {
            this.startGame();
        });

        // Listen for player events
        eventBus.on('multiplayer:player_joined', (data) => this.updatePlayers(data.players));
        eventBus.on('multiplayer:player_left', (data) => this.updatePlayers(data.players));
        eventBus.on('multiplayer:connected', () => this.onConnected());
        eventBus.on('multiplayer:disconnected', () => this.onDisconnected());

        // ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });

        // Listen for open event
        eventBus.on(EVENTS.OPEN_MULTIPLAYER_LOBBY, () => this.show());
    }

    loadPlayerInfo() {
        this.playerName = localStorage.getItem('dnd_player_name') || '';
        this.playerId = localStorage.getItem('dnd_player_id');

        if (!this.playerId) {
            this.playerId = 'player-' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('dnd_player_id', this.playerId);
        }
    }

    // =========================================================================
    // VIEW MANAGEMENT
    // =========================================================================

    showView(viewName) {
        this.container.querySelectorAll('.lobby-view').forEach(view => {
            view.classList.toggle('hidden', view.dataset.view !== viewName);
        });
    }

    show() {
        this.container.classList.remove('hidden');
        this.isVisible = true;
        this.showView('main');

        // Load saved player name
        const nameInput = this.container.querySelector('#player-name');
        nameInput.value = this.playerName;
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
    }

    // =========================================================================
    // SESSION MANAGEMENT
    // =========================================================================

    async createSession() {
        if (!this.playerName) {
            toast.error('Please enter your name first');
            this.showView('main');
            return;
        }

        const mode = this.container.querySelector('#decision-mode').value;
        const timeout = parseInt(this.container.querySelector('#vote-timeout').value) || 60;

        try {
            // Generate session code (for now, random)
            const sessionCode = this.generateSessionCode();

            this.currentSession = {
                id: sessionCode,
                code: sessionCode,
                mode: mode,
                timeout: timeout,
                host: this.playerId,
            };

            this.isHost = true;

            // Connect to WebSocket
            multiplayerVote.connect(sessionCode, this.playerId);

            // Show waiting room
            this.container.querySelector('#display-session-code').textContent = sessionCode;
            this.showView('waiting');

            toast.success('Session created! Share the code with friends.');

        } catch (error) {
            console.error('[MultiplayerLobby] Create session failed:', error);
            toast.error('Failed to create session');
        }
    }

    async joinSession() {
        if (!this.playerName) {
            toast.error('Please enter your name first');
            this.showView('main');
            return;
        }

        const code = this.container.querySelector('#session-code').value.trim().toUpperCase();
        if (!code || code.length < 4) {
            toast.error('Please enter a valid session code');
            return;
        }

        try {
            this.currentSession = {
                id: code,
                code: code,
            };

            this.isHost = false;

            // Connect to WebSocket
            multiplayerVote.connect(code, this.playerId);

            // Show waiting room
            this.container.querySelector('#display-session-code').textContent = code;
            this.showView('waiting');

        } catch (error) {
            console.error('[MultiplayerLobby] Join session failed:', error);
            toast.error('Failed to join session');
        }
    }

    leaveSession() {
        multiplayerVote.disconnect();
        this.currentSession = null;
        this.players = [];
        this.isHost = false;
        this.showView('main');
    }

    async startGame() {
        if (!this.isHost) {
            toast.error('Only the host can start the game');
            return;
        }

        if (this.players.length < 2) {
            toast.error('Need at least 2 players to start');
            return;
        }

        // TODO: Integrate with campaign start
        // For now, just hide the lobby
        this.hide();

        eventBus.emit(EVENTS.MULTIPLAYER_GAME_START, {
            sessionId: this.currentSession.id,
            players: this.players,
            settings: {
                mode: this.currentSession.mode,
                timeout: this.currentSession.timeout,
            },
        });

        toast.success('Game started!');
    }

    // =========================================================================
    // PLAYER MANAGEMENT
    // =========================================================================

    updatePlayers(playerIds) {
        this.players = playerIds || [];

        const listEl = this.container.querySelector('#players-list');
        const countEl = this.container.querySelector('#player-count');

        countEl.textContent = this.players.length;

        listEl.innerHTML = this.players.map(pid => {
            const isMe = pid === this.playerId;
            const isHost = this.currentSession && pid === this.currentSession.host;

            return `
                <li class="player-item ${isMe ? 'me' : ''}">
                    <span class="player-icon">${isHost ? '👑' : '🎮'}</span>
                    <span class="player-name">${isMe ? `${escapeHtml(this.playerName)} (You)` : escapeHtml(pid)}</span>
                </li>
            `;
        }).join('');

        // Enable start button if host and enough players
        const startBtn = this.container.querySelector('#btn-start-game');
        startBtn.disabled = !this.isHost || this.players.length < 2;
    }

    onConnected() {
        this.updatePlayers([this.playerId]);
    }

    onDisconnected() {
        if (this.isVisible) {
            toast.error('Disconnected from session');
            this.leaveSession();
        }
    }

    // =========================================================================
    // UTILITIES
    // =========================================================================

    generateSessionCode() {
        const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        let code = '';
        for (let i = 0; i < 6; i++) {
            code += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return code;
    }

    copySessionCode() {
        const code = this.currentSession?.code || '';
        if (code) {
            navigator.clipboard.writeText(code).then(() => {
                toast.success('Code copied to clipboard!');
            }).catch(() => {
                toast.error('Failed to copy code');
            });
        }
    }
}

// Register event
if (!EVENTS.OPEN_MULTIPLAYER_LOBBY) {
    EVENTS.OPEN_MULTIPLAYER_LOBBY = 'open_multiplayer_lobby';
}
if (!EVENTS.MULTIPLAYER_GAME_START) {
    EVENTS.MULTIPLAYER_GAME_START = 'multiplayer_game_start';
}

// Add styles dynamically
const styles = `
.multiplayer-lobby {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.multiplayer-lobby.hidden {
    display: none;
}

.lobby-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(4px);
}

.lobby-modal {
    position: relative;
    width: 90%;
    max-width: 450px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #3a3a5c;
    border-radius: 12px;
    padding: 24px;
    animation: fadeIn 0.3s ease-out;
}

.lobby-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
}

.lobby-header h2 {
    margin: 0;
    color: #e8d5b7;
}

.lobby-header .close-btn {
    background: none;
    border: none;
    color: #888;
    font-size: 1.8rem;
    cursor: pointer;
    padding: 0 8px;
    line-height: 1;
}

.lobby-header .close-btn:hover {
    color: #e74c3c;
}

.lobby-view.hidden {
    display: none;
}

.lobby-view h3 {
    margin: 0 0 20px;
    color: #e8d5b7;
    text-align: center;
}

/* Main Menu */
.lobby-options {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 24px;
}

.lobby-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
}

.lobby-btn:hover {
    background: rgba(0, 0, 0, 0.4);
    border-color: #4a90d9;
}

.lobby-btn .btn-icon {
    font-size: 2rem;
    margin-bottom: 8px;
}

.lobby-btn .btn-text {
    color: #e8d5b7;
    font-size: 1.1rem;
    font-weight: 600;
}

.lobby-btn .btn-desc {
    color: #888;
    font-size: 0.8rem;
    margin-top: 4px;
}

.player-setup {
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid #3a3a5c;
}

.player-setup label {
    display: block;
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 8px;
}

.player-setup input {
    width: 100%;
    padding: 12px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #e8e8e8;
    font-size: 1rem;
}

/* Form Groups */
.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 8px;
}

.form-group input,
.form-group select {
    width: 100%;
    padding: 12px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #e8e8e8;
    font-size: 0.95rem;
}

/* Waiting Room */
.session-info {
    margin-bottom: 24px;
}

.session-code {
    text-align: center;
}

.session-code label {
    display: block;
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 8px;
}

.code-display {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
}

.code-display span {
    font-family: monospace;
    font-size: 2rem;
    font-weight: bold;
    color: #4a90d9;
    letter-spacing: 0.1em;
    background: rgba(0, 0, 0, 0.3);
    padding: 12px 24px;
    border-radius: 8px;
    border: 1px solid #4a90d9;
}

.copy-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    opacity: 0.7;
    transition: opacity 0.2s;
}

.copy-btn:hover {
    opacity: 1;
}

.players-list {
    margin-bottom: 24px;
}

.players-list h4 {
    margin: 0 0 12px;
    color: #888;
    font-size: 0.9rem;
}

.players-list ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.player-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 6px;
    margin-bottom: 8px;
}

.player-item.me {
    background: rgba(74, 144, 217, 0.15);
    border: 1px solid rgba(74, 144, 217, 0.3);
}

.player-icon {
    font-size: 1.2rem;
}

.player-name {
    color: #c8c8c8;
}

/* Actions */
.lobby-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
}

.lobby-actions .btn {
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 0.95rem;
    cursor: pointer;
    transition: all 0.2s;
}

.lobby-actions .btn.primary {
    background: linear-gradient(135deg, #4a90d9 0%, #357abd 100%);
    border: none;
    color: #fff;
}

.lobby-actions .btn.primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #5a9fe8 0%, #4589cc 100%);
}

.lobby-actions .btn.primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.lobby-actions .btn.secondary {
    background: transparent;
    border: 1px solid #3a3a5c;
    color: #888;
}

.lobby-actions .btn.secondary:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: #555;
    color: #c8c8c8;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const multiplayerLobby = new MultiplayerLobby();
export default multiplayerLobby;
