(function () {
    const panel = document.getElementById("question-voice-panel");
    if (!panel) {
        return;
    }
    panel.classList.add("model-download-panel");
    panel.setAttribute("data-status-element-id", "speech-tts-status");
    panel.setAttribute("data-status-url", "/speech/tts/status");
    panel.setAttribute("data-download-button-id", "question-voice-download-btn");
})();
