/**
 * D&D Combat Engine - Narration Manager
 * Text-to-speech for DM narration using Web Speech API.
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';

/**
 * Narration Manager - Handles text-to-speech for story narration
 */
class NarrationManager {
    constructor() {
        // Speech synthesis
        this.synth = window.speechSynthesis;
        this.voices = [];
        this.currentVoice = null;

        // Settings
        this.rate = 0.95;     // Speech rate (0.5-2)
        this.pitch = 1.0;     // Voice pitch (0.5-2)
        this.volume = 0.8;    // Volume (0-1)
        this.enabled = true;
        this.autoNarrate = false;

        // State
        this.isPlaying = false;
        this.isPaused = false;
        this.currentUtterance = null;
        this.queue = [];

        // Preferred voice settings
        this.preferredVoiceName = null;
        this.preferredLang = 'en';

        // Storage key
        this.storageKey = 'dnd_narration_settings';

        this.init();
    }

    /**
     * Initialize the narration system
     */
    init() {
        // Check for browser support
        if (!this.synth) {
            console.warn('[NarrationManager] Speech synthesis not supported');
            this.enabled = false;
            return;
        }

        // Load voices (they may load asynchronously)
        this.loadVoices();

        // Voice changed event (some browsers load voices async)
        if (speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = () => this.loadVoices();
        }

        // Load saved settings
        this.loadSettings();

        console.log('[NarrationManager] Initialized');
    }

    /**
     * Load available voices
     */
    loadVoices() {
        this.voices = this.synth.getVoices();

        // Try to find a good default voice
        if (this.voices.length > 0 && !this.currentVoice) {
            // Prefer voices that sound good for narration
            const preferredVoices = [
                // English male voices (often better for "DM" feel)
                'Google UK English Male',
                'Microsoft David',
                'Daniel',
                'Alex',
                // English female voices
                'Google UK English Female',
                'Microsoft Zira',
                'Samantha',
                // Generic English
                'en-GB',
                'en-US'
            ];

            // Find first matching voice
            for (const preferred of preferredVoices) {
                const found = this.voices.find(v =>
                    v.name.includes(preferred) || v.lang.startsWith(preferred)
                );
                if (found) {
                    this.currentVoice = found;
                    break;
                }
            }

            // Fallback to first English voice
            if (!this.currentVoice) {
                this.currentVoice = this.voices.find(v => v.lang.startsWith('en')) || this.voices[0];
            }

            // Restore saved voice if it exists
            if (this.preferredVoiceName) {
                const savedVoice = this.voices.find(v => v.name === this.preferredVoiceName);
                if (savedVoice) {
                    this.currentVoice = savedVoice;
                }
            }
        }

        console.log(`[NarrationManager] Loaded ${this.voices.length} voices`);
    }

    // ==================== Playback Control ====================

    /**
     * Speak text
     * @param {string} text - Text to speak
     * @param {Object} options - Speech options
     * @returns {Promise} Resolves when speech completes
     */
    speak(text, options = {}) {
        return new Promise((resolve, reject) => {
            if (!this.enabled || !this.synth) {
                resolve();
                return;
            }

            // Clean text for speech
            const cleanedText = this.cleanTextForSpeech(text);
            if (!cleanedText) {
                resolve();
                return;
            }

            // Create utterance
            const utterance = new SpeechSynthesisUtterance(cleanedText);

            // Apply settings
            utterance.voice = options.voice || this.currentVoice;
            utterance.rate = options.rate ?? this.rate;
            utterance.pitch = options.pitch ?? this.pitch;
            utterance.volume = options.volume ?? this.volume;
            utterance.lang = this.currentVoice?.lang || 'en-US';

            // Event handlers
            utterance.onstart = () => {
                this.isPlaying = true;
                this.isPaused = false;
                this.currentUtterance = utterance;
                eventBus.emit('narration:started', { text: cleanedText });
            };

            utterance.onend = () => {
                this.isPlaying = false;
                this.currentUtterance = null;
                eventBus.emit('narration:ended', { text: cleanedText });
                this.processQueue();
                resolve();
            };

            utterance.onerror = (event) => {
                console.error('[NarrationManager] Speech error:', event.error);
                this.isPlaying = false;
                this.currentUtterance = null;
                eventBus.emit('narration:error', { error: event.error });
                reject(event.error);
            };

            utterance.onpause = () => {
                this.isPaused = true;
                eventBus.emit('narration:paused');
            };

            utterance.onresume = () => {
                this.isPaused = false;
                eventBus.emit('narration:resumed');
            };

            // Queue or speak immediately
            if (options.queue && this.isPlaying) {
                this.queue.push({ utterance, resolve, reject });
            } else {
                // Cancel any ongoing speech
                this.synth.cancel();
                this.synth.speak(utterance);
            }
        });
    }

