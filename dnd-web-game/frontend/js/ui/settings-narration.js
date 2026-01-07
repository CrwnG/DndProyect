/**
 * D&D Combat Engine - Narration Settings UI
 * Text-to-speech controls and voice selection.
 */

import { eventBus } from '../engine/event-bus.js';
import { narrationManager } from '../audio/narration.js';

/**
 * Narration Settings Panel
 */
class NarrationSettings {
    constructor() {
        this.container = null;
        this.isVisible = false;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();

        // Wait for voices to load then update
        setTimeout(() => this.updateUI(), 500);
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'narration-settings';
        this.container.className = 'narration-settings hidden';
        this.container.innerHTML = `
            <div class="nsettings-backdrop"></div>
            <div class="nsettings-panel">
                <header class="nsettings-header">
                    <h2>Narration Settings</h2>
                    <button class="nsettings-close">&times;</button>
                </header>

                <div class="nsettings-content">
                    ${!narrationManager.isSupported() ?
                        `<div class="unsupported-warning">
                            Text-to-speech is not supported in your browser.
                        </div>` : ''
                    }

                    <!-- Enable/Auto toggles -->
                    <div class="toggle-group">
                        <div class="toggle-item">
                            <label for="narration-enabled">Enable Narration</label>
                            <input type="checkbox" id="narration-enabled" class="toggle-switch">
                        </div>
                        <div class="toggle-item">
                            <label for="narration-auto">Auto-Narrate Stories</label>
                            <input type="checkbox" id="narration-auto" class="toggle-switch">
                        </div>
                    </div>

                    <div class="nsettings-divider"></div>

                    <!-- Voice Selection -->
                    <div class="setting-group">
                        <label for="voice-select">Voice</label>
                        <select id="voice-select" class="voice-select"></select>
                    </div>

                    <!-- Rate -->
                    <div class="setting-group">
                        <div class="setting-header">
                            <label>Speech Rate</label>
                            <span class="setting-value" id="rate-value">1.0x</span>
                        </div>
                        <input type="range" id="narration-rate" min="50" max="200" value="95">
                    </div>

                    <!-- Pitch -->
                    <div class="setting-group">
                        <div class="setting-header">
                            <label>Voice Pitch</label>
                            <span class="setting-value" id="pitch-value">1.0</span>
                        </div>
                        <input type="range" id="narration-pitch" min="50" max="200" value="100">
                    </div>

                    <!-- Volume -->
                    <div class="setting-group">
                        <div class="setting-header">
                            <label>Volume</label>
                            <span class="setting-value" id="volume-value">80%</span>
                        </div>
                        <input type="range" id="narration-volume" min="0" max="100" value="80">
                    </div>

                    <div class="nsettings-divider"></div>

                    <!-- Test -->
                    <div class="test-section">
                        <textarea id="test-text" class="test-textarea" placeholder="Enter text to test narration...">The ancient dragon awakens from its slumber, its golden eyes fixing upon the intruders who dare enter its lair.</textarea>
                        <div class="test-buttons">
                            <button class="btn-test" id="btn-test-speak">Test Voice</button>
                            <button class="btn-test btn-stop" id="btn-test-stop">Stop</button>
                        </div>
                    </div>

                    <!-- Speaking indicator -->
                    <div class="speaking-indicator hidden" id="speaking-indicator">
                        <span class="speaking-dot"></span>
                        <span class="speaking-text">Speaking...</span>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Close button
        this.container.querySelector('.nsettings-close').addEventListener('click', () => {
            this.hide();
        });

        // Backdrop click
        this.container.querySelector('.nsettings-backdrop').addEventListener('click', () => {
            this.hide();
        });

        // Enable toggle
        this.container.querySelector('#narration-enabled').addEventListener('change', (e) => {
            narrationManager.setEnabled(e.target.checked);
            this.updateDisabledState();
        });

        // Auto-narrate toggle
        this.container.querySelector('#narration-auto').addEventListener('change', (e) => {
            narrationManager.setAutoNarrate(e.target.checked);
        });

        // Voice selection
        this.container.querySelector('#voice-select').addEventListener('change', (e) => {
            narrationManager.setVoice(e.target.value);
        });

        // Rate slider
        this.container.querySelector('#narration-rate').addEventListener('input', (e) => {
            const rate = parseInt(e.target.value) / 100;
            narrationManager.setRate(rate);
            this.updateRateDisplay(rate);
        });

        // Pitch slider
        this.container.querySelector('#narration-pitch').addEventListener('input', (e) => {
            const pitch = parseInt(e.target.value) / 100;
            narrationManager.setPitch(pitch);
            this.updatePitchDisplay(pitch);
        });

        // Volume slider
        this.container.querySelector('#narration-volume').addEventListener('input', (e) => {
            const volume = parseInt(e.target.value) / 100;
            narrationManager.setVolume(volume);
            this.updateVolumeDisplay(volume);
        });

        // Test button
        this.container.querySelector('#btn-test-speak').addEventListener('click', () => {
            this.testVoice();
        });

        // Stop button
        this.container.querySelector('#btn-test-stop').addEventListener('click', () => {
            narrationManager.stop();
        });

        // Listen for narration events
        eventBus.on('narration:started', () => this.showSpeakingIndicator(true));
        eventBus.on('narration:ended', () => this.showSpeakingIndicator(false));
        eventBus.on('narration:stopped', () => this.showSpeakingIndicator(false));

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });
    }

    // ==================== UI Updates ====================

    updateUI() {
        // Enable/auto toggles
        this.container.querySelector('#narration-enabled').checked = narrationManager.isEnabled();
        this.container.querySelector('#narration-auto').checked = narrationManager.isAutoNarrate();

        // Populate voices
        this.populateVoices();

        // Rate
        const rate = narrationManager.rate;
        this.container.querySelector('#narration-rate').value = rate * 100;
        this.updateRateDisplay(rate);

        // Pitch
        const pitch = narrationManager.pitch;
        this.container.querySelector('#narration-pitch').value = pitch * 100;
        this.updatePitchDisplay(pitch);

        // Volume
        const volume = narrationManager.volume;
        this.container.querySelector('#narration-volume').value = volume * 100;
        this.updateVolumeDisplay(volume);

        // Update disabled state
        this.updateDisabledState();
    }

    populateVoices() {
        const select = this.container.querySelector('#voice-select');
        const voices = narrationManager.getVoices();
        const currentVoice = narrationManager.getVoice();

        select.innerHTML = '';

        // Group by language
        const grouped = {};
        voices.forEach(voice => {
            const lang = voice.lang.split('-')[0];
            if (!grouped[lang]) grouped[lang] = [];
            grouped[lang].push(voice);
        });

        // Add options
        Object.entries(grouped).forEach(([lang, langVoices]) => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = this.getLanguageName(lang);

            langVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.name;
                option.textContent = `${voice.name}${voice.localService ? ' (Local)' : ''}`;
                option.selected = currentVoice?.name === voice.name;
                optgroup.appendChild(option);
            });

            select.appendChild(optgroup);
        });
    }

    getLanguageName(code) {
        const languages = {
            en: 'English',
            es: 'Spanish',
            fr: 'French',
            de: 'German',
            it: 'Italian',
            pt: 'Portuguese',
            ru: 'Russian',
            zh: 'Chinese',
            ja: 'Japanese',
            ko: 'Korean'
        };
        return languages[code] || code.toUpperCase();
    }

    updateRateDisplay(rate) {
        this.container.querySelector('#rate-value').textContent = `${rate.toFixed(2)}x`;
    }

    updatePitchDisplay(pitch) {
        this.container.querySelector('#pitch-value').textContent = pitch.toFixed(2);
    }

    updateVolumeDisplay(volume) {
        this.container.querySelector('#volume-value').textContent = `${Math.round(volume * 100)}%`;
    }

    updateDisabledState() {
        const enabled = narrationManager.isEnabled();
        const controls = this.container.querySelectorAll('#voice-select, #narration-rate, #narration-pitch, #narration-volume, #narration-auto, .btn-test');

        controls.forEach(control => {
            control.disabled = !enabled;
        });
    }

    showSpeakingIndicator(show) {
        const indicator = this.container.querySelector('#speaking-indicator');
        indicator.classList.toggle('hidden', !show);
    }

    // ==================== Test ====================

    testVoice() {
        const text = this.container.querySelector('#test-text').value;
        if (text) {
            narrationManager.speak(text);
        }
    }

    // ==================== Show/Hide ====================

    show() {
        this.updateUI();
        this.container.classList.remove('hidden');
        this.isVisible = true;
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
        narrationManager.stop();
    }

    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }
}

// CSS Styles
const styles = `
.narration-settings {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 10002;
    display: flex;
    align-items: center;
    justify-content: center;
}

.narration-settings.hidden {
    display: none;
}

.nsettings-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.75);
}

