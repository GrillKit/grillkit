(function () {
    const panel = document.getElementById("speech-model-panel");
    if (!panel) {
        return;
    }

    const statusUrl = "/speech/model/status";

    function bindDownloadButtons(root) {
        root.querySelectorAll("#speech-model-download-btn").forEach(function (button) {
            button.addEventListener("click", function () {
                const url = button.getAttribute("data-download-url");
                if (!url) {
                    return;
                }
                button.disabled = true;
                fetch(url, { method: "POST", headers: { Accept: "text/html" } })
                    .then(function (response) {
                        return response.text();
                    })
                    .then(function (html) {
                        const statusHost = panel.querySelector("#speech-model-status");
                        if (statusHost && statusHost.parentElement) {
                            statusHost.outerHTML = html;
                        }
                        bindDownloadButtons(panel);
                        schedulePoll();
                    })
                    .catch(function () {
                        button.disabled = false;
                    });
            });
        });
    }

    let pollTimer = null;

    function schedulePoll() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        const statusEl = panel.querySelector("#speech-model-status");
        if (!statusEl || statusEl.getAttribute("data-state") !== "downloading") {
            return;
        }
        pollTimer = setInterval(function () {
            fetch(statusUrl, { headers: { Accept: "text/html" } })
                .then(function (response) {
                    return response.text();
                })
                .then(function (html) {
                    const current = panel.querySelector("#speech-model-status");
                    if (current) {
                        current.outerHTML = html;
                    }
                    bindDownloadButtons(panel);
                    const updated = panel.querySelector("#speech-model-status");
                    if (!updated || updated.getAttribute("data-state") !== "downloading") {
                        clearInterval(pollTimer);
                        pollTimer = null;
                    }
                });
        }, 1500);
    }

    bindDownloadButtons(panel);
    schedulePoll();
})();
