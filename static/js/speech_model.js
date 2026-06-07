(function () {
    const panel = document.getElementById("speech-model-panel");
    const form = document.getElementById("config-form");
    if (!panel || !form) {
        return;
    }

    panel.classList.add("model-download-panel");
    panel.setAttribute("data-status-element-id", "speech-model-status");
    panel.setAttribute("data-status-url", "/speech/model/status");
    panel.setAttribute("data-download-button-id", "speech-model-download-btn");

    function selectedSize() {
        const checked = form.querySelector('input[name="speech_model_size"]:checked');
        return checked ? checked.value : "small";
    }

    function selectedLocale() {
        const locale = form.querySelector("#locale");
        return locale ? locale.value : "en";
    }

    panel._artifactQueryString = function () {
        return (
            "size=" +
            encodeURIComponent(selectedSize()) +
            "&locale=" +
            encodeURIComponent(selectedLocale())
        );
    };

    function updateSubtitle() {
        const checked = form.querySelector('input[name="speech_model_size"]:checked');
        const subtitle = panel.querySelector(".card-subtitle");
        if (!checked || !subtitle) {
            return;
        }
        const option = checked.closest(".speech-model-size-option");
        const titleEl =
            option && option.querySelector(".speech-model-size-option-title");
        const localeSelect = form.querySelector("#locale");
        const localeLabel =
            localeSelect && localeSelect.selectedIndex >= 0
                ? localeSelect.options[localeSelect.selectedIndex].text
                : "";
        const displayName = titleEl ? titleEl.textContent.trim() : checked.value;
        subtitle.textContent =
            "Offline Whisper (" +
            displayName +
            ") — dictation in " +
            localeLabel;
    }

    function onFormTargetChange() {
        updateSubtitle();
        if (typeof panel._refreshArtifactStatus === "function") {
            panel._refreshArtifactStatus();
        }
    }

    form.querySelectorAll('input[name="speech_model_size"]').forEach(function (radio) {
        radio.addEventListener("change", onFormTargetChange);
    });
    const localeSelect = form.querySelector("#locale");
    if (localeSelect) {
        localeSelect.addEventListener("change", onFormTargetChange);
    }
})();
