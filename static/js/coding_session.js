(function () {
    "use strict";

    const panel = document.getElementById("coding-panel");
    if (!panel) {
        return;
    }

    const interviewId = panel.dataset.interviewId || "";
    let taskId = panel.dataset.taskId || "";
    let currentRound = Number(panel.dataset.round || 0);
    const taskTimerEnabled = panel.dataset.taskTimerEnabled === "true";
    const taskTimeLimitSeconds = panel.dataset.taskTimeLimit
        ? Number(panel.dataset.taskTimeLimit)
        : null;
    let timerRemainingSeconds = panel.dataset.timerRemaining
        ? Number(panel.dataset.timerRemaining)
        : null;
    const llmRequestTimeoutSeconds = Number(panel.dataset.llmTimeout || 60);
    let isSubmitting = false;
    window.isSubmitting = false;
    let ws = null;
    let reconnectTimer = null;
    let evaluationWatchdogTimer = null;
    let followUpMode = "code";
    let starterCode = "";

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl =
        wsProtocol + "//" + window.location.host + "/interview/" + interviewId + "/coding/ws";

    function escapeHtml(text) {
        if (!text) {
            return "";
        }
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function showError(message) {
        if (typeof window.showError === "function") {
            window.showError(message);
            return;
        }
        alert(message);
    }

    function getRunBtn() {
        return document.getElementById("coding-run-btn");
    }

    function getSubmitBtn() {
        return document.getElementById("coding-submit-btn");
    }

    function getOutput() {
        return document.getElementById("coding-output");
    }

    function setComposerEnabled(enabled) {
        const runBtn = getRunBtn();
        const submitBtn = getSubmitBtn();
        if (runBtn) {
            runBtn.disabled = !enabled;
        }
        if (submitBtn) {
            submitBtn.disabled = !enabled;
        }
    }

    function showEvaluating(visible) {
        const indicator = document.getElementById("coding-evaluating-indicator");
        if (indicator) {
            indicator.hidden = !visible;
        }
    }

    function updateProgressDisplay(completed, total) {
        const progressEl = document.getElementById("coding-progress");
        if (!progressEl) {
            return;
        }
        if (completed >= total) {
            progressEl.textContent = "All coding tasks submitted";
        } else {
            progressEl.textContent =
                "Task " + String(completed + 1) + " of " + String(total);
        }
    }

    function updateTaskHeader(task) {
        const title = document.getElementById("coding-task-title");
        const prompt = document.getElementById("coding-task-prompt");
        if (!task) {
            return;
        }
        if (title) {
            let label = "Task " + String(task.order);
            if (task.round > 0) {
                label += " · follow-up";
            }
            title.textContent = label;
        }
        if (prompt) {
            prompt.textContent = task.prompt_text || "";
        }
        if (window.KnownQuestions && window.KnownQuestions.updateCodingKnownItem) {
            const itemId = task.task_id || taskId;
            const round = task.round != null ? Number(task.round) : 0;
            window.KnownQuestions.updateCodingKnownItem(itemId, round);
        }
    }

    function applyTask(task) {
        if (!task) {
            return;
        }
        taskId = task.task_id;
        currentRound = task.round != null ? Number(task.round) : 0;
        panel.dataset.taskId = taskId;
        panel.dataset.round = String(currentRound);
        updateTaskHeader(task);
        const spec = task.task_spec || {};
        starterCode = spec.starter_code || "";
        followUpMode = "code";
        const editorContainer = document.getElementById("coding-editor");
        if (editorContainer && window.grillkitCodingEditor) {
            window.grillkitCodingEditor.init(editorContainer, {
                interviewId: interviewId,
                taskId: taskId,
                round: currentRound,
                starterCode: starterCode,
                language: spec.language || "python",
            }).then(function () {
                window.grillkitCodingEditor.setFollowUpMode("code");
                window.grillkitCodingEditor.layout();
            }).catch(function (err) {
                showError(err.message || "Failed to initialize code editor.");
            });
        }
        const output = getOutput();
        if (output) {
            output.innerHTML = "";
            if (window.grillkitCodingEditor) {
                window.grillkitCodingEditor.syncRunsPanel(output);
            }
        }
        loadRunHistory();
        restartTaskTimer(timerRemainingSeconds);
    }

    function loadRunHistory() {
        if (!taskId) {
            return;
        }
        fetch("/interview/" + encodeURIComponent(interviewId) + "/coding/state")
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Failed to load coding state");
                }
                return response.json();
            })
            .then(function (state) {
                const output = getOutput();
                if (!output) {
                    return;
                }
                const attempts = state.run_attempts || [];
                window.grillkitCodingEditor.renderRunHistory(output, attempts);
                updateProgressDisplay(
                    state.completed_tasks || 0,
                    state.total_tasks || 0
                );
            })
            .catch(function () {
                /* history is optional on load */
            });
    }

    function restartTaskTimer(remainingSeconds) {
        if (!taskTimerEnabled || !window.grillkitQuestionTimer) {
            return;
        }
        const seconds =
            remainingSeconds != null ? remainingSeconds : taskTimeLimitSeconds;
        window.grillkitQuestionTimer.start({
            enabled: true,
            remainingSeconds: seconds,
            questionId: taskId,
            round: currentRound,
            getWs: function () {
                return ws;
            },
        });
    }

    function stopTaskTimer() {
        if (window.grillkitQuestionTimer) {
            window.grillkitQuestionTimer.stop();
        }
    }

    function clearEvaluationWatchdog() {
        if (evaluationWatchdogTimer) {
            clearTimeout(evaluationWatchdogTimer);
            evaluationWatchdogTimer = null;
        }
    }

    function startEvaluationWatchdog() {
        clearEvaluationWatchdog();
        const graceMs = 15000;
        const timeoutMs = llmRequestTimeoutSeconds * 1000 + graceMs;
        evaluationWatchdogTimer = setTimeout(function () {
            evaluationWatchdogTimer = null;
            if (!isSubmitting) {
                return;
            }
            showEvaluating(false);
            isSubmitting = false;
            window.isSubmitting = false;
            setComposerEnabled(true);
            showError(
                "AI evaluation is taking too long. Check /config, then try again."
            );
        }, timeoutMs);
    }

    function connectWebSocket() {
        ws = new WebSocket(wsUrl);

        ws.onopen = function () {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        };

        ws.onmessage = function (event) {
            const data = JSON.parse(event.data);
            handleWsMessage(data);
        };

        ws.onclose = function () {
            const indicator = document.getElementById("coding-evaluating-indicator");
            const wasEvaluating = indicator && !indicator.hidden;
            if (wasEvaluating || isSubmitting) {
                clearEvaluationWatchdog();
                showEvaluating(false);
                isSubmitting = false;
                window.isSubmitting = false;
                setComposerEnabled(true);
                showError(
                    "Connection lost during evaluation. Refresh the page to continue."
                );
            }
            reconnectTimer = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = function (err) {
            console.error("Coding WebSocket error:", err);
        };
    }

    function shouldSwitchToTheoryPhase() {
        return (
            window.grillkitSessionPhaseNav &&
            window.grillkitSessionPhaseNav.hasPendingTheoryPhase()
        );
    }

    function handleFeedback(data) {
        clearEvaluationWatchdog();
        showEvaluating(false);
        isSubmitting = false;
        window.isSubmitting = false;
        setComposerEnabled(true);

        const output = getOutput();
        if (output && data.feedback) {
            window.grillkitCodingEditor.renderFeedback(output, data.feedback);
        }

        if (data.follow_up_question) {
            const mode = data.follow_up_mode || "code";
            followUpMode = mode;
            updateTaskHeader({
                order: data.order,
                round: data.round + 1,
                prompt_text: data.follow_up_question,
            });
            currentRound = data.round + 1;
            panel.dataset.round = String(currentRound);
            if (mode === "explanation") {
                window.grillkitCodingEditor.setFollowUpMode(
                    "explanation",
                    ""
                );
            } else {
                window.grillkitCodingEditor.setFollowUpMode("code");
            }
            restartTaskTimer(data.timer_remaining_seconds);
            return;
        }

        if (data.next_task) {
            window.grillkitCodingEditor.clearDraftForTask(
                interviewId,
                taskId,
                currentRound
            );
            timerRemainingSeconds = data.timer_remaining_seconds;
            applyTask(data.next_task);
            return;
        }

        stopTaskTimer();
        window.grillkitCodingEditor.clearDraftForTask(
            interviewId,
            taskId,
            currentRound
        );
        updateProgressDisplay(
            Number(panel.dataset.taskCount || 0),
            Number(panel.dataset.taskCount || 0)
        );

        if (shouldSwitchToTheoryPhase()) {
            window.location.reload();
            return;
        }

        const footer = document.querySelector(".coding-session__footer");
        const body = document.querySelector(".coding-session__body");
        if (footer) {
            footer.hidden = true;
        }
        if (body) {
            body.hidden = true;
        }
        let doneSection = document.querySelector(".coding-session__done");
        if (!doneSection && panel) {
            doneSection = document.createElement("section");
            doneSection.className = "coding-session__done";
            doneSection.innerHTML =
                "<h2>All coding tasks submitted</h2>" +
                '<p class="text-muted">Use <strong>End Interview</strong> for your final evaluation.</p>';
            panel.appendChild(doneSection);
        }
    }

    function handleWsMessage(data) {
        switch (data.type) {
            case "saved":
                break;
            case "evaluating":
                showEvaluating(true);
                startEvaluationWatchdog();
                break;
            case "feedback":
                handleFeedback(data);
                break;
            case "error":
                clearEvaluationWatchdog();
                showEvaluating(false);
                isSubmitting = false;
                window.isSubmitting = false;
                setComposerEnabled(true);
                showError(data.message || "Coding submit failed.");
                break;
            default:
                break;
        }
    }

    function runCode() {
        if (!taskId || isSubmitting) {
            return;
        }
        const sourceCode = window.grillkitCodingEditor.getValue().trim();
        if (!sourceCode) {
            alert("Please enter some code before running.");
            return;
        }
        const runBtn = getRunBtn();
        if (runBtn) {
            runBtn.disabled = true;
        }
        fetch(
            "/interview/" + encodeURIComponent(interviewId) + "/coding/run",
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    task_id: taskId,
                    source_code: sourceCode,
                }),
            }
        )
            .then(function (response) {
                return response.json().then(function (body) {
                    if (!response.ok) {
                        const message =
                            body.detail ||
                            body.message ||
                            "Run failed (" + String(response.status) + ").";
                        throw new Error(
                            typeof message === "string"
                                ? message
                                : JSON.stringify(message)
                        );
                    }
                    return body;
                });
            })
            .then(function (result) {
                const output = getOutput();
                if (output) {
                    window.grillkitCodingEditor.renderRunResult(output, result);
                }
            })
            .catch(function (err) {
                showError(err.message || "Run failed.");
            })
            .finally(function () {
                if (runBtn) {
                    runBtn.disabled = isSubmitting;
                }
            });
    }

    function submitCode() {
        if (!taskId || isSubmitting) {
            return;
        }
        const sourceCode = window.grillkitCodingEditor.getValue().trim();
        if (!sourceCode) {
            alert(
                followUpMode === "explanation"
                    ? "Please enter your explanation."
                    : "Please enter your code before submitting."
            );
            return;
        }
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            showError("Not connected. Reconnecting…");
            connectWebSocket();
            return;
        }
        isSubmitting = true;
        window.isSubmitting = true;
        setComposerEnabled(false);
        stopTaskTimer();
        ws.send(
            JSON.stringify({
                type: "submit",
                task_id: taskId,
                source_code: sourceCode,
            })
        );
    }

    window.grillkitOnTimerExpired = function () {
        if (isSubmitting) {
            return;
        }
        isSubmitting = true;
        window.isSubmitting = true;
        setComposerEnabled(false);
    };

    function bindActions() {
        const runBtn = getRunBtn();
        const submitBtn = getSubmitBtn();
        if (runBtn) {
            runBtn.addEventListener("click", runCode);
        }
        if (submitBtn) {
            submitBtn.addEventListener("click", submitCode);
        }
    }

    window.grillkitCodingSession = {
        hasPendingCodingPhase: function () {
            return (
                window.grillkitSessionPhaseNav &&
                window.grillkitSessionPhaseNav.hasPendingCodingPhase()
            );
        },
        switchToCodingPhase: function () {
            if (window.grillkitSessionPhaseNav) {
                window.grillkitSessionPhaseNav.continueToNextPhase();
            } else {
                window.location.reload();
            }
        },
    };

    document.addEventListener("DOMContentLoaded", function () {
        if (panel.dataset.complete === "true" || !taskId) {
            return;
        }
        bindActions();
        connectWebSocket();
        const initialTask = {
            task_id: taskId,
            order: Number(panel.dataset.completedTasks || 0) + 1,
            round: currentRound,
            prompt_text:
                document.getElementById("coding-task-prompt")?.textContent || "",
            task_spec: {
                starter_code: starterCode,
                language: "python",
            },
        };
        const bootstrap = window.grillkitCodingBootstrap;
        if (bootstrap && bootstrap.currentTask) {
            initialTask.prompt_text = bootstrap.currentTask.prompt_text;
            initialTask.order = bootstrap.currentTask.order;
            initialTask.round = bootstrap.currentTask.round;
            initialTask.task_spec = bootstrap.currentTask.task_spec || {};
        }
        applyTask(initialTask);
    });
})();
