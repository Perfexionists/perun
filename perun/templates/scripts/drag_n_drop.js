let panelDrag = null;

function getClosestParent(el, cssSelector) {
    return el?.closest?.(cssSelector) ?? null;
}

function findPanelAtPoint(clientX, clientY) {
    return getClosestParent(document.elementFromPoint(clientX, clientY), ".grid-svg-container");
}

function swapPanelElements(panelA, panelB) {
    if (!panelA || !panelB || panelA === panelB) {
        return;
    }
    const parentA = panelA.parentNode;
    const parentB = panelB.parentNode;
    const marker = document.createComment("swap");
    parentA.insertBefore(marker, panelA);
    parentB.insertBefore(panelA, panelB);
    parentA.insertBefore(panelB, marker);
    parentA.removeChild(marker);
}

function clearDropTargetHighlight() {
    for (const panel of document.querySelectorAll(".grid-svg-container.panel-drop-target")) {
        panel.classList.remove("panel-drop-target");
    }
}

function updateDropTargetHighlight(dropPanel) {
    clearDropTargetHighlight();
    if (dropPanel && panelDrag && dropPanel !== panelDrag.sourcePanel) {
        dropPanel.classList.add("panel-drop-target");
    }
}

function endPanelDrag(doSwap) {
    if (!panelDrag) {
        return;
    }
    const { sourcePanel, dropPanel } = panelDrag;
    sourcePanel.classList.remove("panel-dragging");
    clearDropTargetHighlight();
    getClosestParent(sourcePanel, ".section").classList.remove("panel-drag-active");
    if (doSwap && dropPanel) {
        swapPanelElements(sourcePanel, dropPanel);
    }
    panelDrag = null;
}

function onPanelDragHandlePointerDown(e) {
    if (e.button !== 0) {
        return;
    }
    const sourcePanel = getClosestParent(e.currentTarget, ".grid-svg-container");
    if (!sourcePanel) {
        return;
    }

    e.preventDefault();

    const handle = e.currentTarget;
    const pointerId = e.pointerId;
    handle.setPointerCapture(pointerId);

    panelDrag = { sourcePanel, dropPanel: null };
    sourcePanel.classList.add("panel-dragging");
    getClosestParent(sourcePanel, ".section").classList.add("panel-drag-active");

    function onMove(ev) {
        if (ev.pointerId !== pointerId) {
            return;
        }
        panelDrag.dropPanel = findPanelAtPoint(ev.clientX, ev.clientY);
        updateDropTargetHighlight(panelDrag.dropPanel);
    }

    function onEnd(ev) {
        if (ev.pointerId !== pointerId) {
            return;
        }
        handle.releasePointerCapture(pointerId);
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onEnd);
        handle.removeEventListener("pointercancel", onEnd);

        const dropPanel = findPanelAtPoint(ev.clientX, ev.clientY);
        panelDrag.dropPanel = dropPanel;
        const doSwap = dropPanel && dropPanel !== sourcePanel;
        endPanelDrag(doSwap);
    }

    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onEnd);
    handle.addEventListener("pointercancel", onEnd);
}

function initPanelDragDrop() {
    for (const handle of document.querySelectorAll(".panel-drag-handle")) {
        handle.addEventListener("pointerdown", onPanelDragHandlePointerDown);
    }
}

window.addEventListener("DOMContentLoaded", initPanelDragDrop);