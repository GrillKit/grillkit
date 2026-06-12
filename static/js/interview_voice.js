(function () {
    "use strict";

    const panel = document.getElementById("theory-panel");
    if (!panel || panel.dataset.questionVoiceEnabled !== "true") {
        return;
    }

    const interviewId = panel.dataset.interviewId;
    if (!interviewId) {
        return;
    }

    const alertsHost = document.getElementById("interview-alerts");
    let prepareHint = null;
    let audioElement = null;
    let loadToken = 0;
    let activeAnswerId = null;

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

    function setPlayingState(answerId, isPlaying) {
        panel.querySelectorAll(".btn-question-play").forEach(function (button) {
            const buttonAnswerId = button.dataset.answerId || "";
            const active = isPlaying && buttonAnswerId === String(answerId);
            button.classList.toggle("is-playing", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });
    }

    function disposeAudio() {
        if (audioElement) {
            audioElement.pause();
            audioElement.removeAttribute("src");
            audioElement.load();
            audioElement.remove();
            audioElement = null;
        }
        setPlayingState(activeAnswerId, false);
        activeAnswerId = null;
    }

    function playQuestionAudio(answerId) {
        const token = ++loadToken;
        disposeAudio();
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
                activeAnswerId = answerId != null ? String(answerId) : null;
                audioElement.addEventListener("ended", function () {
                    URL.revokeObjectURL(objectUrl);
                    setPlayingState(activeAnswerId, false);
                    activeAnswerId = null;
                    audioElement = null;
                });

                const startPlayback = function () {
                    const playPromise = audioElement.play();
                    if (!playPromise || typeof playPromise.then !== "function") {
                        setPlayingState(activeAnswerId, true);
                        return;
                    }
                    playPromise
                        .then(function () {
                            setPlayingState(activeAnswerId, true);
                        })
                        .catch(function () {
                            setPlayingState(activeAnswerId, false);
                            showVoiceAlert("Could not play question audio.", "warning");
                        });
                };

                if (audioElement.readyState >= 2) {
                    startPlayback();
                } else {
                    audioElement.addEventListener("canplay", startPlayback, {
                        once: true,
                    });
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

    function bindQuestionPlayButtons(root) {
        const scope = root || panel;
        scope.querySelectorAll(".btn-question-play").forEach(function (button) {
            if (button.dataset.voiceBound === "true") {
                return;
            }
            button.dataset.voiceBound = "true";
            button.addEventListener("click", function () {
                const answerId = button.dataset.answerId;
                if (!answerId) {
                    return;
                }
                playQuestionAudio(answerId);
            });
        });
    }

    window.grillkitPlayQuestionAudio = function (answerId) {
        playQuestionAudio(answerId || null);
    };

    window.grillkitBindQuestionPlayButtons = bindQuestionPlayButtons;

    window.grillkitQuestionPlayButtonHtml = function (answerId) {
        if (!answerId) {
            return "";
        }
        return (
            '<button type="button" class="btn btn-sm btn-outline btn-question-play"'
            + ' data-answer-id="' + String(answerId) + '"'
            + ' aria-label="Play question" title="Play question"'
            + ' aria-pressed="false">Play</button>'
        );
    };

    bindQuestionPlayButtons(panel);

    const composer = document.getElementById("answer-section");
    const initialAnswerId = composer ? composer.dataset.currentAnswerId || null : null;
    if (initialAnswerId) {
        playQuestionAudio(initialAnswerId);
    }
})();