    /**
     * Process the speech queue
     */
    processQueue() {
        if (this.queue.length > 0 && !this.isPlaying) {
            const { utterance, resolve, reject } = this.queue.shift();

            utterance.onend = () => {
                this.isPlaying = false;
                this.currentUtterance = null;
                eventBus.emit('narration:ended');
                this.processQueue();
                resolve();
            };

            this.synth.speak(utterance);
        }
    }

    /**
     * Pause current speech
     */
    pause() {
        if (this.synth && this.isPlaying) {
            this.synth.pause();
        }
    }

    /**
     * Resume paused speech
     */
    resume() {
        if (this.synth && this.isPaused) {
            this.synth.resume();
        }
    }

    /**
     * Stop speech and clear queue
     */
    stop() {
        if (this.synth) {
            this.synth.cancel();
            this.isPlaying = false;
            this.isPaused = false;
            this.currentUtterance = null;
            this.queue = [];
            eventBus.emit('narration:stopped');
        }
    }

    /**
     * Skip to next queued speech
     */
    skip() {
        if (this.synth && this.isPlaying) {
            this.synth.cancel();
            // Queue processing will happen via onend
        }
    }

    // ==================== Voice Management ====================

    /**
     * Get available voices
     * @param {string} lang - Filter by language (optional)
     */
    getVoices(lang = null) {
        if (lang) {
            return this.voices.filter(v => v.lang.startsWith(lang));
        }
        return this.voices;
    }

    /**
     * Set the current voice
     * @param {string} voiceName - Voice name
     */
    setVoice(voiceName) {
        const voice = this.voices.find(v => v.name === voiceName);
        if (voice) {
            this.currentVoice = voice;
            this.preferredVoiceName = voiceName;
            this.saveSettings();
        }
    }

    /**
     * Get current voice
     */
    getVoice() {
        return this.currentVoice;
    }

    // ==================== Settings ====================

    /**
     * Set speech rate
     * @param {number} rate - Rate (0.5-2)
     */
    setRate(rate) {
        this.rate = Math.max(0.5, Math.min(2, rate));
        this.saveSettings();
    }

    /**
     * Set voice pitch
     * @param {number} pitch - Pitch (0.5-2)
     */
    setPitch(pitch) {
        this.pitch = Math.max(0.5, Math.min(2, pitch));
        this.saveSettings();
    }

