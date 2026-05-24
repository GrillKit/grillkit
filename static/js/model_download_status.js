(function () {
    function initModelDownloadPanel(panel) {
        const statusElementId = panel.getAttribute("data-status-element-id");
        const statusUrl = panel.getAttribute("data-status-url");
        if (!statusElementId || !statusUrl) {
            return;
        }

        const downloadButtonId = panel.getAttribute("data-download-button-id") || "";

        function bindDownloadButtons(root) {
            if (!downloadButtonId) {
                return;
            }
            root.querySelectorAll("#" + downloadButtonId).forEach(function (button) {
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
                            const statusHost = panel.querySelector("#" + statusElementId);
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
            const statusEl = panel.querySelector("#" + statusElementId);
            if (!statusEl || statusEl.getAttribute("data-state") !== "downloading") {
                return;
            }
            pollTimer = setInterval(function () {
                fetch(statusUrl, { headers: { Accept: "text/html" } })
                    .then(function (response) {
                        return response.text();
                    })
                    .then(function (html) {
                        const current = panel.querySelector("#" + statusElementId);
                        if (current) {
                            current.outerHTML = html;
                        }
                        bindDownloadButtons(panel);
                        const updated = panel.querySelector("#" + statusElementId);
                        if (!updated || updated.getAttribute("data-state") !== "downloading") {
                            clearInterval(pollTimer);
                            pollTimer = null;
                        }
                    });
            }, 1500);
        }

        bindDownloadButtons(panel);
        schedulePoll();
    }

    document.querySelectorAll(".model-download-panel").forEach(initModelDownloadPanel);
})();
