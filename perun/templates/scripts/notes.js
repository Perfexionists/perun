const NOTE_SUFFIX = " -note-item";
const PIN_SUFFIX = " -pin-item";

const noteTitle = document.getElementById("note-popup-title");
const noteContentContainer = document.getElementById("note-popup-content");
const noteContent = document.getElementById("note-popup-content-textarea");
const popupContainer = document.getElementById("note-popup-container");
const popup = document.getElementById("note-popup");

const actionButtons = document.getElementById("note-popup-buttons-action");
const attentionButton = actionButtons.querySelector(".attention");
const approvedButton = actionButtons.querySelector(".approved");

const navigationButtons = document.getElementById("note-popup-buttons-navigation");
const saveButtons = navigationButtons.querySelectorAll(".save");

function openNotePopupAndFill(id) {
    const noteItem = document.getElementById(id + NOTE_SUFFIX);
    popup.dataset.currentId = id;

    const link = noteItem.querySelector(".note-link");
    const content = noteItem.querySelector(".note-input");

    noteTitle.textContent = link ? link.textContent : "UNKNOWN TITLE";
    noteContent.value = content ? content.textContent : "unknown content";

    if (noteItem.classList.contains("note-item--attention")) {
        switchStateToAttention();
    } else {
        switchStateToApproved();
    }

    switchButtonsState(false);
    popupContainer.style.display = "flex";
}

function closeNotePopupAndClear() {
    noteTitle.textContent = "Note title";
    noteContent.value = "Note content";

    popupContainer.style.display = "none";
}

function saveNotePopup() {
    const currentId = popup.dataset.currentId;
    const noteItem = document.getElementById(currentId + NOTE_SUFFIX);

    const textarea = noteItem.querySelector(".note-input");
    textarea.textContent = noteContent.value;

    noteItem.classList.remove("note-item--attention");
    noteItem.classList.remove("note-item--approved");
    noteItem.classList.add("note-item--" + popup.dataset.currentState);

    switchButtonsState(false);
}

function saveNotePopupAndClose() {
    saveNotePopup();
    closeNotePopupAndClear();
}

function deleteNotePopup() {
    const currentId = popup.dataset.currentId;
    const noteItem = document.getElementById(currentId + NOTE_SUFFIX);
    const pinItem = document.getElementById(currentId + PIN_SUFFIX);

    noteItem.remove();
    pinItem.classList.remove("pin-icon__pinned");

    closeNotePopupAndClear();
}

function switchStateToAttention() {
    approvedButton.classList.add("not-chosen");
    attentionButton.classList.remove("not-chosen");
    popup.dataset.currentState = "attention";

    noteContentContainer.classList.remove("approved");
    noteContentContainer.classList.add("attention");

    switchButtonsState(true);
}

function switchStateToApproved() {
    attentionButton.classList.add("not-chosen");
    approvedButton.classList.remove("not-chosen");
    popup.dataset.currentState = "approved";

    noteContentContainer.classList.remove("attention");
    noteContentContainer.classList.add("approved");

    switchButtonsState(true);
}

function switchButtonsState(toChanged) {
    if (toChanged) {
        saveButtons.forEach(btn => btn.classList.add("changed"))
    }
    else {
        saveButtons.forEach(btn => btn.classList.remove("changed"))
    }
}

noteContent.addEventListener('input', () => {
    switchButtonsState(true);
});

function exportNotes() {
        let docHTML = document.documentElement.outerHTML;
        let parser = new DOMParser();
        let doc = parser.parseFromString(docHTML, 'text/html');

        let rawTable = doc.getElementById('table-to-replace');
        let currentTable = doc.getElementById('table_wrapper');

        if (rawTable && currentTable) {
            let newTable = rawTable.cloneNode(true);
            newTable.id = 'table';

            currentTable.replaceWith(newTable);

            let updatedHTML = `<!DOCTYPE html>\n${doc.documentElement.outerHTML}`;

            let blob = new Blob([updatedHTML], { type: 'text/html' });

            let link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'report_with_notes.html';
            link.click();
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const notesList = document.getElementById("notes-list");

        function addNoteForSection(pin, sectionId) {
            const noteItem = document.createElement("div");
            noteItem.classList.add("note-item", "note-item--attention");
            noteItem.setAttribute("id", `${sectionId} -note-item`);

            noteItem.innerHTML = `
            <div style="display: flex; flex-direction: column">
                <b><a href="#${sectionId}" class="note-link">${sectionId}:</a></b>
                <div class="note-item--content">
                    <p class="note-input"></p>
                </div>
                <div style="display: flex; align-self: end; gap: 10px;">
                    <a href="#${sectionId}"><button class="tag-element tag-baseline note-shortcut-button">goto note</button></a>
                    <button class="tag-element tag-target note-shortcut-button" onclick="openNotePopupAndFill('${sectionId}')">open popup</button>
                </div>
            </div>`;

            notesList.appendChild(noteItem);
        }

        document.querySelectorAll(".pin-icon:not(.info-icon__header)").forEach(pin => {
            pin.onclick = () => {
                if (!pin.classList.contains("pin-icon__pinned")) {
                    addNoteForSection(pin, pin.dataset.section);
                    pin.classList.add("pin-icon__pinned");
                    pin.parentElement.setAttribute("id", pin.dataset.section.toString());
                }
                openNotePopupAndFill(pin.dataset.section)
            }
        });
    });