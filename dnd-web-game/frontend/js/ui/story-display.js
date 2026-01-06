/**
 * D&D Combat Engine - Story Display
 * Full-screen story overlay with typewriter effect
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import state from '../engine/state-manager.js';

class StoryDisplay {
    constructor() {
        this.container = null;
        this.textElement = null;
        this.currentText = '';
        this.typewriterInterval = null;
        this.typewriterSpeed = 30; // ms per character
        this.isVisible = false;
        this.onContinue = null;

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'story-display';
        this.container.className = 'story-display hidden';
        this.container.innerHTML = `
            <div class="story-backdrop"></div>
            <div class="story-content">
                <div class="story-header">
                    <h2 id="story-title" class="story-title"></h2>
                </div>
                <div class="story-body">
                    <div id="story-text" class="story-text"></div>
                </div>
                <div class="story-footer">
                    <button id="btn-story-continue" class="story-btn">Continue</button>
                    <span class="story-hint">Press SPACE or ENTER to continue</span>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
        this.textElement = document.getElementById('story-text');
    }

    setupEventListeners() {
        // Continue button
        document.getElementById('btn-story-continue')?.addEventListener('click', () => {
            this.handleContinue();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;

            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();

                // If still typing, skip to end
                if (this.typewriterInterval) {
                    this.skipTypewriter();
                } else {
                    this.handleContinue();
                }
            }

            if (e.key === 'Escape') {
                // Skip typewriter effect
                if (this.typewriterInterval) {
                    this.skipTypewriter();
                }
            }
        });

        // Click to skip typewriter
        this.container.querySelector('.story-body')?.addEventListener('click', () => {
            if (this.typewriterInterval) {
                this.skipTypewriter();
            }
        });
    }

    /**
     * Show story text with typewriter effect
     * @param {Object} options - Display options
     * @param {string} options.title - Story title/encounter name
     * @param {string} options.text - Story text to display
     * @param {string} options.buttonText - Custom button text (default: "Continue")
     * @param {Function} options.onContinue - Callback when user continues
     */
    show(options) {
        const { title, text, buttonText = 'Continue', onContinue } = options;

        this.currentText = text || '';
        this.onContinue = onContinue;

        // Set title
        const titleEl = document.getElementById('story-title');
        if (titleEl) {
            titleEl.textContent = title || '';
            titleEl.style.display = title ? 'block' : 'none';
        }

        // Set button text
        const btnEl = document.getElementById('btn-story-continue');
        if (btnEl) {
            btnEl.textContent = buttonText;
        }

        // Clear previous text
        this.textElement.innerHTML = '';

        // Show container
        this.container.classList.remove('hidden');
        this.isVisible = true;

        // Start typewriter effect
        this.startTypewriter();

        eventBus.emit(EVENTS.STORY_DISPLAYED, { title, text });
    }

    hide() {
        this.stopTypewriter();
        this.container.classList.add('hidden');
        this.isVisible = false;
        this.onContinue = null;
    }

    /**
     * Start the typewriter effect
     */
    startTypewriter() {
        this.stopTypewriter();

        let index = 0;
        const paragraphs = this.currentText.split('\n\n');
        let currentParagraphIndex = 0;
        let currentParagraphCharIndex = 0;

        // Create paragraph elements
        this.textElement.innerHTML = '';
        for (let i = 0; i < paragraphs.length; i++) {
            const p = document.createElement('p');
            p.className = 'story-paragraph';
            this.textElement.appendChild(p);
        }

        const paragraphElements = this.textElement.querySelectorAll('.story-paragraph');

        this.typewriterInterval = setInterval(() => {
            if (currentParagraphIndex >= paragraphs.length) {
                this.stopTypewriter();
                return;
            }

            const currentParagraph = paragraphs[currentParagraphIndex];
            const currentElement = paragraphElements[currentParagraphIndex];

            if (currentParagraphCharIndex < currentParagraph.length) {
                const char = currentParagraph[currentParagraphCharIndex];
                currentElement.textContent += char;
                currentParagraphCharIndex++;
            } else {
                // Move to next paragraph
                currentParagraphIndex++;
                currentParagraphCharIndex = 0;
            }
        }, this.typewriterSpeed);
    }

    /**
     * Stop the typewriter effect
     */
    stopTypewriter() {
        if (this.typewriterInterval) {
            clearInterval(this.typewriterInterval);
            this.typewriterInterval = null;
        }
    }

    /**
     * Skip to end of typewriter effect
     */
    skipTypewriter() {
        this.stopTypewriter();

        // Display all text immediately
        const paragraphs = this.currentText.split('\n\n');
        const paragraphElements = this.textElement.querySelectorAll('.story-paragraph');

        paragraphs.forEach((text, i) => {
            if (paragraphElements[i]) {
                paragraphElements[i].textContent = text;
            }
        });
    }

    /**
     * Handle continue button click
     */
    handleContinue() {
        if (this.onContinue) {
            this.onContinue();
        }

        eventBus.emit(EVENTS.STORY_CONTINUED);
    }

    /**
     * Check if story display is currently showing
     */
    isShowing() {
        return this.isVisible;
    }
}

