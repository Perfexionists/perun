function switchGridLayout(gridId) {
    const elements = document.querySelectorAll(`${gridId} .comparison_container_stacked`);

    elements.forEach(element => {
        const currentDirection = window.getComputedStyle(element).flexDirection;
        if (currentDirection === "row") {
            element.style.flexDirection = "column";
        } else {
            element.style.flexDirection = "row";
        }
    });

    document.querySelectorAll(`${gridId} .svg_switch_container`).forEach(svg => {
        svg.classList.toggle("hidden");
        svg.classList.toggle("visible");
    });
}