document.querySelectorAll(".slider-container").forEach(container => {
    const sliderIndex = parseFloat(container.dataset.sliderIndex);
    const arrow = container.querySelector(".arrow-indicator");
    const segmentsWrapper = container.querySelector(".segments-wrapper");

    const wrapperRect = segmentsWrapper.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    const maxSegments = 9;
    const percentage = (sliderIndex / maxSegments) * 100;

    const arrowHeight = arrow.offsetHeight || 20;
    const top = wrapperRect.top - containerRect.top - arrowHeight;
    arrow.style.top = `${top}px`
    arrow.style.left = `${percentage}%`;
});
