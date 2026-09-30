//-------NOTCHED SLIDER-------
// Every slider shows notches with numeric labels (including both endpoints) and its current value.

export function createSlider({ container, label, min, max, step, value, ticks, format, onInput }) {
    const root = document.createElement('div');
    root.className = 'slider';
    root.innerHTML = `
        <div class="slider-head"><span class="slider-label"></span><span class="slider-value"></span></div>
        <input type="range" class="slider-input">
        <div class="slider-ticks"></div>`;
    root.querySelector('.slider-label').textContent = label;
    const input = root.querySelector('.slider-input');
    const valueEl = root.querySelector('.slider-value');
    const ticksEl = root.querySelector('.slider-ticks');
    Object.assign(input, { min, max, step, value });

    for (const tick of ticks) {
        const fraction = (tick.value - min) / (max - min);
        const tickEl = document.createElement('span');
        tickEl.className = 'slider-tick';
        tickEl.style.setProperty('--fraction', fraction);
        tickEl.textContent = tick.label;
        ticksEl.appendChild(tickEl);
    }

    const render = () => { valueEl.textContent = format(Number(input.value)); };
    input.addEventListener('input', () => {
        render();
        onInput(Number(input.value));
    });
    render();
    container.appendChild(root);

    return {
        get value() { return Number(input.value); },
        set value(next) { input.value = next; render(); },
    };
}

// Discrete slider over an explicit list of values; each value is a labeled notch.
export function createStepSlider({ container, label, values, index, format, tickFormat, onInput }) {
    return createSlider({
        container, label, min: 0, max: values.length - 1, step: 1, value: index,
        ticks: values.map((v, i) => ({ value: i, label: (tickFormat || format)(v) })),
        format: (i) => format(values[i]),
        onInput: (i) => onInput(values[i], i),
    });
}