.nsettings-panel {
    position: relative;
    width: 90%;
    max-width: 450px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid #d4af37;
    border-radius: 12px;
    overflow: hidden;
    max-height: 90vh;
    overflow-y: auto;
    animation: nsettingsSlideIn 0.3s ease-out;
}

@keyframes nsettingsSlideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.nsettings-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #3a3a5c;
    background: rgba(0, 0, 0, 0.2);
}

.nsettings-header h2 {
    margin: 0;
    color: #d4af37;
    font-family: 'Cinzel', serif;
    font-size: 1.2rem;
}

.nsettings-close {
    width: 32px;
    height: 32px;
    background: transparent;
    border: none;
    color: #888;
    font-size: 24px;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s;
}

.nsettings-close:hover {
    color: #e8e8e8;
    background: rgba(255, 255, 255, 0.1);
}

.nsettings-content {
    padding: 20px;
}

.unsupported-warning {
    padding: 12px;
    background: rgba(231, 76, 60, 0.2);
    border: 1px solid #e74c3c;
    border-radius: 6px;
    color: #e74c3c;
    text-align: center;
    margin-bottom: 16px;
}

.toggle-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.toggle-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.toggle-item label {
    color: #c8c8c8;
}

.toggle-switch {
    width: 50px;
    height: 26px;
    -webkit-appearance: none;
    background: #3a3a5c;
    border-radius: 13px;
    position: relative;
    cursor: pointer;
    transition: background 0.3s;
}

