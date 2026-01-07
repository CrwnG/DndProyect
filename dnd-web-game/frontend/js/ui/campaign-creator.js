/**
 * D&D Combat Engine - Campaign Creator
 * AI-powered campaign generation and document import wizard
 *
 * Features:
 * - Generate BG3-quality campaigns from prompts
 * - Parse campaign PDFs with AI enhancement
 * - Parse pasted text content
 * - Campaign preview with structure visualization
 */

import { eventBus, EVENTS } from '../engine/event-bus.js';
import api from '../api/api-client.js';
import { toast } from './toast-notification.js';

/**
 * Escape HTML special characters to prevent XSS
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

/**
 * Campaign Creator Wizard
 */
class CampaignCreator {
    constructor() {
        this.container = null;
        this.isVisible = false;
        this.currentStep = 1;
        this.mode = null; // 'generate' or 'upload'
        this.generatedCampaign = null;

        // Form state
        this.formData = {
            // Generate mode
            concept: '',
            levelStart: 1,
            levelEnd: 10,
            length: 'medium',
            tone: 'mixed',
            // Upload mode
            uploadFile: null,
            textContent: '',
            textTitle: '',
            enhancement: 'moderate',
        };

        this.init();
    }

    init() {
        this.createContainer();
        this.setupEventListeners();
        this.checkAvailability();
    }

    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'campaign-creator';
        this.container.className = 'campaign-creator hidden';
        this.container.innerHTML = `
            <div class="campaign-creator-backdrop"></div>
            <div class="campaign-creator-modal">
                <div class="creator-header">
                    <h2>Create Campaign</h2>
                    <button class="close-btn" id="cc-close">&times;</button>
                </div>

                <div class="creator-progress">
                    <div class="progress-step active" data-step="1">
                        <span class="step-num">1</span>
                        <span class="step-label">Mode</span>
                    </div>
                    <div class="progress-line"></div>
                    <div class="progress-step" data-step="2">
                        <span class="step-num">2</span>
                        <span class="step-label">Details</span>
                    </div>
                    <div class="progress-line"></div>
                    <div class="progress-step" data-step="3">
                        <span class="step-num">3</span>
                        <span class="step-label">Preview</span>
                    </div>
                </div>

                <div class="creator-body">
                    <!-- Step 1: Choose Mode -->
                    <div class="creator-step" data-step="1">
                        <h3>How would you like to create your campaign?</h3>
                        <div class="mode-selection">
                            <button class="mode-card" id="cc-mode-generate">
                                <div class="mode-icon">✨</div>
                                <h4>Generate from Prompt</h4>
                                <p>Describe your campaign concept and let AI create a BG3-quality adventure with intense stories, meaningful choices, and memorable NPCs.</p>
                            </button>
                            <button class="mode-card" id="cc-mode-upload">
                                <div class="mode-icon">📄</div>
                                <h4>Import Document</h4>
                                <p>Upload a campaign PDF or paste text content. AI will parse encounters, NPCs, and structure into playable format.</p>
                            </button>
                        </div>
                    </div>

                    <!-- Step 2a: Generate Mode Form -->
                    <div class="creator-step hidden" data-step="2" data-mode="generate">
                        <h3>Describe Your Campaign</h3>

                        <div class="form-group">
                            <label for="cc-concept">Campaign Concept</label>
                            <textarea id="cc-concept" class="concept-input" placeholder="Describe your campaign idea...&#10;&#10;Example: A dark fantasy campaign where the party must uncover a conspiracy within a holy order. The paladins are secretly controlled by a mind flayer elder brain hiding beneath the cathedral. Include moral dilemmas, betrayal, and a dramatic climax in the undercrypt."></textarea>
                            <span class="hint">Be specific! Include themes, tone, key plot points, and what makes it exciting.</span>
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label>Party Level Range</label>
                                <div class="level-range">
                                    <input type="number" id="cc-level-start" min="1" max="20" value="1">
                                    <span>to</span>
                                    <input type="number" id="cc-level-end" min="1" max="20" value="10">
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="cc-length">Campaign Length</label>
                                <select id="cc-length">
                                    <option value="short">Short (5-8 encounters)</option>
                                    <option value="medium" selected>Medium (15-20 encounters)</option>
                                    <option value="long">Long (30+ encounters)</option>
                                    <option value="epic">Epic (50+ encounters)</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label for="cc-tone">Tone</label>
                                <select id="cc-tone">
                                    <option value="dark">Dark & Gritty</option>
                                    <option value="heroic">Heroic Fantasy</option>
                                    <option value="comedic">Comedic</option>
                                    <option value="mixed" selected>Mixed (Recommended)</option>
                                </select>
                            </div>
                        </div>

                        <div class="ai-notice">
                            <span class="ai-icon">🤖</span>
                            <span>AI will create a 3-act campaign with varied encounters, meaningful choices, and consequences that ripple through the story.</span>
                        </div>
                    </div>

                    <!-- Step 2b: Upload Mode Form -->
                    <div class="creator-step hidden" data-step="2" data-mode="upload">
                        <h3>Import Campaign Document</h3>

                        <div class="upload-tabs">
                            <button class="tab active" data-tab="pdf">Upload PDF</button>
                            <button class="tab" data-tab="text">Paste Text</button>
                        </div>

                        <div class="tab-content" data-tab="pdf">
                            <div class="drop-zone" id="cc-drop-zone">
                                <div class="drop-zone-content">
                                    <span class="drop-icon">📁</span>
                                    <p>Drag & drop a campaign PDF</p>
                                    <p class="drop-hint">or click to browse</p>
                                    <input type="file" id="cc-file-input" accept=".pdf" hidden>
                                </div>
                            </div>
                        </div>

                        <div class="tab-content hidden" data-tab="text">
                            <div class="form-group">
                                <label for="cc-text-title">Campaign Title</label>
                                <input type="text" id="cc-text-title" placeholder="Enter campaign name...">
                            </div>
                            <div class="form-group">
                                <label for="cc-text-content">Campaign Content</label>
                                <textarea id="cc-text-content" class="text-content-input" placeholder="Paste your campaign text here...&#10;&#10;Include chapter headers, encounter descriptions, NPC names, stat blocks, etc."></textarea>
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="cc-enhancement">AI Enhancement Level</label>
                            <select id="cc-enhancement">
                                <option value="minimal">Minimal - Just parse structure</option>
                                <option value="moderate" selected>Moderate - Fill gaps with AI (Recommended)</option>
                                <option value="full">Full - Rich BG3-quality enhancement</option>
                            </select>
                            <span class="hint">Higher enhancement creates richer descriptions and better pacing but takes longer.</span>
                        </div>
                    </div>

                    <!-- Step 3: Preview -->
                    <div class="creator-step hidden" data-step="3">
                        <h3>Campaign Preview</h3>

                        <div id="cc-preview-content" class="preview-content">
                            <!-- Filled dynamically -->
                        </div>
                    </div>

                    <!-- Loading State -->
                    <div class="creator-loading hidden">
                        <div class="loading-spinner"></div>
                        <p class="loading-text">Generating your campaign...</p>
                        <p class="loading-hint">This may take a moment as AI crafts your adventure.</p>
                    </div>

                    <!-- Error State -->
                    <div class="creator-error hidden">
                        <div class="error-icon">⚠️</div>
                        <p class="error-text"></p>
                        <button class="btn secondary" id="cc-retry">Try Again</button>
                    </div>
                </div>

                <div class="creator-footer">
                    <button class="btn secondary" id="cc-back">Back</button>
                    <button class="btn primary" id="cc-next">Next</button>
                    <button class="btn primary hidden" id="cc-create">Create Campaign</button>
                    <button class="btn primary hidden" id="cc-launch">Launch Campaign</button>
                </div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    setupEventListeners() {
        // Close button
        this.container.querySelector('#cc-close').addEventListener('click', () => this.hide());
        this.container.querySelector('.campaign-creator-backdrop').addEventListener('click', () => this.hide());

        // Mode selection
        this.container.querySelector('#cc-mode-generate').addEventListener('click', () => {
            this.mode = 'generate';
            this.goToStep(2);
        });
        this.container.querySelector('#cc-mode-upload').addEventListener('click', () => {
            this.mode = 'upload';
            this.goToStep(2);
        });

        // Navigation
        this.container.querySelector('#cc-back').addEventListener('click', () => this.goBack());
        this.container.querySelector('#cc-next').addEventListener('click', () => this.goNext());
        this.container.querySelector('#cc-create').addEventListener('click', () => this.createCampaign());
        this.container.querySelector('#cc-launch').addEventListener('click', () => this.launchCampaign());
        this.container.querySelector('#cc-retry').addEventListener('click', () => this.retry());

        // Upload tabs
        this.container.querySelectorAll('.upload-tabs .tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchUploadTab(tab.dataset.tab));
        });

        // File drop zone
        const dropZone = this.container.querySelector('#cc-drop-zone');
        const fileInput = this.container.querySelector('#cc-file-input');

        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const file = e.dataTransfer.files[0];
            if (file) this.handleFileSelect(file);
        });
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this.handleFileSelect(file);
        });

        // Form inputs
        this.container.querySelector('#cc-concept').addEventListener('input', (e) => {
            this.formData.concept = e.target.value;
        });
        this.container.querySelector('#cc-level-start').addEventListener('change', (e) => {
            this.formData.levelStart = parseInt(e.target.value) || 1;
        });
        this.container.querySelector('#cc-level-end').addEventListener('change', (e) => {
            this.formData.levelEnd = parseInt(e.target.value) || 10;
        });
        this.container.querySelector('#cc-length').addEventListener('change', (e) => {
            this.formData.length = e.target.value;
        });
        this.container.querySelector('#cc-tone').addEventListener('change', (e) => {
            this.formData.tone = e.target.value;
        });
        this.container.querySelector('#cc-text-title').addEventListener('input', (e) => {
            this.formData.textTitle = e.target.value;
        });
        this.container.querySelector('#cc-text-content').addEventListener('input', (e) => {
            this.formData.textContent = e.target.value;
        });
        this.container.querySelector('#cc-enhancement').addEventListener('change', (e) => {
            this.formData.enhancement = e.target.value;
        });

        // ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });

        // Listen for open event
        eventBus.on(EVENTS.OPEN_CAMPAIGN_CREATOR, () => this.show());
    }

    async checkAvailability() {
        try {
            const status = await api.getCampaignGeneratorStatus();
            this.aiAvailable = status.campaign_generator?.available || false;
        } catch {
            this.aiAvailable = false;
        }
    }

    // =========================================================================
    // VISIBILITY
    // =========================================================================

    show() {
        this.container.classList.remove('hidden');
        this.isVisible = true;
        this.reset();
    }

    hide() {
        this.container.classList.add('hidden');
        this.isVisible = false;
    }

    reset() {
        this.currentStep = 1;
        this.mode = null;
        this.generatedCampaign = null;
        this.formData = {
            concept: '',
            levelStart: 1,
            levelEnd: 10,
            length: 'medium',
            tone: 'mixed',
            uploadFile: null,
            textContent: '',
            textTitle: '',
            enhancement: 'moderate',
        };

        // Reset form fields
        this.container.querySelector('#cc-concept').value = '';
        this.container.querySelector('#cc-level-start').value = '1';
        this.container.querySelector('#cc-level-end').value = '10';
        this.container.querySelector('#cc-length').value = 'medium';
        this.container.querySelector('#cc-tone').value = 'mixed';
        this.container.querySelector('#cc-text-title').value = '';
        this.container.querySelector('#cc-text-content').value = '';
        this.container.querySelector('#cc-enhancement').value = 'moderate';

        // Reset drop zone
        const dropZone = this.container.querySelector('#cc-drop-zone');
        dropZone.innerHTML = `
            <div class="drop-zone-content">
                <span class="drop-icon">📁</span>
                <p>Drag & drop a campaign PDF</p>
                <p class="drop-hint">or click to browse</p>
                <input type="file" id="cc-file-input" accept=".pdf" hidden>
            </div>
        `;

        this.updateStepDisplay();
    }

    // =========================================================================
    // NAVIGATION
    // =========================================================================

    goToStep(step) {
        this.currentStep = step;
        this.updateStepDisplay();
    }

    goBack() {
        if (this.currentStep > 1) {
            this.goToStep(this.currentStep - 1);
        }
    }

    goNext() {
        if (this.currentStep === 2) {
            // Validate before creating
            if (!this.validateStep2()) return;
            this.createCampaign();
        }
    }

    updateStepDisplay() {
        // Update progress indicators
        this.container.querySelectorAll('.progress-step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.toggle('active', stepNum <= this.currentStep);
            step.classList.toggle('current', stepNum === this.currentStep);
        });

        // Hide all steps
        this.container.querySelectorAll('.creator-step').forEach(step => {
            step.classList.add('hidden');
        });

        // Show current step
        if (this.currentStep === 2 && this.mode) {
            // Show mode-specific step 2
            const modeStep = this.container.querySelector(`.creator-step[data-step="2"][data-mode="${this.mode}"]`);
            if (modeStep) modeStep.classList.remove('hidden');
        } else {
            const step = this.container.querySelector(`.creator-step[data-step="${this.currentStep}"]:not([data-mode])`);
            if (step) step.classList.remove('hidden');
        }

        // Hide loading/error states
        this.container.querySelector('.creator-loading').classList.add('hidden');
        this.container.querySelector('.creator-error').classList.add('hidden');

        // Update buttons
        const backBtn = this.container.querySelector('#cc-back');
        const nextBtn = this.container.querySelector('#cc-next');
        const createBtn = this.container.querySelector('#cc-create');
        const launchBtn = this.container.querySelector('#cc-launch');

        backBtn.classList.toggle('hidden', this.currentStep === 1);
        nextBtn.classList.toggle('hidden', this.currentStep !== 2);
        createBtn.classList.add('hidden');
        launchBtn.classList.toggle('hidden', this.currentStep !== 3);
    }

    // =========================================================================
    // FILE HANDLING
    // =========================================================================

    handleFileSelect(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            toast.error('Please select a PDF file');
            return;
        }

        this.formData.uploadFile = file;

        // Update drop zone
        const dropZone = this.container.querySelector('#cc-drop-zone');
        dropZone.innerHTML = `
            <div class="drop-zone-content success">
                <span class="drop-icon">✅</span>
                <p>${escapeHtml(file.name)}</p>
                <p class="drop-hint">Ready to parse</p>
            </div>
        `;
    }

    switchUploadTab(tabId) {
        // Update tabs
        this.container.querySelectorAll('.upload-tabs .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });

        // Update content
        this.container.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('hidden', content.dataset.tab !== tabId);
        });
    }

    // =========================================================================
    // VALIDATION
    // =========================================================================

    validateStep2() {
        if (this.mode === 'generate') {
            if (!this.formData.concept.trim() || this.formData.concept.length < 20) {
                toast.error('Please provide a more detailed campaign concept (at least 20 characters)');
                return false;
            }
            if (this.formData.levelStart > this.formData.levelEnd) {
                toast.error('Starting level cannot be higher than ending level');
                return false;
            }
        } else if (this.mode === 'upload') {
            const activeTab = this.container.querySelector('.upload-tabs .tab.active')?.dataset.tab;
            if (activeTab === 'pdf') {
                if (!this.formData.uploadFile) {
                    toast.error('Please select a PDF file');
                    return false;
                }
            } else {
                if (!this.formData.textContent.trim() || this.formData.textContent.length < 50) {
                    toast.error('Please paste more campaign content (at least 50 characters)');
                    return false;
                }
            }
        }
        return true;
    }

    // =========================================================================
    // CAMPAIGN CREATION
    // =========================================================================

    async createCampaign() {
        this.showLoading();

        try {
            let response;

            if (this.mode === 'generate') {
                // Generate from prompt
                this.setLoadingText('Crafting your adventure...');
                response = await api.generateCampaign(
                    this.formData.concept,
                    this.formData.levelStart,
                    this.formData.levelEnd,
                    this.formData.length,
                    this.formData.tone
                );
            } else {
                // Parse document
                const activeTab = this.container.querySelector('.upload-tabs .tab.active')?.dataset.tab;

                if (activeTab === 'pdf') {
                    this.setLoadingText('Parsing PDF document...');
                    response = await api.parseCampaignPDF(
                        this.formData.uploadFile,
                        this.formData.enhancement
                    );
                } else {
                    this.setLoadingText('Processing text content...');
                    response = await api.parseCampaignText(
                        this.formData.textContent,
                        this.formData.textTitle || 'Imported Campaign',
                        this.formData.enhancement
                    );
                }
            }

            if (response.campaign_id) {
                this.generatedCampaign = response;
                this.showPreview();
            } else {
                throw new Error(response.message || 'Failed to create campaign');
            }
        } catch (error) {
            console.error('[CampaignCreator] Creation failed:', error);
            this.showError(error.message || 'Failed to create campaign. Please try again.');
        }
    }

    showLoading() {
        this.container.querySelectorAll('.creator-step').forEach(step => step.classList.add('hidden'));
        this.container.querySelector('.creator-loading').classList.remove('hidden');
        this.container.querySelector('.creator-error').classList.add('hidden');

        // Hide footer buttons
        this.container.querySelector('#cc-back').classList.add('hidden');
        this.container.querySelector('#cc-next').classList.add('hidden');
        this.container.querySelector('#cc-launch').classList.add('hidden');
    }

    setLoadingText(text) {
        this.container.querySelector('.loading-text').textContent = text;
    }

    showError(message) {
        this.container.querySelector('.creator-loading').classList.add('hidden');
        this.container.querySelector('.creator-error').classList.remove('hidden');
        this.container.querySelector('.error-text').textContent = message;

        // Show back button
        this.container.querySelector('#cc-back').classList.remove('hidden');
    }

    retry() {
        this.goToStep(2);
    }

    // =========================================================================
    // PREVIEW
    // =========================================================================

    showPreview() {
        this.currentStep = 3;
        this.updateStepDisplay();

        const preview = this.container.querySelector('#cc-preview-content');
        const campaign = this.generatedCampaign;

        preview.innerHTML = `
            <div class="preview-header">
                <h4>${escapeHtml(campaign.name)}</h4>
                <p class="preview-desc">${escapeHtml(campaign.description)}</p>
            </div>

