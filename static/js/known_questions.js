(function () {
    "use strict";

    async function fetchKnown() {
        const response = await fetch("/known-questions");
        if (!response.ok) {
            throw new Error("Failed to load known questions");
        }
        return response.json();
    }

    async function markKnown(branch, itemId) {
        const response = await fetch("/known-questions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ branch: branch, item_id: itemId }),
        });
        if (!response.ok) {
            throw new Error("Failed to mark question as known");
        }
        return response.json();
    }

    async function unmarkKnown(branch, itemId) {
        const response = await fetch("/known-questions", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ branch: branch, item_id: itemId }),
        });
        if (!response.ok) {
            throw new Error("Failed to unmark question");
        }
        return response.json();
    }

    function isKnown(known, branch, itemId) {
        const ids = known[branch] || [];
        return ids.indexOf(itemId) !== -1;
    }

    function markLabel(button) {
        return button.classList.contains("known-question-toggle--interview")
            ? "I know this"
            : "Mark as known";
    }

    function updateButton(button, known) {
        const branch = button.dataset.branch;
        const itemId = button.dataset.itemId;
        const marked = isKnown(known, branch, itemId);
        button.textContent = marked ? "Unmark" : markLabel(button);
        button.classList.toggle("btn-primary", marked);
        button.classList.toggle("btn-outline", !marked);
        button.dataset.known = marked ? "true" : "false";
    }

    function bindKnownToggleButton(button, known) {
        if (!button || button.dataset.knownBound === "true") {
            return;
        }
        const branch = button.dataset.branch;
        if (!branch || !button.dataset.itemId) {
            return;
        }
        if (known) {
            updateButton(button, known);
        }
        button.dataset.knownBound = "true";
        button.addEventListener("click", function () {
            const itemId = button.dataset.itemId;
            const action = button.dataset.known === "true"
                ? unmarkKnown(branch, itemId)
                : markKnown(branch, itemId);
            action
                .then(function (updated) {
                    updateButton(button, updated);
                })
                .catch(function () {
                    window.alert("Could not update known status. Try again.");
                });
        });
    }

    function bindKnownToggleButtons(scope, branch, known) {
        const root = scope || document;
        root.querySelectorAll(".known-question-toggle").forEach(function (button) {
            if (branch && button.dataset.branch !== branch) {
                return;
            }
            bindKnownToggleButton(button, known);
        });
    }

    function initKnownToggleButtons(branch) {
        const buttons = document.querySelectorAll(".known-question-toggle");
        if (!buttons.length) {
            return;
        }
        fetchKnown()
            .then(function (known) {
                bindKnownToggleButtons(document, branch, known);
            })
            .catch(function () {
                buttons.forEach(function (button) {
                    if (!branch || button.dataset.branch === branch) {
                        button.disabled = true;
                    }
                });
            });
    }

    function knownToggleButtonHtml(branch, itemId, interviewMode) {
        const classes = "btn btn-outline btn-sm known-question-toggle"
            + (interviewMode ? " known-question-toggle--interview" : "");
        const label = interviewMode ? "I know this" : "Mark as known";
        return '<button type="button" class="' + classes + '" data-branch="'
            + branch + '" data-item-id="' + itemId + '">' + label + "</button>";
    }

    function bindKnownToggleIn(root) {
        fetchKnown()
            .then(function (known) {
                bindKnownToggleButtons(root, null, known);
            })
            .catch(function () {
                if (!root) {
                    return;
                }
                root.querySelectorAll(".known-question-toggle").forEach(function (button) {
                    button.disabled = true;
                });
            });
    }

    function updateCodingKnownItem(itemId, round) {
        const button = document.getElementById("coding-known-item-btn");
        if (!button) {
            return;
        }
        const roundNum = Number(round || 0);
        button.hidden = roundNum > 0;
        if (roundNum > 0) {
            return;
        }
        button.dataset.itemId = itemId;
        delete button.dataset.knownBound;
        fetchKnown()
            .then(function (known) {
                bindKnownToggleButton(button, known);
            })
            .catch(function () {
                button.disabled = true;
            });
    }

    function initManagePage() {
        document.querySelectorAll(".known-questions-unmark").forEach(function (button) {
            button.addEventListener("click", function () {
                const branch = button.dataset.branch;
                const itemId = button.dataset.itemId;
                unmarkKnown(branch, itemId)
                    .then(function () {
                        const item = button.closest(".known-questions-item");
                        if (item) {
                            item.remove();
                        }
                        const list = document.querySelector(
                            '.known-questions-list[data-branch="' + branch + '"]'
                        );
                        if (list && !list.querySelector(".known-questions-item")) {
                            const section = list.closest(".known-questions-section");
                            if (section) {
                                const empty = document.createElement("p");
                                empty.className = "known-questions-empty";
                                empty.textContent = branch === "theory"
                                    ? "No theory questions marked as known."
                                    : "No coding tasks marked as known.";
                                list.replaceWith(empty);
                            }
                        }
                    })
                    .catch(function () {
                        window.alert("Could not unmark question. Try again.");
                    });
            });
        });
    }

    window.KnownQuestions = {
        fetchKnown: fetchKnown,
        markKnown: markKnown,
        unmarkKnown: unmarkKnown,
        knownToggleButtonHtml: knownToggleButtonHtml,
        bindKnownToggleIn: bindKnownToggleIn,
        initReviewButtons: initKnownToggleButtons,
        initInterviewTheory: function () {
            initKnownToggleButtons("theory");
        },
        initInterviewCoding: function () {
            initKnownToggleButtons("coding");
        },
        updateCodingKnownItem: updateCodingKnownItem,
        initManagePage: initManagePage,
    };

    if (document.body.classList.contains("page-known-questions")) {
        initManagePage();
    }
})();