.toggle-switch:checked {
    background: #d4af37;
}

.toggle-switch::after {
    content: '';
    position: absolute;
    width: 22px;
    height: 22px;
    background: white;
    border-radius: 50%;
    top: 2px;
    left: 2px;
    transition: transform 0.3s;
}

.toggle-switch:checked::after {
    transform: translateX(24px);
}

.nsettings-divider {
    height: 1px;
    background: #3a3a5c;
    margin: 20px 0;
}

.setting-group {
    margin-bottom: 20px;
}

.setting-group label {
    display: block;
    color: #c8c8c8;
    margin-bottom: 8px;
}

.setting-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
}

.setting-value {
    color: #d4af37;
    font-weight: 600;
}

.voice-select {
    width: 100%;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #e8e8e8;
    font-size: 0.95rem;
}

.voice-select:focus {
    outline: none;
    border-color: #d4af37;
}

.voice-select optgroup {
    background: #1a1a2e;
    color: #d4af37;
}

.voice-select option {
    background: #1a1a2e;
    color: #e8e8e8;
}

.nsettings-content input[type="range"] {
    width: 100%;
    height: 6px;
    -webkit-appearance: none;
    background: #3a3a5c;
    border-radius: 3px;
    cursor: pointer;
}

.nsettings-content input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    background: #d4af37;
    border-radius: 50%;
    cursor: pointer;
}

.nsettings-content input[type="range"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.test-section {
    margin-top: 16px;
}

.test-textarea {
    width: 100%;
    min-height: 80px;
    padding: 10px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #e8e8e8;
    font-size: 0.9rem;
    resize: vertical;
    margin-bottom: 12px;
}

.test-textarea:focus {
    outline: none;
    border-color: #d4af37;
}

.test-buttons {
    display: flex;
    gap: 12px;
}

.btn-test {
    flex: 1;
    padding: 10px;
    background: rgba(212, 175, 55, 0.2);
    border: 1px solid #d4af37;
    border-radius: 6px;
    color: #d4af37;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-test:hover:not(:disabled) {
    background: #d4af37;
    color: #1a1a2e;
}

.btn-test:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-stop {
    background: rgba(231, 76, 60, 0.2);
    border-color: #e74c3c;
    color: #e74c3c;
}

.btn-stop:hover:not(:disabled) {
    background: #e74c3c;
    color: white;
}

.speaking-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px;
    background: rgba(46, 204, 113, 0.2);
    border-radius: 6px;
    margin-top: 12px;
}

.speaking-indicator.hidden {
    display: none;
}

.speaking-dot {
    width: 10px;
    height: 10px;
    background: #2ecc71;
    border-radius: 50%;
    animation: speakingPulse 1s infinite;
}

@keyframes speakingPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

.speaking-text {
    color: #2ecc71;
}
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const narrationSettings = new NarrationSettings();
export default narrationSettings;