    /**
     * Set volume
     * @param {number} volume - Volume (0-1)
     */
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        this.saveSettings();
    }

    /**
     * Enable/disable narration
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        if (!enabled) {
            this.stop();
        }
        this.saveSettings();
    }

    /**
     * Enable/disable auto-narration
     */
    setAutoNarrate(enabled) {
        this.autoNarrate = enabled;
        this.saveSettings();
    }

    /**
     * Save settings to localStorage
     */
    saveSettings() {
        const settings = {
            rate: this.rate,
            pitch: this.pitch,
            volume: this.volume,
            enabled: this.enabled,
            autoNarrate: this.autoNarrate,
            preferredVoiceName: this.preferredVoiceName
        };

        try {
            localStorage.setItem(this.storageKey, JSON.stringify(settings));
        } catch (e) {
            console.warn('[NarrationManager] Failed to save settings:', e);
        }
    }

    /**
     * Load settings from localStorage
     */
    loadSettings() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            if (saved) {
                const settings = JSON.parse(saved);
                this.rate = settings.rate ?? this.rate;
                this.pitch = settings.pitch ?? this.pitch;
                this.volume = settings.volume ?? this.volume;
                this.enabled = settings.enabled ?? this.enabled;
                this.autoNarrate = settings.autoNarrate ?? this.autoNarrate;
                this.preferredVoiceName = settings.preferredVoiceName;
            }
        } catch (e) {
            console.warn('[NarrationManager] Failed to load settings:', e);
        }
    }

    // ==================== Text Processing ====================

    /**
     * Clean text for speech synthesis
     */
    cleanTextForSpeech(text) {
        if (!text) return '';

        return text
            // Remove HTML tags
            .replace(/<[^>]*>/g, '')
            // Replace common D&D abbreviations
            .replace(/\bHP\b/gi, 'hit points')
            .replace(/\bAC\b/gi, 'armor class')
            .replace(/\bDC\b/gi, 'difficulty class')
            .replace(/\bDM\b/gi, 'dungeon master')
            .replace(/\bNPC\b/gi, 'non-player character')
            .replace(/\bPC\b/gi, 'player character')
            .replace(/\bXP\b/gi, 'experience points')
            // Handle dice notation (speak as words)
            .replace(/(\d+)d(\d+)/gi, (_, num, die) => `${num} D ${die}`)
            .replace(/\+(\d+)/g, ' plus $1')
            .replace(/\-(\d+)/g, ' minus $1')
            // Handle feet notation
            .replace(/(\d+)\s*ft\.?/gi, '$1 feet')
            .replace(/(\d+)\s*'/g, '$1 feet')
            // Clean up multiple spaces
            .replace(/\s+/g, ' ')
            // Trim
            .trim();
    }

    /**
     * Split long text into chunks for better speech
     */
    splitIntoChunks(text, maxLength = 200) {
        const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
        const chunks = [];
        let currentChunk = '';

        for (const sentence of sentences) {
            if ((currentChunk + sentence).length > maxLength && currentChunk) {
                chunks.push(currentChunk.trim());
                currentChunk = sentence;
            } else {
                currentChunk += sentence;
            }
        }

        if (currentChunk) {
            chunks.push(currentChunk.trim());
        }

        return chunks;
    }

    // ==================== Story Narration ====================

    /**
     * Narrate story text with dramatic pauses
     * @param {string} text - Story text to narrate
     * @param {Object} options - Narration options
     */
    async narrateStory(text, options = {}) {
        if (!this.enabled || !text) return;

        const {
            dramaticPauses = true,
            chunkDelay = 500
        } = options;

        // Split into chunks
        const chunks = this.splitIntoChunks(text);

        // Speak each chunk
        for (let i = 0; i < chunks.length; i++) {
            let chunk = chunks[i];

            // Add slight pause after dramatic punctuation
            if (dramaticPauses) {
                chunk = chunk
                    .replace(/\.\.\./g, '... ')
                    .replace(/!/g, '! ')
                    .replace(/\?/g, '? ');
            }

            await this.speak(chunk);

            // Brief pause between chunks
            if (i < chunks.length - 1) {
                await this.delay(chunkDelay);
            }
        }
    }

    /**
     * Simple delay helper
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ==================== State Queries ====================

    /**
     * Check if currently speaking
     */
    isSpeaking() {
        return this.isPlaying;
    }

    /**
     * Check if paused
     */
    isPausedState() {
        return this.isPaused;
    }

    /**
     * Check if narration is enabled
     */
    isEnabled() {
        return this.enabled && !!this.synth;
    }

    /**
     * Check if auto-narrate is enabled
     */
    isAutoNarrate() {
        return this.autoNarrate;
    }

    /**
     * Check browser support
     */
    isSupported() {
        return !!window.speechSynthesis;
    }
}

// Export singleton
export const narrationManager = new NarrationManager();
export default narrationManager;