            <div class="preview-stats">
                <div class="stat-card">
                    <span class="stat-value">${campaign.acts || 0}</span>
                    <span class="stat-label">Acts</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">${campaign.chapters || 0}</span>
                    <span class="stat-label">Chapters</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">${campaign.encounters || 0}</span>
                    <span class="stat-label">Encounters</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">${campaign.npcs || 0}</span>
                    <span class="stat-label">NPCs</span>
                </div>
            </div>

            ${campaign.enhancement_level ? `
            <div class="preview-info">
                <span class="info-label">Enhancement:</span>
                <span class="info-value">${escapeHtml(campaign.enhancement_level)}</span>
            </div>
            ` : ''}

            <div class="preview-message success">
                <span class="message-icon">✅</span>
                <span>${escapeHtml(campaign.message)}</span>
            </div>
        `;
    }

    // =========================================================================
    // LAUNCH CAMPAIGN
    // =========================================================================

    async launchCampaign() {
        if (!this.generatedCampaign?.campaign_id) {
            toast.error('No campaign to launch');
            return;
        }

        try {
            // Import the generated campaign to the regular campaign system
            const campaignData = await api.getGeneratedCampaign(this.generatedCampaign.campaign_id);

            // Import to campaign list
            const importResponse = await api.importCampaign(campaignData);

            if (importResponse.success || importResponse.campaign_id) {
                toast.success('Campaign created! Select it from the campaign list.');
                this.hide();

                // Emit event to refresh campaign list
                eventBus.emit(EVENTS.CAMPAIGN_IMPORTED, {
                    campaignId: importResponse.campaign_id || this.generatedCampaign.campaign_id,
                });
            } else {
                throw new Error(importResponse.error || 'Failed to import campaign');
            }
        } catch (error) {
            console.error('[CampaignCreator] Launch failed:', error);
            toast.error('Failed to launch campaign: ' + error.message);
        }
    }
}

// Register event
if (!EVENTS.OPEN_CAMPAIGN_CREATOR) {
    EVENTS.OPEN_CAMPAIGN_CREATOR = 'open_campaign_creator';
}
if (!EVENTS.CAMPAIGN_IMPORTED) {
    EVENTS.CAMPAIGN_IMPORTED = 'campaign_imported';
}

// Export singleton
export const campaignCreator = new CampaignCreator();
export default campaignCreator;
