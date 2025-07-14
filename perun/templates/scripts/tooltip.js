document.addEventListener("DOMContentLoaded", function () {
    const section_guide = document.createElement("div");
    section_guide.classList.add("section_guide");
    document.body.appendChild(section_guide);

    document.addEventListener("mouseover", function (event) {
        const target = event.target.closest(".info-icon__header");
        if (target) {
            section_guide.innerHTML = target.getAttribute("data-tooltip")
                .trim()
                .split("\n")
                .map((line, index) => `[${index + 1}] ${line.trim()}`)
                .join("<br><br>");
            section_guide.classList.add("visible");
            section_guide.style.left = event.pageX + 10 + "px";
            section_guide.style.top = event.pageY + 10 + "px";
        }
    });

    document.addEventListener("mousemove", function (event) {
        if (section_guide.classList.contains("visible")) {
            section_guide.style.left = event.pageX + 10 + "px";
            section_guide.style.top = event.pageY + 10 + "px";
        }
    });

    document.addEventListener("mouseout", function (event) {
        if (!event.relatedTarget || !event.relatedTarget.closest(".info-icon__header")) {
            section_guide.classList.remove("visible");
        }
    });
});