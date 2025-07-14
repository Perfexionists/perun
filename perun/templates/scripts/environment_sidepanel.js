document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".environment-property").forEach((property) => {
        const toggleArrow = property.querySelector(".toggle-arrow");
        const environmentValues = property.querySelector(".environment-values");

        environmentValues.style.height = "auto";

        toggleArrow.addEventListener("click", () => {
            if (environmentValues.classList.contains("collapsed")) {
                environmentValues.classList.remove("collapsed");
                environmentValues.style.height = `${environmentValues.scrollHeight}px`;
                toggleArrow.classList.remove("collapsed");
            } else {
                environmentValues.style.height = `${environmentValues.scrollHeight}px`;
                requestAnimationFrame(() => {
                    environmentValues.style.height = "0";
                });
                environmentValues.classList.add("collapsed");
                toggleArrow.classList.add("collapsed");
            }
        });

        environmentValues.addEventListener("transitionend", () => {
            if (!environmentValues.classList.contains("collapsed")) {
                environmentValues.style.height = "auto";
            }
        });
    });
});