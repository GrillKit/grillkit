(function () {
    const composer = document.getElementById("answer-section");
    if (!composer || composer.dataset.questionVoiceEnabled !== "true") {
        return;
    }

    const interviewId = composer.dataset.interviewId;
    if (!interviewId) {
        return;
    }

    const alertsHost = document.getElementById("interview-alerts");
    let prepareHint = null;
    let playButton = null;
    let audioElement = null;
    let loadToken = 0;

    function showPrepareHint() {
        if (!alertsHost || prepareHint) {
            return;
        }
        prepareHint = document.createElement("div");
        prepareHint.className = "alert alert-info question-voice-hint";
        prepareHint.id = "question-voice-prepare-hint";
        prepareHint.textContent = "Preparing question audio…";
        alertsHost.appendChild(prepareHint);
    }

    function clearPrepareHint() {
        if (prepareHint && prepareHint.parentElement) {
            prepareHint.remove();
        }
        prepareHint = null;
    }

    function showVoiceAlert(message, level) {
        if (!alertsHost) {
            return;
        }
        const alertDiv = document.createElement("div");
        alertDiv.className = "alert alert-" + (level || "warning");
        alertDiv.textContent = message;
        alertsHost.appendChild(alertDiv);
    }

    function ensurePlayButton(onClick) {
        if (playButton) {
            playButton.onclick = onClick;
            return;
        }
        const footer = composer.querySelector(".composer-footer");
        if (!footer) {
            return;
        }
        playButton = document.createElement("button");
        playButton.type = "button";
        playButton.className = "btn btn-secondary btn-question-voice";
        playButton.textContent = "Play question";
        playButton.setAttribute("aria-label", "Play question audio");
        playButton.hidden = true;
        playButton.addEventListener("click", onClick);
        footer.insertBefore(playButton, footer.firstChild);
    }

    function hidePlayButton() {
        if (playButton) {
            playButton.hidden = true;
        }
    }

    function showPlayButton() {
        if (playButton) {
            playButton.hidden = false;
        }
    }

    function disposeAudio() {
        if (audioElement) {
            audioElement.pause();
            audioElement.removeAttribute("src");
            audioElement.load();
            audioElement.remove();
            audioElement = null;
        }
    }

    function playQuestionAudio(answerId) {
        const token = ++loadToken;
        disposeAudio();
        hidePlayButton();
        showPrepareHint();

        let url = "/interview/" + encodeURIComponent(interviewId) + "/question-audio";
        if (answerId) {
            url += "?answer_id=" + encodeURIComponent(String(answerId));
        }

        fetch(url, { method: "GET" })
            .then(function (response) {
                if (!response.ok) {
                    return response
                        .json()
                        .then(function (body) {
                            let detail = response.statusText;
                            if (body && body.detail) {
                                detail =
                                    typeof body.detail === "string"
                                        ? body.detail
                                        : String(body.detail);
                            }
                            throw new Error(detail);
                        })
                        .catch(function (err) {
                            if (err instanceof Error && err.message) {
                                throw err;
                            }
                            throw new Error(
                                response.statusText || "Question audio failed"
                            );
                        });
                }
                return response.blob();
            })
            .then(function (blob) {
                if (token !== loadToken) {
                    return;
                }
                clearPrepareHint();
                const objectUrl = URL.createObjectURL(blob);
                audioElement = new Audio(objectUrl);
                audioElement.addEventListener("ended", function () {
                    URL.revokeObjectURL(objectUrl);
                });

                const tryAutoplay = function () {
                    const playPromise = audioElement.play();
                    if (!playPromise || typeof playPromise.then !== "function") {
                        return;
                    }
                    playPromise.then(function () {
                        hidePlayButton();
                    }).catch(function () {
                        ensurePlayButton(function () {
                            audioElement.play().catch(function () {
                                showVoiceAlert("Could not play question audio.", "warning");
                            });
                        });
                        showPlayButton();
                    });
                };

                ensurePlayButton(tryAutoplay);
                if (audioElement.readyState >= 2) {
                    tryAutoplay();
                } else {
                    audioElement.addEventListener("canplay", tryAutoplay, { once: true });
                }
                audioElement.load();
            })
            .catch(function (err) {
                if (token !== loadToken) {
                    return;
                }
                clearPrepareHint();
                showVoiceAlert(
                    err && err.message ? err.message : "Question audio is unavailable.",
                    "warning"
                );
            });
    }

    window.grillkitPlayQuestionAudio = function (answerId) {
        playQuestionAudio(answerId || null);
    };

    const initialAnswerId = composer.dataset.currentAnswerId || null;
    playQuestionAudio(initialAnswerId);
})();
