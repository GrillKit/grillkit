(function () {
    const panel = document.getElementById("speech-model-panel");
    if (!panel) {
        return;
    }
    panel.classList.add("model-download-panel");
    panel.setAttribute("data-status-element-id", "speech-model-status");
    panel.setAttribute("data-status-url", "/speech/model/status");
    panel.setAttribute("data-download-button-id", "speech-model-download-btn");
})();
