document.addEventListener("DOMContentLoaded", () => {
    const SIDEPANEL_UNEXPANDED_WIDTH = 50;

    const trigger = document.getElementById("navigation-panel__submenu--trigger");
    const submenuLinks = document.getElementById("navigation-panel__submenu--links");
    const navigationSidePanel = document.getElementById("navigation-side-panel");

    let panelFullyExpanded = false;
    let submenuRequested = false;

    function positionSubmenu() {
        const panelWidth = navigationSidePanel.offsetWidth;
        const offsetFromTop = trigger.getBoundingClientRect().top;

        submenuLinks.style.right = (panelWidth + 10) + "px";
        submenuLinks.style.top = (offsetFromTop + (submenuLinks.offsetHeight / 2)) + "px";
    }

    navigationSidePanel.addEventListener("transitionend", (e) => {
        if (e.propertyName === "width" && navigationSidePanel.offsetWidth > SIDEPANEL_UNEXPANDED_WIDTH) {
            panelFullyExpanded = true;
            positionSubmenu();
            if (submenuRequested) {
                showSubmenu();
                submenuRequested = false;
            }
        } else if (e.propertyName === "width" && navigationSidePanel.offsetWidth <= SIDEPANEL_UNEXPANDED_WIDTH) {
            panelFullyExpanded = false;
        }
      });

    function showSubmenu() {
        navigationSidePanel.classList.add("expanded");
        submenuLinks.style.display = "flex";
        positionSubmenu();
    }

    function hideSubmenu() {
        navigationSidePanel.classList.remove("expanded");
        submenuLinks.style.display = "none";
    }

    trigger.addEventListener("mouseenter", () => {
        if (panelFullyExpanded) {
          showSubmenu();
        } else {
          submenuRequested = true;
        }
    });

    submenuLinks.addEventListener("mouseenter", () => {
        if (panelFullyExpanded) showSubmenu();
    });

    trigger.addEventListener("mouseleave", () => {
        setTimeout(() => {
            if (!submenuLinks.matches(":hover")) hideSubmenu();
        }, 100);
    });

    submenuLinks.addEventListener("mouseleave", () => {
        setTimeout(() => {
            if (!trigger.matches(":hover")) hideSubmenu();
        }, 100);
    });
});