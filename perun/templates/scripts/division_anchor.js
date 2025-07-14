const traces_table = document.getElementById("traces");
const anchorsBase = document.getElementById("division_anchor__baseline");
const anchorTgt = document.getElementById("division_anchor__target");

document.addEventListener("scroll", () => {
    const tracesTableBottomOffset =
        traces_table.offsetTop + traces_table.offsetHeight;

    if (
        traces_table.offsetTop <= window.scrollY &&
        tracesTableBottomOffset >= window.scrollY
    ) {
        anchorsBase.style.display = "none";
        anchorTgt.style.display = "none";
    } else {
        anchorsBase.style.display = "unset";
        anchorTgt.style.display = "unset";
    }
});
