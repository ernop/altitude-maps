// Color schemes for terrain visualization

const COLOR_SCHEMES = {
    elevation: [
        { stop: 0.0, color: new THREE.Color(0x0000ff) },
        { stop: 0.5, color: new THREE.Color(0x00ff00) },
        { stop: 1.0, color: new THREE.Color(0xff0000) }
    ],
    grayscale: [
        { stop: 0.0, color: new THREE.Color(0x111111) },
        { stop: 1.0, color: new THREE.Color(0xffffff) }
    ],
    rainbow: [
        { stop: 0.0, color: new THREE.Color(0x9400d3) },
        { stop: 0.2, color: new THREE.Color(0x0000ff) },
        { stop: 0.4, color: new THREE.Color(0x00ff00) },
        { stop: 0.6, color: new THREE.Color(0xffff00) },
        { stop: 0.8, color: new THREE.Color(0xff7f00) },
        { stop: 1.0, color: new THREE.Color(0xff0000) }
    ],
    earth: [
        { stop: 0.0, color: new THREE.Color(0x2C1810) },
        { stop: 0.3, color: new THREE.Color(0x6B5244) },
        { stop: 0.6, color: new THREE.Color(0x8B9A6B) },
        { stop: 1.0, color: new THREE.Color(0xC4B89C) }
    ],
    heatmap: [
        { stop: 0.0, color: new THREE.Color(0x000033) },
        { stop: 0.25, color: new THREE.Color(0x0066ff) },
        { stop: 0.5, color: new THREE.Color(0x00ff66) },
        { stop: 0.75, color: new THREE.Color(0xffff00) },
        { stop: 1.0, color: new THREE.Color(0xff0000) }
    ],
    test: [
        { stop: 0.00, color: new THREE.Color(0x001b3a) },
        { stop: 0.08, color: new THREE.Color(0x004e98) },
        { stop: 0.16, color: new THREE.Color(0x00b4d8) },
        { stop: 0.28, color: new THREE.Color(0x28a745) },
        { stop: 0.38, color: new THREE.Color(0xfff275) },
        { stop: 0.46, color: new THREE.Color(0xffb703) },
        { stop: 0.54, color: new THREE.Color(0xfb8500) },
        { stop: 0.64, color: new THREE.Color(0xe85d04) },
        { stop: 0.74, color: new THREE.Color(0xd00000) },
        { stop: 0.86, color: new THREE.Color(0x9d0208) },
        { stop: 0.94, color: new THREE.Color(0xf5f5f5) },
        { stop: 1.00, color: new THREE.Color(0xffffff) }
    ],
    'terrain-muted': [
        { stop: 0.0, color: new THREE.Color(0x274b4a) },
        { stop: 0.3, color: new THREE.Color(0x4e6e58) },
        { stop: 0.6, color: new THREE.Color(0x7a8f6a) },
        { stop: 0.85, color: new THREE.Color(0xa8b59a) },
        { stop: 1.0, color: new THREE.Color(0xdedfd6) }
    ],
    'relief-emphasis': [
        { stop: 0.0, color: new THREE.Color(0x2b2b2b) },
        { stop: 0.5, color: new THREE.Color(0x6aa84f) },
        { stop: 0.75, color: new THREE.Color(0xf1c232) },
        { stop: 1.0, color: new THREE.Color(0xe06666) }
    ],
    'diverging-elevation': [
        { stop: 0.0, color: new THREE.Color(0x313695) },
        { stop: 0.5, color: new THREE.Color(0xf7f7f7) },
        { stop: 1.0, color: new THREE.Color(0xa50026) }
    ],
    hypsometric: [
        { stop: 0.0, color: new THREE.Color(0x00441b) },
        { stop: 0.2, color: new THREE.Color(0x1a9850) },
        { stop: 0.4, color: new THREE.Color(0x66bd63) },
        { stop: 0.6, color: new THREE.Color(0xfdae61) },
        { stop: 0.8, color: new THREE.Color(0xf46d43) },
        { stop: 1.0, color: new THREE.Color(0xa50f15) }
    ],
    'hypsometric-natural': [
        { stop: 0.00, color: new THREE.Color(0x0a4f2c) }, // deep green lowlands
        { stop: 0.20, color: new THREE.Color(0x2f7d32) }, // green
        { stop: 0.40, color: new THREE.Color(0x9bbf6b) }, // olive/grass
        { stop: 0.60, color: new THREE.Color(0xc9b27d) }, // tan foothills
        { stop: 0.80, color: new THREE.Color(0x8b5e34) }, // brown highlands
        { stop: 0.92, color: new THREE.Color(0xdedede) }, // light grey
        { stop: 1.00, color: new THREE.Color(0xffffff) } // white peaks
    ],
    'hypsometric-banded': [
        // Discrete elevation bands (will be rendered with step function)
        { stop: 0.00, color: new THREE.Color(0x0a4f2c) }, // deep green (0-15%)
        { stop: 0.15, color: new THREE.Color(0x2f7d32) }, // green (15-30%)
        { stop: 0.30, color: new THREE.Color(0x7da850) }, // yellow-green (30-45%)
        { stop: 0.45, color: new THREE.Color(0xb8a665) }, // tan (45-60%)
        { stop: 0.60, color: new THREE.Color(0xa87d50) }, // brown (60-75%)
        { stop: 0.75, color: new THREE.Color(0x8b5e34) }, // dark brown (75-90%)
        { stop: 0.90, color: new THREE.Color(0xc8c8c8) }, // grey (90-95%)
        { stop: 0.95, color: new THREE.Color(0xffffff) } // white peaks (95-100%)
    ]
};

const COLOR_SCHEME_DESCRIPTIONS = {
    'test': 'High-contrast ramp to accentuate small elevation changes.',
    'auto-stretch': 'Dynamic percentile stretch (2-98%) for maximum contrast on this map.',
    'slope': 'Colors by slope steepness (degrees): blue=flat, red=steep.',
    'aspect': 'Hue encodes slope direction (0-360deg).',
    'elevation': 'Classic blue-red by relative elevation.',
    'grayscale': 'Simple lightness by elevation.',
    'rainbow': 'Multi-hue (use cautiously).',
    'earth': 'Earth tones for subdued presentation.',
    'heatmap': 'Dark to hot colors by elevation.',
    'terrain-muted': 'Softer natural palette for overlays and labels.',
    'relief-emphasis': 'Color ramp tuned to emphasize relief with gentle chroma.',
    'diverging-elevation': 'Diverges around mid-elevation to reveal relative high/low areas.',
    'hypsometric': 'Perceptual hypsometric tint for terrain form.',
    'hypsometric-natural': 'Hypsometric with naturalistic greens-tans-browns-snow for peaks.',
    'hypsometric-banded': 'Discrete elevation zones - classic topographic map style.'
};

function updateColorSchemeDescription() {
    const el = document.getElementById('colorSchemeDescription');
    if (!el) return;
    const key = params.colorScheme || 'test';
    el.textContent = COLOR_SCHEME_DESCRIPTIONS[key] || '';
}

