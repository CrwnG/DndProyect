/**
 * D&D Combat Engine - Audio Manager
 * Centralized audio system for sound effects, music, and ambient sounds.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

/**
 * Audio categories with independent volume controls
 */
export const AudioCategory = {
    SFX: 'sfx',
    MUSIC: 'music',
    AMBIENT: 'ambient',
    VOICE: 'voice'
};

/**
 * Audio Manager - Singleton for all game audio
 */
class AudioManager {
    constructor() {
        // Volume settings (0-1)
        this.masterVolume = 0.7;
        this.categoryVolumes = {
            [AudioCategory.SFX]: 1.0,
            [AudioCategory.MUSIC]: 0.5,
            [AudioCategory.AMBIENT]: 0.4,
            [AudioCategory.VOICE]: 0.8
        };

        // Mute states
        this.masterMuted = false;
        this.categoryMuted = {
            [AudioCategory.SFX]: false,
            [AudioCategory.MUSIC]: false,
            [AudioCategory.AMBIENT]: false,
            [AudioCategory.VOICE]: false
        };

        // Audio pools for managing concurrent sounds
        this.sfxPool = [];
        this.maxSfxPoolSize = 10;

        // Currently playing tracks
        this.currentMusic = null;
        this.currentAmbient = null;

        // Audio context for Web Audio API (better control)
        this.audioContext = null;
        this.gainNodes = {};

        // Preloaded audio buffers
        this.audioCache = new Map();
        this.loadingPromises = new Map();

        // Settings persistence key
        this.storageKey = 'dnd_audio_settings';

        // Initialize
        this.init();
    }

    /**
     * Initialize the audio system
     */
    init() {
        // Load saved settings
        this.loadSettings();

        // Create audio context on first user interaction (browser policy)
        const initAudioContext = () => {
            if (!this.audioContext) {
                try {
                    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    this.setupGainNodes();
                    console.log('[AudioManager] Audio context initialized');
                } catch (e) {
                    console.warn('[AudioManager] Web Audio API not available:', e);
                }
            }
            // Remove listeners after first interaction
            document.removeEventListener('click', initAudioContext);
            document.removeEventListener('keydown', initAudioContext);
        };

        document.addEventListener('click', initAudioContext, { once: true });
        document.addEventListener('keydown', initAudioContext, { once: true });

        // Initialize SFX pool
        this.initSfxPool();
    }

    /**
     * Setup Web Audio API gain nodes for volume control
     */
    setupGainNodes() {
        if (!this.audioContext) return;

        // Master gain
        this.masterGain = this.audioContext.createGain();
        this.masterGain.connect(this.audioContext.destination);
        this.masterGain.gain.value = this.masterMuted ? 0 : this.masterVolume;

        // Category gains
        Object.values(AudioCategory).forEach(category => {
            const gain = this.audioContext.createGain();
            gain.connect(this.masterGain);
            gain.gain.value = this.categoryMuted[category] ? 0 : this.categoryVolumes[category];
            this.gainNodes[category] = gain;
        });
    }

    /**
     * Initialize the SFX pool for concurrent sound playback
     */
    initSfxPool() {
        for (let i = 0; i < this.maxSfxPoolSize; i++) {
            const audio = new Audio();
            audio.preload = 'auto';
            this.sfxPool.push({
                element: audio,
                inUse: false
            });
        }
    }

    /**
     * Get an available audio element from the SFX pool
     */
    getPooledAudio() {
        // Find an available slot
        let slot = this.sfxPool.find(s => !s.inUse);

        if (!slot) {
            // All slots in use, find the oldest one and reuse it
            slot = this.sfxPool[0];
            slot.element.pause();
            slot.element.currentTime = 0;
        }

        slot.inUse = true;
        return slot;
    }

    /**
     * Release a pooled audio element
     */
    releasePooledAudio(slot) {
        slot.inUse = false;
        slot.element.src = '';
    }

    // ==================== Playback Methods ====================