// Add CSS for story display
const storyCSS = `
/* =============================================================================
   Story Display Styles - Enhanced Fantasy Theme
   ============================================================================= */

@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Cinzel+Decorative:wght@700&display=swap');

.story-display {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    animation: storyFadeIn 0.5s ease forwards;
}

@keyframes storyFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.story-display.hidden {
    display: none;
}

.story-backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(180deg, rgba(15, 10, 25, 0.97) 0%, rgba(20, 25, 40, 0.98) 100%);
    overflow: hidden;
}

/* Floating particles effect */
.story-backdrop::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image:
        radial-gradient(2px 2px at 20px 30px, rgba(212, 175, 55, 0.3), transparent),
        radial-gradient(2px 2px at 40px 70px, rgba(212, 175, 55, 0.2), transparent),
        radial-gradient(2px 2px at 50px 160px, rgba(212, 175, 55, 0.3), transparent),
        radial-gradient(2px 2px at 90px 40px, rgba(212, 175, 55, 0.2), transparent),
        radial-gradient(2px 2px at 130px 80px, rgba(212, 175, 55, 0.25), transparent),
        radial-gradient(2px 2px at 160px 120px, rgba(212, 175, 55, 0.15), transparent);
    background-repeat: repeat;
    background-size: 200px 200px;
    animation: particleFloat 20s linear infinite;
    opacity: 0.6;
}

@keyframes particleFloat {
    0% { transform: translateY(0); }
    100% { transform: translateY(-200px); }
}

/* Subtle vignette effect */
.story-backdrop::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(ellipse at center, transparent 40%, rgba(0, 0, 0, 0.5) 100%);
    pointer-events: none;
}

.story-content {
    position: relative;
    width: 90%;
    max-width: 850px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    padding: 0;
    background: linear-gradient(180deg, rgba(20, 15, 35, 0.95) 0%, rgba(15, 20, 35, 0.97) 100%);
    border: 2px solid var(--accent-gold);
    border-radius: 8px;
    box-shadow:
        0 0 40px rgba(212, 175, 55, 0.25),
        0 0 80px rgba(212, 175, 55, 0.1),
        inset 0 0 60px rgba(0, 0, 0, 0.5);
    animation: contentSlideIn 0.6s ease forwards;
}

@keyframes contentSlideIn {
    from {
        opacity: 0;
        transform: translateY(20px) scale(0.98);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

/* Decorative corner ornaments */
.story-content::before,
.story-content::after {
    content: '◆';
    position: absolute;
    font-size: 1.5rem;
    color: var(--accent-gold);
    text-shadow: 0 0 10px rgba(212, 175, 55, 0.5);
}

.story-content::before {
    top: -12px;
    left: 50%;
    transform: translateX(-50%);
}

.story-content::after {
    bottom: -12px;
    left: 50%;
    transform: translateX(-50%);
}

.story-header {
    text-align: center;
    padding: var(--spacing-lg) var(--spacing-lg) var(--spacing-md);
    border-bottom: 1px solid rgba(212, 175, 55, 0.3);
    background: linear-gradient(180deg, rgba(212, 175, 55, 0.08) 0%, transparent 100%);
}

.story-title {
    margin: 0;
    font-family: 'Cinzel', 'Times New Roman', serif;
    font-size: 2rem;
    font-weight: 600;
    color: var(--accent-gold);
    text-shadow:
        0 0 20px rgba(212, 175, 55, 0.6),
        0 2px 4px rgba(0, 0, 0, 0.5);
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.story-body {
    flex: 1;
    overflow-y: auto;
    margin: 0;
    padding: var(--spacing-lg) var(--spacing-xl);
    background: transparent;
    border: none;
    border-radius: 0;
}

/* Custom scrollbar for story body */
.story-body::-webkit-scrollbar {
    width: 8px;
}

.story-body::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
}

.story-body::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, var(--accent-gold) 0%, #8b7355 100%);
    border-radius: 4px;
}

.story-text {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 1.15rem;
    line-height: 1.9;
    color: #e8e4dc;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.story-paragraph {
    margin: 0 0 1.5em;
    text-indent: 0;
    opacity: 0;
    animation: paragraphReveal 0.5s ease forwards;
}

@keyframes paragraphReveal {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.story-paragraph:first-of-type::first-letter {
    float: left;
    font-family: 'Cinzel Decorative', 'Cinzel', serif;
    font-size: 3.5em;
    line-height: 0.8;
    padding-right: 0.1em;
    color: var(--accent-gold);
    text-shadow:
        0 0 15px rgba(212, 175, 55, 0.5),
        2px 2px 4px rgba(0, 0, 0, 0.5);
}

.story-paragraph:last-child {
    margin-bottom: 0;
}

.story-footer {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-lg);
    border-top: 1px solid rgba(212, 175, 55, 0.3);
    background: linear-gradient(0deg, rgba(212, 175, 55, 0.08) 0%, transparent 100%);
}

.story-btn {
    position: relative;
    padding: var(--spacing-md) var(--spacing-xl);
    min-width: 220px;
    background: linear-gradient(135deg, var(--accent-gold) 0%, #a08030 100%);
    border: 2px solid var(--accent-gold);
    border-radius: 4px;
    color: #1a1520;
    font-family: 'Cinzel', serif;
    font-size: 1.1rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow:
        0 4px 15px rgba(0, 0, 0, 0.3),
        0 0 20px rgba(212, 175, 55, 0.2);
}

.story-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.2) 0%, transparent 50%);
    border-radius: 2px;
    pointer-events: none;
}

.story-btn:hover {
    background: linear-gradient(135deg, #e5c04a 0%, #c9a030 100%);
    transform: translateY(-3px);
    box-shadow:
        0 6px 20px rgba(0, 0, 0, 0.4),
        0 0 30px rgba(212, 175, 55, 0.4);
}

.story-btn:active {
    transform: translateY(-1px);
}

.story-hint {
    font-family: 'Georgia', serif;
    font-size: 0.85rem;
    font-style: italic;
    color: rgba(232, 228, 220, 0.5);
    letter-spacing: 0.05em;
}

/* Divider decoration */
.story-divider {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    margin: 1.5em 0;
    color: var(--accent-gold);
    opacity: 0.6;
}

.story-divider::before,
.story-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent-gold), transparent);
}
`;

// Inject CSS
const styleSheet = document.createElement('style');
styleSheet.textContent = storyCSS;
document.head.appendChild(styleSheet);

// Export singleton
export const storyDisplay = new StoryDisplay();
export default storyDisplay;
