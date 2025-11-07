// Color Scale Legend - Visual key showing color-to-value mapping

class ColorLegend {
    constructor() {
        this.canvas = document.getElementById('color-legend-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.labelsContainer = document.getElementById('color-legend-labels');
        this.container = document.getElementById('color-legend');
        this.titleElement = document.querySelector('.color-legend-title');

        console.log('ColorLegend constructor:', {
            hasCanvas: !!this.canvas,
            hasCtx: !!this.ctx,
            canvasWidth: this.canvas ? this.canvas.width : 0,
            canvasHeight: this.canvas ? this.canvas.height : 0,
            hasLabels: !!this.labelsContainer,
            hasContainer: !!this.container
        });

        if (!this.canvas || !this.ctx || !this.labelsContainer || !this.container) {
            console.error('Color legend elements not found - cannot initialize');
            return;
        }

        // Test rendering - draw a simple gradient to verify canvas works
        this.ctx.fillStyle = '#ff0000';
        this.ctx.fillRect(0, 0, this.canvas.width / 2, this.canvas.height);
        this.ctx.fillStyle = '#0000ff';
        this.ctx.fillRect(this.canvas.width / 2, 0, this.canvas.width / 2, this.canvas.height);
        console.log('Test gradient drawn (red/blue split)');

        // Hide by default until data is loaded
        this.container.style.display = 'none';
    }

    /**
     * Update the legend to reflect current color scheme and data range
     * @param {string} colorScheme - Current color scheme name
     * @param {number} minValue - Minimum data value
     * @param {number} maxValue - Maximum data value
     * @param {string} unit - Unit label (e.g., "m", "°", "%")
     */
    update(colorScheme, minValue, maxValue, unit = 'm') {
        if (!this.ctx) return;

        // Handle special color schemes
        const isSlope = colorScheme === 'slope';
        const isAspect = colorScheme === 'aspect';
        const isAutoStretch = colorScheme === 'auto-stretch';

        // Set title based on color scheme
        let title = 'Elevation';
        if (isSlope) {
            title = 'Slope';
            minValue = 0;
            maxValue = 60;
            unit = '°';
        } else if (isAspect) {
            title = 'Aspect';
            minValue = 0;
            maxValue = 360;
            unit = '°';
        }

        // Update title element
        if (this.titleElement) {
            this.titleElement.textContent = title;
        }

        // Get the color scheme definition
        const scheme = COLOR_SCHEMES[colorScheme] || COLOR_SCHEMES['high-contrast'];

        // Draw the color gradient on canvas
        this.drawGradient(scheme, colorScheme);

        // Generate labels
        this.generateLabels(minValue, maxValue, unit, colorScheme);

        // Show the legend
        this.container.style.display = 'block';
    }

    /**
     * Draw the color gradient on the canvas
     */
    drawGradient(scheme, colorScheme) {
        if (!this.canvas || !this.ctx) {
            console.error('Canvas or context not available');
            return;
        }

        const width = this.canvas.width;
        const height = this.canvas.height;

        if (width === 0 || height === 0) {
            console.warn('Canvas dimensions are zero');
            return;
        }

        // Clear canvas with a test color to verify rendering works
        this.ctx.fillStyle = '#333';
        this.ctx.fillRect(0, 0, width, height);

        if (!scheme || !scheme.length) {
            console.error('Invalid color scheme');
            return;
        }

        const isBanded = colorScheme === 'hypsometric-banded' || 
                         colorScheme === 'hypsometric-intense' ||
                         colorScheme === 'hypsometric-refined';

        // Draw gradient from top (high) to bottom (low)
        for (let y = 0; y < height; y++) {
            // t goes from 1.0 (top) to 0.0 (bottom) - high values at top
            const t = 1.0 - (y / height);

            // Get color for this normalized value
            const color = this.getColorFromScheme(scheme, t, isBanded);

            if (color && typeof color.r === 'number') {
                this.ctx.fillStyle = `rgb(${Math.round(color.r * 255)}, ${Math.round(color.g * 255)}, ${Math.round(color.b * 255)})`;
                this.ctx.fillRect(0, y, width, 1);
            }
        }
    }

    /**
     * Get color from scheme for normalized value (0-1)
     */
    getColorFromScheme(scheme, t, isBanded) {
        const color = new THREE.Color();

        // Find the right color stops
        for (let i = 0; i < scheme.length - 1; i++) {
            const a = scheme[i];
            const b = scheme[i + 1];

            if (t >= a.stop && t <= b.stop) {
                if (isBanded) {
                    // Step function - use lower stop's color
                    color.copy(a.color);
                } else {
                    // Linear interpolation
                    const localT = (t - a.stop) / (b.stop - a.stop);
                    color.copy(a.color).lerp(b.color, localT);
                }
                return color;
            }
        }

        // Edge cases
        if (t <= scheme[0].stop) {
            color.copy(scheme[0].color);
        } else {
            color.copy(scheme[scheme.length - 1].color);
        }

        return color;
    }

    /**
     * Generate value labels for the legend
     */
    generateLabels(minValue, maxValue, unit, colorScheme) {
        this.labelsContainer.innerHTML = '';

        // Determine number of labels and format
        const numLabels = 5;
        const labels = [];

        for (let i = 0; i < numLabels; i++) {
            // Labels from top (max) to bottom (min)
            const t = 1.0 - (i / (numLabels - 1));
            const value = minValue + t * (maxValue - minValue);

            // Format based on value magnitude
            let formatted;
            if (colorScheme === 'slope' || colorScheme === 'aspect') {
                formatted = Math.round(value).toString();
            } else if (Math.abs(value) >= 1000) {
                formatted = (value / 1000).toFixed(1) + 'k';
            } else if (Math.abs(value) >= 100) {
                formatted = Math.round(value).toString();
            } else {
                formatted = value.toFixed(1);
            }

            labels.push({ value: formatted, unit });
        }

        // Create label elements
        labels.forEach(label => {
            const div = document.createElement('div');
            div.className = 'color-legend-label';
            div.textContent = `${label.value}${label.unit}`;
            this.labelsContainer.appendChild(div);
        });
    }

    /**
     * Hide the legend
     */
    hide() {
        if (this.container) {
            this.container.style.display = 'none';
        }
    }

    /**
     * Show the legend
     */
    show() {
        if (this.container) {
            this.container.style.display = 'flex';
        }
    }
}

// Global instance
let colorLegend = null;

/**
 * Initialize the color legend
 */
function initColorLegend() {
    colorLegend = new ColorLegend();
    return colorLegend;
}

/**
 * Update the color legend with current data
 */
function updateColorLegend() {
    // Check if legend should be visible (respect toggle state)
    const showColorScaleCheckbox = document.getElementById('showColorScale');
    if (showColorScaleCheckbox && !showColorScaleCheckbox.checked) {
        return; // Don't update if hidden
    }

    // Select stats source: global stats if enabled, otherwise per-region stats
    let stats = null;
    const useGlobalScale = (params && params.useGlobalScale);
    
    if (useGlobalScale && window.globalElevationStats) {
        stats = window.globalElevationStats;
    } else if (rawElevationData && rawElevationData.stats) {
        stats = rawElevationData.stats;
    }
    
    if (!colorLegend || !stats) {
        return;
    }

    const colorScheme = params.colorScheme || 'high-contrast';

    // Determine value range based on color scheme
    let minValue = stats.min;
    let maxValue = stats.max;
    let unit = 'm';

    // For auto-stretch, use the computed bounds
    if (colorScheme === 'auto-stretch' && stats.autoLow !== undefined && stats.autoHigh !== undefined) {
        minValue = stats.autoLow;
        maxValue = stats.autoHigh;
    }

    // Update the legend
    colorLegend.update(colorScheme, minValue, maxValue, unit);
}

