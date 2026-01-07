/**
 * D&D Combat Engine - Audio Settings UI
 * Volume controls and audio preferences.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import { audioManager, AudioCategory } from '../audio/audio-manager.js';

/**
 * Audio Settings Panel
 */
class AudioSettings {
    constructor() {
        this.container = null;
        this.isVisible = false;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
        this.updateUI();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'audio-settings';
        this.container.className = 'audio-settings hidden';
        this.container.innerHTML = `
            <div class="settings-backdrop"></div>
            <div class="settings-panel">
                <header class="settings-header">
                    <h2>Audio Settings</h2>
                    <button class="settings-close">&times;</button>
                </header>

                <div class="settings-content">
                    <!-- Master Volume -->
                    <div class="volume-group master-volume">
                        <div class="volume-header">
                            <label>Master Volume</label>
                            <button class="mute-btn" data-category="master" title="Mute All">
                                <span class="mute-icon">🔊</span>
                            </button>
                        </div>
                        <div class="volume-control">
                            <input type="range" id="volume-master" min="0" max="100" value="70">
                            <span class="volume-value">70%</span>
                        </div>
                    </div>

                    <div class="settings-divider"></div>

                    <!-- Sound Effects -->
                    <div class="volume-group">
                        <div class="volume-header">
                            <label>Sound Effects</label>
                            <button class="mute-btn" data-category="sfx" title="Mute SFX">
                                <span class="mute-icon">🔊</span>
                            </button>
                        </div>
                        <div class="volume-control">
                            <input type="range" id="volume-sfx" min="0" max="100" value="100">
                            <span class="volume-value">100%</span>
                        </div>
                        <button class="test-btn" data-sound="attack_sword_hit">Test</button>
                    </div>

                    <!-- Music -->
                    <div class="volume-group">
                        <div class="volume-header">
                            <label>Music</label>
                            <button class="mute-btn" data-category="music" title="Mute Music">
                                <span class="mute-icon">🔊</span>
                            </button>
                        </div>
                        <div class="volume-control">
                            <input type="range" id="volume-music" min="0" max="100" value="50">
                            <span class="volume-value">50%</span>
                        </div>
                        <button class="test-btn" data-sound="music_combat_standard">Test</button>
                    </div>

                    <!-- Ambient -->
                    <div class="volume-group">
                        <div class="volume-header">
                            <label>Ambient</label>
                            <button class="mute-btn" data-category="ambient" title="Mute Ambient">
                                <span class="mute-icon">🔊</span>
                            </button>
                        </div>
                        <div class="volume-control">
                            <input type="range" id="volume-ambient" min="0" max="100" value="40">
                            <span class="volume-value">40%</span>
                        </div>
                        <button class="test-btn" data-sound="ambient_dungeon">Test</button>
                    </div>

                    <!-- Voice/Narration -->
                    <div class="volume-group">
                        <div class="volume-header">
                            <label>Voice/Narration</label>
                            <button class="mute-btn" data-category="voice" title="Mute Voice">
                                <span class="mute-icon">🔊</span>
                            </button>
                        </div>
                        <div class="volume-control">
                            <input type="range" id="volume-voice" min="0" max="100" value="80">
                            <span class="volume-value">80%</span>
                        </div>
                    </div>

                    <div class="settings-divider"></div>

                    <!-- Quick Actions -->
                    <div class="settings-actions">
                        <button class="action-btn btn-mute-all">Mute All</button>
                        <button class="action-btn btn-reset">Reset to Default</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Close button
        this.container.querySelector('.settings-close').addEventListener('click', () => {
            this.hide();
        });

        // Backdrop click
        this.container.querySelector('.settings-backdrop').addEventListener('click', () => {
            this.hide();
        });

        // Master volume
        const masterSlider = this.container.querySelector('#volume-master');
        masterSlider.addEventListener('input', (e) => {
            this.setMasterVolume(parseInt(e.target.value));
        });

        // Category volumes
        const categories = ['sfx', 'music', 'ambient', 'voice'];
        categories.forEach(category => {
            const slider = this.container.querySelector(`#volume-${category}`);
            if (slider) {
                slider.addEventListener('input', (e) => {
                    this.setCategoryVolume(category, parseInt(e.target.value));
                });
            }
        });

        // Mute buttons
        this.container.querySelectorAll('.mute-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const category = btn.dataset.category;
                this.toggleMute(category);
            });
        });

        // Test buttons
        this.container.querySelectorAll('.test-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const sound = btn.dataset.sound;
                this.testSound(sound);
            });
        });

        // Mute all button
        this.container.querySelector('.btn-mute-all').addEventListener('click', () => {
            this.toggleMuteAll();
        });

        // Reset button
        this.container.querySelector('.btn-reset').addEventListener('click', () => {
            this.resetToDefault();
        });

        // Keyboard shortcut to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });
    }

    // ==================== Volume Control ====================

    setMasterVolume(percent) {
        const volume = percent / 100;
        audioManager.setMasterVolume(volume);
        this.updateVolumeDisplay('master', percent);
    }

    setCategoryVolume(category, percent) {
        const volume = percent / 100;
        const categoryMap = {
            sfx: AudioCategory.SFX,
            music: AudioCategory.MUSIC,
            ambient: AudioCategory.AMBIENT,
            voice: AudioCategory.VOICE
        };

        audioManager.setCategoryVolume(categoryMap[category], volume);
        this.updateVolumeDisplay(category, percent);
    }

    toggleMute(category) {
        if (category === 'master') {
            const isMuted = audioManager.isMasterMuted();
            audioManager.setMasterMute(!isMuted);
        } else {
            const categoryMap = {
                sfx: AudioCategory.SFX,
                music: AudioCategory.MUSIC,
                ambient: AudioCategory.AMBIENT,
                voice: AudioCategory.VOICE
            };
            audioManager.toggleMute(categoryMap[category]);
        }

        this.updateMuteButtons();
    }

    toggleMuteAll() {
        const isMuted = audioManager.isMasterMuted();
        audioManager.setMasterMute(!isMuted);
        this.updateMuteButtons();

        const btn = this.container.querySelector('.btn-mute-all');
        btn.textContent = isMuted ? 'Mute All' : 'Unmute All';
    }

    resetToDefault() {
        // Reset master
        audioManager.setMasterVolume(0.7);
        audioManager.setMasterMute(false);

        // Reset categories
        audioManager.setCategoryVolume(AudioCategory.SFX, 1.0);
        audioManager.setCategoryVolume(AudioCategory.MUSIC, 0.5);
        audioManager.setCategoryVolume(AudioCategory.AMBIENT, 0.4);
        audioManager.setCategoryVolume(AudioCategory.VOICE, 0.8);

        // Unmute all
        audioManager.setCategoryMute(AudioCategory.SFX, false);
        audioManager.setCategoryMute(AudioCategory.MUSIC, false);
        audioManager.setCategoryMute(AudioCategory.AMBIENT, false);
        audioManager.setCategoryMute(AudioCategory.VOICE, false);

        // Update UI
        this.updateUI();
    }

    // ==================== Test Sounds ====================

    testSound(soundId) {
        // Stop any currently playing test
        audioManager.stopMusic(0);
        audioManager.stopAmbient(0);

        // Play based on sound type
        if (soundId.startsWith('music_')) {
            audioManager.playMusic(soundId, { fadeIn: 0, loop: false });
            // Stop after 5 seconds
            setTimeout(() => audioManager.stopMusic(1000), 5000);
        } else if (soundId.startsWith('ambient_')) {
            audioManager.playAmbient(soundId, { fadeIn: 0 });
            // Stop after 3 seconds
            setTimeout(() => audioManager.stopAmbient(500), 3000);
        } else {
            audioManager.playSFX(soundId);
        }
    }

    // ==================== UI Updates ====================

    updateUI() {
        // Update master volume
        const masterPercent = Math.round(audioManager.getMasterVolume() * 100);
        this.container.querySelector('#volume-master').value = masterPercent;
        this.updateVolumeDisplay('master', masterPercent);

        // Update category volumes
        const categories = [
            { key: 'sfx', category: AudioCategory.SFX },
            { key: 'music', category: AudioCategory.MUSIC },
            { key: 'ambient', category: AudioCategory.AMBIENT },
            { key: 'voice', category: AudioCategory.VOICE }
        ];

        categories.forEach(({ key, category }) => {
            const percent = Math.round(audioManager.getCategoryVolume(category) * 100);
            const slider = this.container.querySelector(`#volume-${key}`);
            if (slider) {
                slider.value = percent;
                this.updateVolumeDisplay(key, percent);
            }
        });

        // Update mute buttons
        this.updateMuteButtons();
    }

    updateVolumeDisplay(category, percent) {
        const group = this.container.querySelector(
            category === 'master' ? '.master-volume' : `#volume-${category}`
        )?.closest('.volume-group');

        if (group) {
            const valueDisplay = group.querySelector('.volume-value');
            if (valueDisplay) {
                valueDisplay.textContent = `${percent}%`;
            }
        }
    }

    updateMuteButtons() {
        // Master mute
        const masterBtn = this.container.querySelector('.mute-btn[data-category="master"]');
        if (masterBtn) {
            const isMuted = audioManager.isMasterMuted();
            masterBtn.querySelector('.mute-icon').textContent = isMuted ? '🔇' : '🔊';
            masterBtn.classList.toggle('muted', isMuted);
        }

        // Category mutes
        const categories = ['sfx', 'music', 'ambient', 'voice'];
        const categoryMap = {
            sfx: AudioCategory.SFX,
            music: AudioCategory.MUSIC,
            ambient: AudioCategory.AMBIENT,
            voice: AudioCategory.VOICE
        };

        categories.forEach(key => {
            const btn = this.container.querySelector(`.mute-btn[data-category="${key}"]`);
            if (btn) {
                const isMuted = audioManager.isCategoryMuted(categoryMap[key]);
                btn.querySelector('.mute-icon').textContent = isMuted ? '🔇' : '🔊';
                btn.classList.toggle('muted', isMuted);
            }
        });

        // Update mute all button
        const muteAllBtn = this.container.querySelector('.btn-mute-all');
        muteAllBtn.textContent = audioManager.isMasterMuted() ? 'Unmute All' : 'Mute All';
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
.audio-settings {
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

.audio-settings.hidden {
    display: none;
}

.settings-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.75);
}

