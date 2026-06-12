(function () {
    "use strict";

    const STORAGE_KEY = "grillkit_setup_wizard";
    const SUBMITTED_KEY = "grillkit_setup_wizard_submitted";

    const SESSION_MODE_LABELS = {
        theory_only: "Theory only",
        coding_only: "Coding only",
        theory_then_coding: "Theory, then coding",
        coding_then_theory: "Coding, then theory",
    };

    const form = document.getElementById("setup-form");
    const wizard = document.getElementById("setup-wizard");
    if (!form || !wizard) {
        return;
    }

    const selectionInput = document.getElementById("selection_json");
    const submitBtn = document.getElementById("setup-submit");
    const nextBtn = document.getElementById("setup-wizard-next");
    const backBtn = document.getElementById("setup-wizard-back");
    const wizardNav = document.querySelector(".setup-wizard-nav");
    const stepper = document.getElementById("setup-stepper");
    const reviewSummary = document.getElementById("setup-review-summary");
    const questionCountInput = document.getElementById("question_count");
    const questionCountHint = document.getElementById("question-count-hint");
    const codingCountInput = document.getElementById("coding_question_count");
    const codingCountHint = document.getElementById("coding-count-hint");
    const timerCheckbox = document.getElementById("enable_question_timer");
    const timerMinutesGroup = document.getElementById("question-timer-minutes-group");
    const codingTimerCheckbox = document.getElementById("enable_coding_timer");
    const codingTimerMinutesGroup = document.getElementById("coding-timer-minutes-group");

    const localeLabel = wizard.dataset.localeLabel || "";
    const initialStep = wizard.dataset.initialStep || "mode";
    const hasServerError = wizard.dataset.hasError === "true";

    let currentStepId = "mode";

    function formatTopic(slug) {
        return slug.charAt(0).toUpperCase() + slug.slice(1).replace(/-/g, " ");
    }

    function formatLevel(level) {
        return level.charAt(0).toUpperCase() + level.slice(1);
    }

    function selectedSessionMode() {
        const checked = document.querySelector(".session-mode-radio:checked");
        return checked ? checked.value : "theory_only";
    }

    function branchEnabled(mode, branch) {
        if (mode === "theory_only") {
            return branch === "theory";
        }
        if (mode === "coding_only") {
            return branch === "coding";
        }
        return true;
    }

    function getStepSequence() {
        const mode = selectedSessionMode();
        const sections = [];
        if (mode === "theory_only") {
            sections.push("theory");
        } else if (mode === "coding_only") {
            sections.push("coding");
        } else if (mode === "theory_then_coding") {
            sections.push("theory", "coding");
        } else {
            sections.push("coding", "theory");
        }
        return ["mode", ...sections, "review"];
    }

    function stepLabel(stepId) {
        if (stepId === "mode") {
            return "Mode";
        }
        if (stepId === "theory") {
            return "Theory";
        }
        if (stepId === "coding") {
            return "Coding";
        }
        return "Review";
    }

    function selectedTheoryTopicCount() {
        let count = 0;
        document.querySelectorAll(".theory-track-block").forEach(function (block) {
            const enable = block.querySelector(".track-enable");
            if (enable && enable.checked) {
                block.querySelectorAll(".topic-checkbox:checked").forEach(function () {
                    count += 1;
                });
            }
        });
        return count;
    }

    function selectedCodingTopicCount() {
        let count = 0;
        document.querySelectorAll(".coding-track-block").forEach(function (block) {
            const enable = block.querySelector(".coding-track-enable");
            if (enable && enable.checked) {
                block.querySelectorAll(".coding-topic-checkbox:checked").forEach(function () {
                    count += 1;
                });
            }
        });
        return count;
    }

    function syncTheoryCountMin() {
        const topics = selectedTheoryTopicCount();
        const minVal = Math.max(1, topics);
        questionCountInput.min = String(minVal);
        if (Number(questionCountInput.value) < minVal) {
            questionCountInput.value = String(minVal);
        }
        questionCountHint.textContent =
            "How many questions in this session (1–20). Must be at least "
            + minVal + " (one per selected topic).";
    }

    function syncCodingCountMin() {
        const topics = selectedCodingTopicCount();
        const minVal = Math.max(1, topics);
        codingCountInput.min = String(minVal);
        if (Number(codingCountInput.value) < minVal) {
            codingCountInput.value = String(minVal);
        }
        codingCountHint.textContent =
            "How many coding tasks in this session (1–20). Must be at least "
            + minVal + " (one per selected topic).";
    }

    function buildTheorySources() {
        const sources = [];
        document.querySelectorAll(".theory-track-block").forEach(function (block) {
            const track = block.dataset.track;
            const enabled = block.querySelector(".track-enable");
            if (!enabled || !enabled.checked) {
                return;
            }
            const levelSelect = block.querySelector(".track-level");
            const level = levelSelect ? levelSelect.value : "";
            const categories = [];
            block.querySelectorAll(".topic-checkbox:checked").forEach(function (cb) {
                categories.push(cb.value);
            });
            if (categories.length > 0) {
                sources.push({ track: track, level: level, categories: categories });
            }
        });
        return sources;
    }

    function buildCodingSources() {
        const sources = [];
        document.querySelectorAll(".coding-track-block").forEach(function (block) {
            const track = block.dataset.track;
            const enabled = block.querySelector(".coding-track-enable");
            if (!enabled || !enabled.checked) {
                return;
            }
            const levelSelect = block.querySelector(".coding-track-level");
            const level = levelSelect ? levelSelect.value : "";
            const categories = [];
            block.querySelectorAll(".coding-topic-checkbox:checked").forEach(function (cb) {
                categories.push(cb.value);
            });
            if (categories.length > 0) {
                sources.push({ track: track, level: level, categories: categories });
            }
        });
        return sources;
    }

    function buildSelection() {
        const sessionMode = selectedSessionMode();
        const theorySources = buildTheorySources();
        const codingSources = buildCodingSources();
        const theoryCount = Number(questionCountInput.value);
        const codingCount = Number(codingCountInput.value);
        const theoryTimerSeconds = timerCheckbox && timerCheckbox.checked
            ? Math.max(1, Number(document.getElementById("question_time_minutes").value)) * 60
            : null;
        const codingTimerSeconds = codingTimerCheckbox && codingTimerCheckbox.checked
            ? Math.max(1, Number(document.getElementById("coding_time_minutes").value)) * 60
            : null;
        const theoryEnabled = branchEnabled(sessionMode, "theory");
        const codingEnabled = branchEnabled(sessionMode, "coding");
        return {
            version: 2,
            session_mode: sessionMode,
            theory: {
                enabled: theoryEnabled,
                question_count: theoryEnabled ? theoryCount : 0,
                task_time_limit_seconds: theoryEnabled ? theoryTimerSeconds : null,
                sources: theoryEnabled ? theorySources : [],
            },
            coding: {
                enabled: codingEnabled,
                question_count: codingEnabled ? codingCount : 0,
                task_time_limit_seconds: codingEnabled ? codingTimerSeconds : null,
                sources: codingEnabled ? codingSources : [],
            },
        };
    }

    function theoryValid(selection) {
        if (!selection.theory.enabled) {
            return true;
        }
        const topics = selectedTheoryTopicCount();
        if (topics === 0 || selection.theory.sources.length === 0) {
            return false;
        }
        const count = Number(questionCountInput.value);
        return count >= topics && count >= 1 && count <= 20;
    }

    function codingValid(selection) {
        if (!selection.coding.enabled) {
            return true;
        }
        const topics = selectedCodingTopicCount();
        if (topics === 0 || selection.coding.sources.length === 0) {
            return false;
        }
        const count = Number(codingCountInput.value);
        return count >= topics && count >= 1 && count <= 20;
    }

    function validateStep(stepId) {
        if (stepId === "mode") {
            return Boolean(document.querySelector(".session-mode-radio:checked"));
        }
        const selection = buildSelection();
        if (stepId === "theory") {
            return theoryValid(selection);
        }
        if (stepId === "coding") {
            return codingValid(selection);
        }
        return theoryValid(selection) && codingValid(selection);
    }

    function syncTimerFields() {
        if (!timerCheckbox || !timerMinutesGroup) {
            return;
        }
        timerMinutesGroup.hidden = !timerCheckbox.checked;
    }

    function syncCodingTimerFields() {
        if (!codingTimerCheckbox || !codingTimerMinutesGroup) {
            return;
        }
        codingTimerMinutesGroup.hidden = !codingTimerCheckbox.checked;
    }

    function renderStepper() {
        const sequence = getStepSequence();
        stepper.innerHTML = "";
        sequence.forEach(function (stepId, index) {
            const item = document.createElement("li");
            item.className = "setup-wizard-stepper-item";
            item.dataset.step = stepId;
            const sequenceIndex = sequence.indexOf(currentStepId);
            if (stepId === currentStepId) {
                item.classList.add("setup-wizard-stepper-item-active");
            } else if (index < sequenceIndex) {
                item.classList.add("setup-wizard-stepper-item-complete");
            }
            const marker = document.createElement("span");
            marker.className = "setup-wizard-stepper-marker";
            marker.textContent = String(index + 1);
            const label = document.createElement("span");
            label.className = "setup-wizard-stepper-label";
            label.textContent = stepLabel(stepId);
            item.appendChild(marker);
            item.appendChild(label);
            stepper.appendChild(item);
        });
    }

    function showStep(stepId) {
        const sequence = getStepSequence();
        if (sequence.indexOf(stepId) === -1) {
            stepId = sequence[0];
        }
        currentStepId = stepId;
        document.querySelectorAll(".setup-wizard-step").forEach(function (panel) {
            panel.hidden = panel.dataset.wizardStep !== stepId;
        });
        renderStepper();
        updateNavButtons();
        if (stepId === "review") {
            renderReviewSummary();
        }
        saveWizardState();
    }

    function updateNavButtons() {
        const sequence = getStepSequence();
        const index = sequence.indexOf(currentStepId);
        backBtn.hidden = index <= 0;
        const onReview = currentStepId === "review";
        if (wizardNav) {
            wizardNav.classList.toggle("setup-wizard-nav-review", onReview);
        }
        nextBtn.hidden = onReview;
        submitBtn.hidden = !onReview;
        if (!onReview) {
            nextBtn.disabled = !validateStep(currentStepId);
        } else {
            submitBtn.disabled = !validateStep("review");
        }
    }

    function formatTimer(seconds) {
        if (seconds === null || seconds === undefined) {
            return "Disabled";
        }
        const minutes = Math.round(seconds / 60);
        return minutes + " min per round";
    }

    function renderSectionSources(sources) {
        if (!sources.length) {
            return "<p class=\"setup-review-empty\">No topics selected.</p>";
        }
        const items = sources.map(function (source) {
            const topics = source.categories.map(formatTopic).join(", ");
            return "<li><strong>" + formatTopic(source.track) + "</strong> ("
                + formatLevel(source.level) + "): " + topics + "</li>";
        });
        return "<ul class=\"selection-sources-list\">" + items.join("") + "</ul>";
    }

    function renderReviewCard(stepId, title, bodyHtml, editable) {
        const editButton = editable
            ? "<button type=\"button\" class=\"btn btn-outline btn-sm setup-review-edit\""
                + " data-edit-step=\"" + stepId + "\">Edit</button>"
            : "";
        return "<div class=\"setup-review-card\">"
            + "<div class=\"setup-review-card-header\">"
            + "<h3 class=\"setup-review-card-title\">" + title + "</h3>"
            + editButton
            + "</div>"
            + "<div class=\"setup-review-card-body\">" + bodyHtml + "</div>"
            + "</div>";
    }

    function renderReviewSummary() {
        const selection = buildSelection();
        const mode = selection.session_mode;
        let html = renderReviewCard(
            "mode",
            "Session mode",
            "<p>" + (SESSION_MODE_LABELS[mode] || mode) + "</p>",
            true
        );
        if (selection.theory.enabled) {
            html += renderReviewCard(
                "theory",
                "Theory",
                "<p><strong>Questions:</strong> " + selection.theory.question_count + "</p>"
                + "<p><strong>Timer:</strong> "
                + formatTimer(selection.theory.task_time_limit_seconds) + "</p>"
                + "<p><strong>Topics:</strong></p>"
                + renderSectionSources(selection.theory.sources),
                true
            );
        }
        if (selection.coding.enabled) {
            html += renderReviewCard(
                "coding",
                "Coding",
                "<p><strong>Tasks:</strong> " + selection.coding.question_count + "</p>"
                + "<p><strong>Timer:</strong> "
                + formatTimer(selection.coding.task_time_limit_seconds) + "</p>"
                + "<p><strong>Topics:</strong></p>"
                + renderSectionSources(selection.coding.sources),
                true
            );
        }
        html += renderReviewCard(
            "mode",
            "Interview language",
            "<p>" + localeLabel + "</p>"
            + "<p class=\"form-hint\">Change in <a href=\"/config\">Configuration</a>.</p>",
            false
        );
        reviewSummary.innerHTML = html;
        reviewSummary.querySelectorAll(".setup-review-edit").forEach(function (button) {
            button.addEventListener("click", function () {
                showStep(button.dataset.editStep);
            });
        });
        submitBtn.disabled = !validateStep("review");
    }

    function goNext() {
        const sequence = getStepSequence();
        const index = sequence.indexOf(currentStepId);
        if (index === -1 || index >= sequence.length - 1) {
            return;
        }
        if (!validateStep(currentStepId)) {
            return;
        }
        showStep(sequence[index + 1]);
    }

    function goBack() {
        const sequence = getStepSequence();
        const index = sequence.indexOf(currentStepId);
        if (index <= 0) {
            return;
        }
        showStep(sequence[index - 1]);
    }

    function collectBranchState(prefix, enableClass, levelClass, topicClass) {
        const tracks = {};
        document.querySelectorAll("." + prefix + "-track-block").forEach(function (block) {
            const track = block.dataset.track;
            const enable = block.querySelector("." + enableClass);
            const levelSelect = block.querySelector("." + levelClass);
            const categories = [];
            block.querySelectorAll("." + topicClass + ":checked").forEach(function (cb) {
                categories.push(cb.value);
            });
            tracks[track] = {
                enabled: Boolean(enable && enable.checked),
                level: levelSelect ? levelSelect.value : "",
                categories: categories,
            };
        });
        return tracks;
    }

    function saveWizardState() {
        const state = {
            sessionMode: selectedSessionMode(),
            theoryTracks: collectBranchState("theory", "track-enable", "track-level", "topic-checkbox"),
            codingTracks: collectBranchState(
                "coding",
                "coding-track-enable",
                "coding-track-level",
                "coding-topic-checkbox"
            ),
            questionCount: questionCountInput.value,
            codingQuestionCount: codingCountInput.value,
            theoryTimerEnabled: Boolean(timerCheckbox && timerCheckbox.checked),
            theoryTimerMinutes: document.getElementById("question_time_minutes").value,
            codingTimerEnabled: Boolean(codingTimerCheckbox && codingTimerCheckbox.checked),
            codingTimerMinutes: document.getElementById("coding_time_minutes").value,
            currentStepId: currentStepId,
        };
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (_error) {
            /* ignore quota errors */
        }
    }

    function clearWizardState() {
        try {
            sessionStorage.removeItem(STORAGE_KEY);
        } catch (_error) {
            /* ignore quota errors */
        }
    }

    function markWizardSubmitted() {
        try {
            sessionStorage.setItem(SUBMITTED_KEY, "1");
        } catch (_error) {
            /* ignore quota errors */
        }
    }

    function clearWizardSubmitted() {
        try {
            sessionStorage.removeItem(SUBMITTED_KEY);
        } catch (_error) {
            /* ignore quota errors */
        }
    }

    function wasWizardSubmitted() {
        try {
            return sessionStorage.getItem(SUBMITTED_KEY) === "1";
        } catch (_error) {
            return false;
        }
    }

    async function restoreBranchState(prefix, tracks, enableClass, levelClass, topicClass, loadTopics) {
        for (const block of document.querySelectorAll("." + prefix + "-track-block")) {
            const track = block.dataset.track;
            const saved = tracks[track];
            if (!saved) {
                continue;
            }
            const enable = block.querySelector("." + enableClass);
            const body = block.querySelector(".setup-track-body");
            const levelSelect = block.querySelector("." + levelClass);
            if (enable) {
                enable.checked = saved.enabled;
            }
            if (body) {
                body.hidden = !saved.enabled;
            }
            if (levelSelect && saved.level) {
                levelSelect.value = saved.level;
            }
            if (saved.enabled && typeof loadTopics === "function") {
                await loadTopics(block);
            }
            const wanted = new Set(saved.categories || []);
            block.querySelectorAll("." + topicClass).forEach(function (cb) {
                cb.checked = wanted.has(cb.value);
            });
        }
    }

    async function restoreWizardState() {
        let raw;
        try {
            raw = sessionStorage.getItem(STORAGE_KEY);
        } catch (_error) {
            return false;
        }
        if (!raw) {
            return false;
        }
        let state;
        try {
            state = JSON.parse(raw);
        } catch (_error) {
            return false;
        }
        const modeRadio = document.querySelector(
            ".session-mode-radio[value=\"" + state.sessionMode + "\"]"
        );
        if (modeRadio && !modeRadio.disabled) {
            modeRadio.checked = true;
        }
        await restoreBranchState(
            "theory",
            state.theoryTracks || {},
            "track-enable",
            "track-level",
            "topic-checkbox",
            loadTheoryTopics
        );
        await restoreBranchState(
            "coding",
            state.codingTracks || {},
            "coding-track-enable",
            "coding-track-level",
            "coding-topic-checkbox",
            loadCodingTopics
        );
        if (state.questionCount) {
            questionCountInput.value = state.questionCount;
        }
        if (state.codingQuestionCount) {
            codingCountInput.value = state.codingQuestionCount;
        }
        if (timerCheckbox) {
            timerCheckbox.checked = Boolean(state.theoryTimerEnabled);
        }
        if (state.theoryTimerMinutes) {
            document.getElementById("question_time_minutes").value = state.theoryTimerMinutes;
        }
        if (codingTimerCheckbox) {
            codingTimerCheckbox.checked = Boolean(state.codingTimerEnabled);
        }
        if (state.codingTimerMinutes) {
            document.getElementById("coding_time_minutes").value = state.codingTimerMinutes;
        }
        syncTimerFields();
        syncCodingTimerFields();
        syncTheoryCountMin();
        syncCodingCountMin();
        return true;
    }

    async function loadTheoryTopics(block) {
        const track = block.dataset.track;
        const levelSelect = block.querySelector(".track-level");
        const topicList = block.querySelector(".setup-topic-list");
        if (!levelSelect || !topicList) {
            return;
        }
        const level = levelSelect.value;
        const url = "/setup/options?track=" + encodeURIComponent(track)
            + "&level=" + encodeURIComponent(level);
        const response = await fetch(url);
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        const categories = data.categories || [];
        const checked = new Set();
        topicList.querySelectorAll(".topic-checkbox:checked").forEach(function (cb) {
            checked.add(cb.value);
        });
        topicList.innerHTML = "";
        categories.forEach(function (cat) {
            const label = document.createElement("label");
            label.className = "setup-topic-item";
            const input = document.createElement("input");
            input.type = "checkbox";
            input.className = "topic-checkbox";
            input.value = cat;
            input.dataset.track = track;
            if (checked.has(cat)) {
                input.checked = true;
            }
            input.addEventListener("change", onFormChange);
            label.appendChild(input);
            label.appendChild(document.createTextNode(" " + formatTopic(cat)));
            topicList.appendChild(label);
        });
    }

    async function loadCodingTopics(block) {
        const track = block.dataset.track;
        const levelSelect = block.querySelector(".coding-track-level");
        const topicList = block.querySelector(".coding-topic-list");
        if (!levelSelect || !topicList) {
            return;
        }
        const level = levelSelect.value;
        const url = "/setup/coding-options?track=" + encodeURIComponent(track)
            + "&level=" + encodeURIComponent(level);
        const response = await fetch(url);
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        const categories = data.categories || [];
        const checked = new Set();
        topicList.querySelectorAll(".coding-topic-checkbox:checked").forEach(function (cb) {
            checked.add(cb.value);
        });
        topicList.innerHTML = "";
        categories.forEach(function (cat) {
            const label = document.createElement("label");
            label.className = "setup-topic-item";
            const input = document.createElement("input");
            input.type = "checkbox";
            input.className = "coding-topic-checkbox";
            input.value = cat;
            input.dataset.track = track;
            if (checked.has(cat)) {
                input.checked = true;
            }
            input.addEventListener("change", onFormChange);
            label.appendChild(input);
            label.appendChild(document.createTextNode(" " + formatTopic(cat)));
            topicList.appendChild(label);
        });
    }

    function onFormChange() {
        syncTheoryCountMin();
        syncCodingCountMin();
        updateNavButtons();
        if (currentStepId === "review") {
            renderReviewSummary();
        } else {
            saveWizardState();
        }
    }

    function bindTrackBlocks() {
        document.querySelectorAll(".theory-track-block").forEach(function (block) {
            const enable = block.querySelector(".track-enable");
            const body = block.querySelector(".setup-track-body");
            const levelSelect = block.querySelector(".track-level");
            if (enable && body) {
                enable.addEventListener("change", function () {
                    body.hidden = !enable.checked;
                    onFormChange();
                });
            }
            if (levelSelect) {
                levelSelect.addEventListener("change", function () {
                    loadTheoryTopics(block).then(onFormChange);
                });
            }
            block.querySelectorAll(".topic-checkbox").forEach(function (cb) {
                cb.addEventListener("change", onFormChange);
            });
        });

        document.querySelectorAll(".coding-track-block").forEach(function (block) {
            const enable = block.querySelector(".coding-track-enable");
            const body = block.querySelector(".setup-track-body");
            const levelSelect = block.querySelector(".coding-track-level");
            if (enable && body) {
                enable.addEventListener("change", function () {
                    body.hidden = !enable.checked;
                    onFormChange();
                });
            }
            if (levelSelect) {
                levelSelect.addEventListener("change", function () {
                    loadCodingTopics(block).then(onFormChange);
                });
            }
            block.querySelectorAll(".coding-topic-checkbox").forEach(function (cb) {
                cb.addEventListener("change", onFormChange);
            });
        });

        document.querySelectorAll(".session-mode-radio").forEach(function (radio) {
            radio.addEventListener("change", function () {
                const sequence = getStepSequence();
                if (sequence.indexOf(currentStepId) === -1) {
                    showStep("mode");
                } else {
                    renderStepper();
                    updateNavButtons();
                }
                onFormChange();
            });
        });
    }

    function bindControls() {
        questionCountInput.addEventListener("input", onFormChange);
        codingCountInput.addEventListener("input", onFormChange);
        if (timerCheckbox) {
            timerCheckbox.addEventListener("change", function () {
                syncTimerFields();
                onFormChange();
            });
        }
        if (codingTimerCheckbox) {
            codingTimerCheckbox.addEventListener("change", function () {
                syncCodingTimerFields();
                onFormChange();
            });
        }
        document.getElementById("question_time_minutes").addEventListener("input", onFormChange);
        document.getElementById("coding_time_minutes").addEventListener("input", onFormChange);

        nextBtn.addEventListener("click", goNext);
        backBtn.addEventListener("click", goBack);

        form.addEventListener("submit", function (event) {
            const selection = buildSelection();
            if (!theoryValid(selection) || !codingValid(selection)) {
                event.preventDefault();
                showStep("review");
                renderReviewSummary();
                return;
            }
            selectionInput.value = JSON.stringify(selection);
            saveWizardState();
            markWizardSubmitted();
        });
    }

    async function init() {
        bindTrackBlocks();
        bindControls();
        syncTimerFields();
        syncCodingTimerFields();

        let restored = false;
        if (hasServerError) {
            clearWizardSubmitted();
            restored = await restoreWizardState();
        } else if (wasWizardSubmitted()) {
            clearWizardSubmitted();
            clearWizardState();
        } else {
            restored = await restoreWizardState();
        }
        let startStep = initialStep;
        if (restored && hasServerError) {
            startStep = "review";
        } else if (restored) {
            try {
                const state = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
                if (state.currentStepId && getStepSequence().includes(state.currentStepId)) {
                    startStep = state.currentStepId;
                }
            } catch (_error) {
                /* use initialStep */
            }
        }
        showStep(startStep);
        onFormChange();
    }

    init();
})();