    /**
     * Play a sound effect
     * @param {string} soundId - Sound identifier from sound library
     * @param {Object} options - Playback options
     */
    playSFX(soundId, options = {}) {
        const {
            volume = 1.0,
            pitch = 1.0,
            loop = false,
            delay = 0
        } = options;

        // Import sound library dynamically to avoid circular deps
        import('./sound-library.js').then(({ SOUNDS }) => {
            const soundPath = SOUNDS[soundId];
            if (!soundPath) {
                console.warn(`[AudioManager] Sound not found: ${soundId}`);
                return;
            }

            const play = () => {
                const slot = this.getPooledAudio();
                const audio = slot.element;

                audio.src = soundPath;
                audio.volume = this.calculateVolume(AudioCategory.SFX, volume);
                audio.playbackRate = pitch;
                audio.loop = loop;

                audio.onended = () => {
                    if (!loop) {
                        this.releasePooledAudio(slot);
                    }
                };

                audio.play().catch(e => {
                    console.warn(`[AudioManager] Failed to play SFX: ${soundId}`, e);
                    this.releasePooledAudio(slot);
                });
            };

            if (delay > 0) {
                setTimeout(play, delay);
            } else {
                play();
            }
        });
    }

    /**
     * Play background music
     * @param {string} trackId - Track identifier from sound library
     * @param {Object} options - Playback options
     */
    playMusic(trackId, options = {}) {
        const {
            volume = 1.0,
            fadeIn = 1000,
            loop = true
        } = options;

        import('./sound-library.js').then(({ SOUNDS }) => {
            const trackPath = SOUNDS[trackId];
            if (!trackPath) {
                console.warn(`[AudioManager] Music track not found: ${trackId}`);
                return;
            }

            // Fade out current music if playing
            if (this.currentMusic) {
                this.fadeOut(this.currentMusic, 500).then(() => {
                    this.currentMusic.pause();
                    this.currentMusic = null;
                    this.startMusic(trackPath, volume, fadeIn, loop);
                });
            } else {
                this.startMusic(trackPath, volume, fadeIn, loop);
            }
        });
    }

    /**
     * Start playing a music track
     */
    startMusic(path, volume, fadeIn, loop) {
        this.currentMusic = new Audio(path);
        this.currentMusic.loop = loop;
        this.currentMusic.volume = 0;

        this.currentMusic.play().then(() => {
            this.fadeIn(this.currentMusic, fadeIn, this.calculateVolume(AudioCategory.MUSIC, volume));
        }).catch(e => {
            console.warn('[AudioManager] Failed to play music:', e);
        });
    }

    /**
     * Stop the current music
     * @param {number} fadeOut - Fade out duration in ms
     */
    stopMusic(fadeOut = 1000) {
        if (!this.currentMusic) return;

        this.fadeOut(this.currentMusic, fadeOut).then(() => {
            this.currentMusic.pause();
            this.currentMusic = null;
        });
    }

    /**
     * Play ambient sound
     * @param {string} sceneId - Ambient scene identifier
     * @param {Object} options - Playback options
     */
    playAmbient(sceneId, options = {}) {
        const {
            volume = 1.0,
            fadeIn = 2000
        } = options;

        import('./sound-library.js').then(({ SOUNDS }) => {
            const ambientPath = SOUNDS[sceneId];
            if (!ambientPath) {
                console.warn(`[AudioManager] Ambient not found: ${sceneId}`);
                return;
            }

            // Fade out current ambient if playing
            if (this.currentAmbient) {
                this.fadeOut(this.currentAmbient, 1000).then(() => {
                    this.currentAmbient.pause();
                    this.currentAmbient = null;
                    this.startAmbient(ambientPath, volume, fadeIn);
                });
            } else {
                this.startAmbient(ambientPath, volume, fadeIn);
            }
        });
    }

    /**
     * Start playing ambient sound
     */
    startAmbient(path, volume, fadeIn) {
        this.currentAmbient = new Audio(path);
        this.currentAmbient.loop = true;
        this.currentAmbient.volume = 0;

        this.currentAmbient.play().then(() => {
            this.fadeIn(this.currentAmbient, fadeIn, this.calculateVolume(AudioCategory.AMBIENT, volume));
        }).catch(e => {
            console.warn('[AudioManager] Failed to play ambient:', e);
        });
    }