.settings-panel {
    position: relative;
    width: 90%;
    max-width: 400px;
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    border: 2px solid #d4af37;
    border-radius: 12px;
    overflow: hidden;
    animation: settingsSlideIn 0.3s ease-out;
}

@keyframes settingsSlideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.settings-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #3a3a5c;
    background: rgba(0, 0, 0, 0.2);
}

.settings-header h2 {
    margin: 0;
    color: #d4af37;
    font-family: 'Cinzel', serif;
    font-size: 1.2rem;
}

.settings-close {
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

.settings-close:hover {
    color: #e8e8e8;
    background: rgba(255, 255, 255, 0.1);
}

.settings-content {
    padding: 20px;
}

.volume-group {
    margin-bottom: 20px;
}

.volume-group.master-volume {
    padding-bottom: 16px;
}

.volume-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.volume-header label {
    color: #c8c8c8;
    font-size: 0.95rem;
}

.mute-btn {
    width: 32px;
    height: 32px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.mute-btn:hover {
    background: rgba(212, 175, 55, 0.2);
    border-color: #d4af37;
}

.mute-btn.muted {
    background: rgba(231, 76, 60, 0.2);
    border-color: #e74c3c;
}

.mute-icon {
    font-size: 1rem;
}

.volume-control {
    display: flex;
    align-items: center;
    gap: 12px;
}

.volume-control input[type="range"] {
    flex: 1;
    height: 6px;
    -webkit-appearance: none;
    background: #3a3a5c;
    border-radius: 3px;
    cursor: pointer;
}

.volume-control input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    background: #d4af37;
    border-radius: 50%;
    cursor: pointer;
    transition: transform 0.2s;
}

.volume-control input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.1);
}

.volume-value {
    min-width: 45px;
    text-align: right;
    color: #888;
    font-size: 0.9rem;
}

.test-btn {
    margin-top: 8px;
    padding: 6px 12px;
    background: transparent;
    border: 1px solid #666;
    border-radius: 4px;
    color: #888;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s;
}

.test-btn:hover {
    border-color: #d4af37;
    color: #d4af37;
}

.settings-divider {
    height: 1px;
    background: #3a3a5c;
    margin: 16px 0;
}

.settings-actions {
    display: flex;
    gap: 12px;
    margin-top: 8px;
}

.action-btn {
    flex: 1;
    padding: 10px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid #3a3a5c;
    border-radius: 6px;
    color: #888;
    cursor: pointer;
    transition: all 0.2s;
}

.action-btn:hover {
    border-color: #d4af37;
    color: #d4af37;
}
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Export singleton
export const audioSettings = new AudioSettings();
export default audioSettings;
