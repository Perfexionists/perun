/**
 * Synchronizes the height of identical elements across multiple flexbox cards.
 * Measures the natural wrapped height of all matching elements and explicitly locks 
 * them to the maximum height, guaranteeing horizontal alignment.
 * 
 * @param {string} selector - CSS selector of the nested elements to equalize
 * @param {NodeList|Array} containers - The parent wrappers to search within
 */

function syncHeights(selector, containers) {
    let maxHeight = 0;
    const els = [];
    containers.forEach(c => {
        const el = c.querySelector(selector);
        if (el) {
            el.style.height = 'auto'; // Reset to measure natural wrapped height
            els.push(el);
        }
    });

    els.forEach(el => {
        maxHeight = Math.max(maxHeight, el.offsetHeight);
    });

    // Rigidly lock to the tallest sibling globally to keep horizontal rows perfectly synched
    els.forEach(el => {
        el.style.height = `${maxHeight}px`;
    });
}

function positionArrows() {
    const containers = document.querySelectorAll(".slider-container");

    // Harmonize vertical rows globally BEFORE calculating coordinates!
    if (containers.length > 0) {
        syncHeights('.slider-title-wrapper', containers);
        syncHeights('h2[class*="color-segment"]', containers);
        syncHeights('.rating-display', containers);
    }

    containers.forEach(container => {
        const sliderIndex = parseFloat(container.dataset.sliderIndex);
        const arrow = container.querySelector(".arrow-indicator");
        const segmentsWrapper = container.querySelector(".segments-wrapper");

        const maxSegmentsIndex = 9;
        const clampedIndex = Math.max(0, Math.min(maxSegmentsIndex, sliderIndex));

        // padding included
        const percentage = 5 + (clampedIndex / maxSegmentsIndex) * 90;

        const wrapperRect = segmentsWrapper.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();

        const top = wrapperRect.top - containerRect.top - (arrow.offsetHeight || 20);
        arrow.style.top = `${top}px`;

        arrow.style.left = `${percentage}%`;
    });
}
const observer = new ResizeObserver(() => {
    positionArrows();
});

document.querySelectorAll('.slider-container').forEach(container => {
    observer.observe(container);
});

positionArrows();
