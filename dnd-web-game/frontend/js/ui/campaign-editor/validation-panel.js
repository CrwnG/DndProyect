/**
 * D&D Combat Engine - Validation Panel
 * Displays campaign validation errors and warnings.
 */

/**
 * Validation results display panel
 */
export class ValidationPanel {
    constructor(container) {
        this.container = container;
        this.results = null;
    }

    showResults(results) {
        this.results = results;
        this.render();
    }

    clear() {
        this.results = null;
        this.container.innerHTML = `
            <h3>Validation</h3>
            <div class="validation-placeholder">
                <p>Click "Validate" to check campaign</p>
            </div>
        `;
    }

    render() {
        if (!this.results) {
            this.clear();
            return;
        }

        const { errors = [], warnings = [] } = this.results;
        const isValid = errors.length === 0 && warnings.length === 0;

        let html = `<h3>Validation Results</h3>`;

        if (isValid) {
            html += `
                <div class="validation-success">
                    <span class="icon">✓</span>
                    <span>Campaign is valid!</span>
                </div>
            `;
        } else {
            if (errors.length > 0) {
                html += `
                    <div class="validation-section errors">
                        <h4>Errors (${errors.length})</h4>
                        <ul>
                            ${errors.map(e => `<li class="error-item">${this.escapeHtml(e)}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }

            if (warnings.length > 0) {
                html += `
                    <div class="validation-section warnings">
                        <h4>Warnings (${warnings.length})</h4>
                        <ul>
                            ${warnings.map(w => `<li class="warning-item">${this.escapeHtml(w)}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }
        }

        this.container.innerHTML = html;
    }

    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }
}

export default ValidationPanel;
