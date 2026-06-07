(function () {
    const panel = document.getElementById("question-voice-panel");
    const form = document.getElementById("config-form");
    if (!panel || !form) {
        return;
    }

    panel.classList.add("model-download-panel");
    panel.setAttribute("data-status-element-id", "speech-tts-status");
    panel.setAttribute("data-status-url", "/speech/tts/status");
    panel.setAttribute("data-download-button-id", "question-voice-download-btn");

    function selectedLocale() {
        const locale = form.querySelector("#locale");
        return locale ? locale.value : "en";
    }

    panel._artifactQueryString = function () {
        return "locale=" + encodeURIComponent(selectedLocale());
    };

    function updateSubtitle() {
        const subtitle = panel.querySelector(".card-subtitle");
        const localeSelect = form.querySelector("#locale");
        if (!subtitle || !localeSelect || localeSelect.selectedIndex < 0) {
            return;
        }
        const localeLabel = localeSelect.options[localeSelect.selectedIndex].text;
        subtitle.textContent =
            "Offline Piper voice for reading interview questions aloud in " +
            localeLabel;
    }

    function onFormTargetChange() {
        updateSubtitle();
        if (typeof panel._refreshArtifactStatus === "function") {
            panel._refreshArtifactStatus();
        }
    }

    const localeSelect = form.querySelector("#locale");
    if (localeSelect) {
        localeSelect.addEventListener("change", onFormTargetChange);
    }
})();
