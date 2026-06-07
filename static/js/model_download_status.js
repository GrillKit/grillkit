(function () {
    function artifactUrl(baseUrl, panel) {
        const queryFn = panel._artifactQueryString;
        if (typeof queryFn !== "function") {
            return baseUrl;
        }
        const query = queryFn();
        if (!query) {
            return baseUrl;
        }
        const separator = baseUrl.indexOf("?") >= 0 ? "&" : "?";
        return baseUrl + separator + query;
    }

    function initModelDownloadPanel(panel) {
        const statusElementId = panel.getAttribute("data-status-element-id");
        const statusUrl = panel.getAttribute("data-status-url");
        if (!statusElementId || !statusUrl) {
            return;
        }

        const downloadButtonId = panel.getAttribute("data-download-button-id") || "";
        let pollTimer = null;

        function bindDownloadButtons(root) {
            if (!downloadButtonId) {
                return;
            }
            root.querySelectorAll("#" + downloadButtonId).forEach(function (button) {
                button.addEventListener("click", function () {
                    const baseUrl = button.getAttribute("data-download-url");
                    if (!baseUrl) {
                        return;
                    }
                    button.disabled = true;
                    fetch(artifactUrl(baseUrl, panel), {
                        method: "POST",
                        headers: { Accept: "text/html" },
                    })
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

        function replaceStatusHtml(html) {
            const current = panel.querySelector("#" + statusElementId);
            if (current) {
                current.outerHTML = html;
            }
            bindDownloadButtons(panel);
        }

        function fetchStatusHtml() {
            return fetch(artifactUrl(statusUrl, panel), {
                headers: { Accept: "text/html" },
            }).then(function (response) {
                return response.text();
            });
        }

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
                fetchStatusHtml()
                    .then(function (html) {
                        replaceStatusHtml(html);
                        const updated = panel.querySelector("#" + statusElementId);
                        if (!updated || updated.getAttribute("data-state") !== "downloading") {
                            clearInterval(pollTimer);
                            pollTimer = null;
                        }
                    });
            }, 1500);
        }

        panel._refreshArtifactStatus = function () {
            if (pollTimer) {
                clearInterval(pollTimer);
                pollTimer = null;
            }
            fetchStatusHtml()
                .then(function (html) {
                    replaceStatusHtml(html);
                    schedulePoll();
                })
                .catch(function () {
                    /* keep current status on transient errors */
                });
        };

        bindDownloadButtons(panel);
        schedulePoll();
    }

    document.querySelectorAll(".model-download-panel").forEach(initModelDownloadPanel);
})();
