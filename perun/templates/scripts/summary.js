function setupSlider(sliderInfo) {
    const sliderContainer = document.getElementById(`slider-container-${sliderInfo.id}`);
    const segmentsWrapper = document.getElementById(`segmentsWrapper-${sliderInfo.id}`);
    const arrowIndicator = document.getElementById(`arrowIndicator-${sliderInfo.id}`);
    const ratingDisplay = document.getElementById(`ratingDisplay-${sliderInfo.id}`);

    if (!sliderContainer || !segmentsWrapper || !arrowIndicator || !ratingDisplay) {
        console.error(`Slider elements not found for ID: ${sliderInfo.id}`);
        return;
    }

    const numSegments = segmentsWrapper.children.length;
    let sliderRect;

    function updateRating(arrowLeft, ratingText) {
        const gapSize = parseFloat(getComputedStyle(segmentsWrapper).gap);
        const totalGapWidth = gapSize * (numSegments - 1);
        const effectiveSegmentWidth = (sliderRect.width - totalGapWidth) / numSegments;

        let currentSegmentIndex = 0;
        let accumulatedWidth = 0;
        for (let i = 0; i < numSegments; i++) {
            const segmentAndGapWidth = effectiveSegmentWidth + (i < numSegments - 1 ? gapSize : 0);
            if (arrowLeft >= accumulatedWidth && arrowLeft < accumulatedWidth + segmentAndGapWidth) {
                currentSegmentIndex = i;
                break;
            }
            accumulatedWidth += segmentAndGapWidth;
        }

        currentSegmentIndex = Math.max(0, Math.min(numSegments - 1, currentSegmentIndex));
        ratingDisplay.textContent = ratingText;
    }

    function initializeSliderRect() {
        sliderRect = segmentsWrapper.getBoundingClientRect();
        const gapSize = parseFloat(getComputedStyle(segmentsWrapper).gap);
        const totalGapWidth = gapSize * (numSegments - 1);
        const effectiveSegmentWidth = (sliderRect.width - totalGapWidth) / numSegments;

        const desiredTileIndex = sliderInfo.segmentIx;

        let initialArrowLeft = (desiredTileIndex * effectiveSegmentWidth) + (desiredTileIndex * gapSize) + (effectiveSegmentWidth / 2);

        initialArrowLeft = Math.max(0, Math.min(initialArrowLeft, sliderRect.width));

        const wrapperRect = segmentsWrapper.getBoundingClientRect();
        const containerRect = sliderContainer.getBoundingClientRect();

        const topOffset = wrapperRect.top - containerRect.top - 10;

        arrowIndicator.style.top = `${topOffset}px`;
        arrowIndicator.style.left = `${initialArrowLeft}px`;

        updateRating(initialArrowLeft, sliderInfo.text);
    }

    window.addEventListener('load', initializeSliderRect);
    window.addEventListener('resize', initializeSliderRect);
}

const sliders = [
    { id: 1, text: '100G → 130G', segmentIx: 4 },
    { id: 2, text: '1166.947 → 2193.86', segmentIx: 8 },
    { id: 3, text: '32 → 31', segmentIx: 5 }
];

sliders.forEach(slider => {
    setupSlider(slider);
});