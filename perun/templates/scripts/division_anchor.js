const anchorsBase = document.getElementById("division_anchor__baseline");
const anchorTgt = document.getElementById("division_anchor__target");

const hiddenSections = [
    document.getElementById("traces"),
    document.getElementById("overview")
].filter(el => el !== null);

document.addEventListener("scroll", () => {
    let shouldHide = false;
    for (const section of hiddenSections) {
        const rect = section.getBoundingClientRect();
        if (rect.top <= 150 && rect.bottom >= 0) {
            shouldHide = true;
            break;
        }
    }

    if (shouldHide) {
        anchorsBase.style.display = "none";
        anchorTgt.style.display = "none";
    } else {
        anchorsBase.style.display = "unset";
        anchorTgt.style.display = "unset";
    }
});

document.dispatchEvent(new Event("scroll"));
