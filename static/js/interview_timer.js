(function () {
    "use strict";

    let intervalId = null;
    let remaining = 0;
    let questionId = "";
    let round = 0;
    let getWs = null;
    let timedOutSent = false;

    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return String(minutes).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
    }

    function updateDisplay() {
        const el = document.getElementById("interview-timer");
        if (!el) {
            return;
        }
        el.textContent = formatTime(Math.max(0, remaining));
        el.classList.toggle("timer-warning", remaining > 0 && remaining <= 30);
        el.classList.toggle("timer-expired", remaining <= 0);
    }

    function stop() {
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
    }

    function sendTimeout() {
        if (timedOutSent || !getWs) {
            return;
        }
        if (window.isSubmitting) {
            return;
        }
        const socket = getWs();
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            return;
        }
        timedOutSent = true;
        if (typeof window.grillkitOnTimerExpired === "function") {
            window.grillkitOnTimerExpired();
        }
        socket.send(
            JSON.stringify({
                type: "timeout",
                question_id: questionId,
                round: round,
            })
        );
    }

    function tick() {
        if (remaining <= 0) {
            stop();
            updateDisplay();
            sendTimeout();
            return;
        }
        remaining -= 1;
        updateDisplay();
        if (remaining <= 0) {
            stop();
            sendTimeout();
        }
    }

    window.grillkitQuestionTimer = {
        start: function (config) {
            stop();
            const row = document.getElementById("interview-timer-row");
            if (!config || !config.enabled) {
                if (row) {
                    row.hidden = true;
                }
                return;
            }
            if (row) {
                row.hidden = false;
            }
            remaining =
                config.remainingSeconds != null ? Number(config.remainingSeconds) : 0;
            questionId = config.questionId || "";
            round = config.round != null ? Number(config.round) : 0;
            getWs = config.getWs || null;
            timedOutSent = false;
            updateDisplay();
            if (remaining <= 0) {
                sendTimeout();
                return;
            }
            intervalId = setInterval(tick, 1000);
        },
        stop: stop,
    };
})();
