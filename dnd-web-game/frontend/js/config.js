/**
 * D&D Combat Engine - Configuration
 */

export const CONFIG = {
    // API Configuration
    API_BASE_URL: 'http://localhost:8000/api',

    // Grid Configuration
    GRID: {
        SIZE: 8,           // 8x8 grid
        CELL_SIZE: 60,     // pixels per cell
        CANVAS_SIZE: 480,  // 8 * 60 = 480px
    },

    // Colors
    COLORS: {
        // Grid
        GRID_BG: '#0d1117',
        GRID_LINE: '#2a3a4a',
        GRID_LINE_MAJOR: '#3a4a5a',

        // Cells
        CELL_EMPTY: '#1a2332',
        CELL_WALL: '#444444',
        CELL_DIFFICULT: '#2a3a2a',

        // Highlights
        HIGHLIGHT_REACHABLE: 'rgba(46, 204, 113, 0.3)',
        HIGHLIGHT_REACHABLE_BORDER: 'rgba(46, 204, 113, 0.7)',
        HIGHLIGHT_ATTACK: 'rgba(231, 76, 60, 0.3)',
        HIGHLIGHT_ATTACK_BORDER: 'rgba(231, 76, 60, 0.7)',
        HIGHLIGHT_SELECTED: 'rgba(212, 175, 55, 0.4)',
        HIGHLIGHT_SELECTED_BORDER: '#d4af37',
        HIGHLIGHT_PATH: 'rgba(52, 152, 219, 0.4)',
        HIGHLIGHT_PATH_BORDER: 'rgba(52, 152, 219, 0.7)',
        HIGHLIGHT_HOVER: 'rgba(255, 255, 255, 0.1)',

        // Tokens
        TOKEN_PLAYER: '#2ecc71',
        TOKEN_PLAYER_BORDER: '#d4af37',
        TOKEN_ENEMY: '#e74c3c',
        TOKEN_ENEMY_BORDER: '#c0392b',
        TOKEN_ALLIED: '#3498db',

        // Text
        TEXT_LIGHT: '#e8e8e8',
        TEXT_DARK: '#1a1a2e',

        // HP Colors
        HP_FULL: '#2ecc71',
        HP_MID: '#f39c12',
        HP_LOW: '#e74c3c',

        // Cover Indicators (D&D 5e: half +2 AC, three-quarters +5 AC)
        COVER_HALF: 'rgba(52, 152, 219, 0.35)',
        COVER_HALF_BORDER: 'rgba(52, 152, 219, 0.8)',
        COVER_THREE_QUARTERS: 'rgba(142, 68, 173, 0.35)',
        COVER_THREE_QUARTERS_BORDER: 'rgba(142, 68, 173, 0.8)',

        // Elevation Indicators
        ELEVATION_BASE: 'rgba(139, 119, 101, 0.2)',
        ELEVATION_HIGH: 'rgba(100, 80, 60, 0.3)',
        ELEVATION_SHADOW: 'rgba(0, 0, 0, 0.15)',

        // Threat Zone Indicators
        THREAT_ZONE: 'rgba(231, 76, 60, 0.15)',
        THREAT_ZONE_BORDER: 'rgba(231, 76, 60, 0.4)',
        THREAT_WARNING: 'rgba(243, 156, 18, 0.4)',
    },

    // Token Configuration
    TOKEN: {
        RADIUS: 22,        // Token circle radius
        BORDER_WIDTH: 3,
        FONT_SIZE: 12,
    },

    // Animation Settings
    ANIMATION: {
        MOVE_DURATION: 200,     // ms per cell
        ATTACK_DURATION: 300,
        DAMAGE_FLOAT_DURATION: 1000,
    },

    // Game Rules
    RULES: {
        MOVEMENT_COST_NORMAL: 5,     // 5ft per cell
        MOVEMENT_COST_DIFFICULT: 10, // 10ft per cell (difficult terrain)
        DIAGONAL_COST: 5,            // Same as normal in 5e
        MELEE_RANGE: 5,              // 5ft = 1 cell
        DEFAULT_SPEED: 30,           // 30ft default movement
    },

    // Debug Mode
    DEBUG: true,
};

// Freeze configuration to prevent accidental modification
Object.freeze(CONFIG);
Object.freeze(CONFIG.GRID);
Object.freeze(CONFIG.COLORS);
Object.freeze(CONFIG.TOKEN);
Object.freeze(CONFIG.ANIMATION);
Object.freeze(CONFIG.RULES);

export default CONFIG;