    /**
     * Stop ambient sound
     * @param {number} fadeOut - Fade out duration in ms
     */
    stopAmbient(fadeOut = 2000) {
        if (!this.currentAmbient) return;

        this.fadeOut(this.currentAmbient, fadeOut).then(() => {
            this.currentAmbient.pause();
            this.currentAmbient = null;
        });
    }

    /**
     * Stop all audio
     */
    stopAll() {
        // Stop SFX pool
        this.sfxPool.forEach(slot => {
            if (slot.inUse) {
                slot.element.pause();
                this.releasePooledAudio(slot);
            }
        });

        // Stop music
        this.stopMusic(500);

        // Stop ambient
        this.stopAmbient(500);
    }

    // ==================== Volume Control ====================

    /**
     * Set master volume
     * @param {number} volume - Volume level (0-1)
     */
    setMasterVolume(volume) {
        this.masterVolume = Math.max(0, Math.min(1, volume));

        if (this.masterGain && !this.masterMuted) {
            this.masterGain.gain.setValueAtTime(this.masterVolume, this.audioContext.currentTime);
        }

        // Update HTML audio elements
        this.updateAudioVolumes();
        this.saveSettings();
    }

    /**
     * Set volume for a category
     * @param {string} category - Audio category
     * @param {number} volume - Volume level (0-1)
     */
    setCategoryVolume(category, volume) {
        this.categoryVolumes[category] = Math.max(0, Math.min(1, volume));

        if (this.gainNodes[category] && !this.categoryMuted[category]) {
            this.gainNodes[category].gain.setValueAtTime(
                this.categoryVolumes[category],
                this.audioContext.currentTime
            );
        }

        this.updateAudioVolumes();
        this.saveSettings();
    }

    /**
     * Mute/unmute master audio
     * @param {boolean} muted - Mute state
     */
    setMasterMute(muted) {
        this.masterMuted = muted;

        if (this.masterGain) {
            this.masterGain.gain.setValueAtTime(
                muted ? 0 : this.masterVolume,
                this.audioContext.currentTime
            );
        }

        this.updateAudioVolumes();
        this.saveSettings();
    }

    /**
     * Mute/unmute a category
     * @param {string} category - Audio category
     * @param {boolean} muted - Mute state
     */
    setCategoryMute(category, muted) {
        this.categoryMuted[category] = muted;

        if (this.gainNodes[category]) {
            this.gainNodes[category].gain.setValueAtTime(
                muted ? 0 : this.categoryVolumes[category],
                this.audioContext.currentTime
            );
        }

        this.updateAudioVolumes();
        this.saveSettings();
    }

    /**
     * Toggle mute for a category
     */
    toggleMute(category) {
        this.setCategoryMute(category, !this.categoryMuted[category]);
    }

    /**
     * Calculate effective volume for an audio element
     */
    calculateVolume(category, soundVolume = 1.0) {
        if (this.masterMuted || this.categoryMuted[category]) {
            return 0;
        }
        return this.masterVolume * this.categoryVolumes[category] * soundVolume;
    }

    /**
     * Update volumes on all playing audio elements
     */
    updateAudioVolumes() {
        // Update current music
        if (this.currentMusic) {
            this.currentMusic.volume = this.calculateVolume(AudioCategory.MUSIC);
        }

        // Update current ambient
        if (this.currentAmbient) {
            this.currentAmbient.volume = this.calculateVolume(AudioCategory.AMBIENT);
        }
    }

    // ==================== Fade Effects ====================

    /**
     * Fade in an audio element
     */
    fadeIn(audio, duration, targetVolume) {
        return new Promise(resolve => {
            const startVolume = 0;
            const steps = 20;
            const stepTime = duration / steps;
            const volumeStep = (targetVolume - startVolume) / steps;
            let currentStep = 0;

            const fade = setInterval(() => {
                currentStep++;
                audio.volume = Math.min(targetVolume, startVolume + volumeStep * currentStep);

                if (currentStep >= steps) {
                    clearInterval(fade);
                    resolve();
                }
            }, stepTime);
        });
    }

    /**
     * Fade out an audio element
     */
    fadeOut(audio, duration) {
        return new Promise(resolve => {
            const startVolume = audio.volume;
            const steps = 20;
            const stepTime = duration / steps;
            const volumeStep = startVolume / steps;
            let currentStep = 0;

            const fade = setInterval(() => {
                currentStep++;
                audio.volume = Math.max(0, startVolume - volumeStep * currentStep);

                if (currentStep >= steps) {
                    clearInterval(fade);
                    resolve();
                }
            }, stepTime);
        });
    }

    /**
     * Crossfade between two tracks
     */
    crossfade(fromAudio, toAudio, duration) {
        return Promise.all([
            this.fadeOut(fromAudio, duration),
            this.fadeIn(toAudio, duration, this.calculateVolume(AudioCategory.MUSIC))
        ]);
    }

    // ==================== Preloading ====================

    /**
     * Preload a set of sounds
     * @param {string[]} soundIds - Array of sound IDs to preload
     */
    async preload(soundIds) {
        const promises = soundIds.map(id => this.preloadSound(id));
        return Promise.all(promises);
    }

    /**
     * Preload a single sound
     */
    async preloadSound(soundId) {
        if (this.audioCache.has(soundId)) {
            return this.audioCache.get(soundId);
        }

        if (this.loadingPromises.has(soundId)) {
            return this.loadingPromises.get(soundId);
        }

        const loadPromise = import('./sound-library.js').then(({ SOUNDS }) => {
            const path = SOUNDS[soundId];
            if (!path) return null;

            return new Promise((resolve, reject) => {
                const audio = new Audio();
                audio.preload = 'auto';

                audio.oncanplaythrough = () => {
                    this.audioCache.set(soundId, audio);
                    this.loadingPromises.delete(soundId);
                    resolve(audio);
                };

                audio.onerror = () => {
                    this.loadingPromises.delete(soundId);
                    reject(new Error(`Failed to load: ${soundId}`));
                };

                audio.src = path;
            });
        });

        this.loadingPromises.set(soundId, loadPromise);
        return loadPromise;
    }

    /**
     * Preload sounds for a category
     */
    async preloadCategory(category) {
        const { SOUNDS } = await import('./sound-library.js');

        const soundIds = Object.keys(SOUNDS).filter(id => {
            const path = SOUNDS[id];
            return path.includes(`/${category}/`);
        });

        return this.preload(soundIds);
    }

    // ==================== Settings Persistence ====================

    /**
     * Save audio settings to localStorage
     */
    saveSettings() {
        const settings = {
            masterVolume: this.masterVolume,
            masterMuted: this.masterMuted,
            categoryVolumes: this.categoryVolumes,
            categoryMuted: this.categoryMuted
        };

        try {
            localStorage.setItem(this.storageKey, JSON.stringify(settings));
        } catch (e) {
            console.warn('[AudioManager] Failed to save settings:', e);
        }
    }

    /**
     * Load audio settings from localStorage
     */
    loadSettings() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            if (saved) {
                const settings = JSON.parse(saved);
                this.masterVolume = settings.masterVolume ?? this.masterVolume;
                this.masterMuted = settings.masterMuted ?? this.masterMuted;
                this.categoryVolumes = { ...this.categoryVolumes, ...settings.categoryVolumes };
                this.categoryMuted = { ...this.categoryMuted, ...settings.categoryMuted };
            }
        } catch (e) {
            console.warn('[AudioManager] Failed to load settings:', e);
        }
    }

    // ==================== Getters ====================

    getMasterVolume() {
        return this.masterVolume;
    }

    getCategoryVolume(category) {
        return this.categoryVolumes[category] ?? 1.0;
    }

    isMasterMuted() {
        return this.masterMuted;
    }

    isCategoryMuted(category) {
        return this.categoryMuted[category] ?? false;
    }

    isPlaying(type) {
        switch (type) {
            case 'music':
                return this.currentMusic && !this.currentMusic.paused;
            case 'ambient':
                return this.currentAmbient && !this.currentAmbient.paused;
            default:
                return false;
        }
    }
}

// Export singleton
export const audioManager = new AudioManager();
export default audioManager;
