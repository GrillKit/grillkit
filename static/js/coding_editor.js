(function () {
    "use strict";

    let editor = null;
    let monacoReady = false;
    let monacoInitPromise = null;

    function loadMonaco() {
        if (monacoInitPromise) {
            return monacoInitPromise;
        }
        monacoInitPromise = new Promise(function (resolve, reject) {
            if (window.monaco && window.monaco.editor) {
                monacoReady = true;
                resolve(window.monaco);
                return;
            }
            const script = document.createElement("script");
            script.src =
                "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js";
            script.onload = function () {
                window.require.config({
                    paths: {
                        vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs",
                    },
                });
                window.require(["vs/editor/editor.main"], function () {
                    monacoReady = true;
                    resolve(window.monaco);
                }, reject);
            };
            script.onerror = function () {
                reject(new Error("Failed to load Monaco editor"));
            };
            document.head.appendChild(script);
        });
        return monacoInitPromise;
    }

    function escapeHtml(text) {
        if (!text) {
            return "";
        }
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function getRunsPanel() {
        return document.getElementById("coding-runs-panel");
    }

    function getBrief() {
        return document.querySelector(".coding-session__brief");
    }

    function syncRunsPanel(container) {
        const output = container || document.getElementById("coding-output");
        const hasContent = output && output.childElementCount > 0;
        const panel = getRunsPanel();
        const brief = getBrief();
        if (panel) {
            panel.hidden = !hasContent;
        }
        if (brief) {
            brief.classList.toggle("coding-session__brief--has-runs", hasContent);
        }
    }

    function draftKey(interviewId, taskId, round) {
        return (
            "grillkit-coding-draft:" +
            interviewId +
            ":" +
            taskId +
            ":" +
            String(round != null ? round : 0)
        );
    }

    function readDraft(key) {
        try {
            return sessionStorage.getItem(key);
        } catch (_err) {
            return null;
        }
    }

    function writeDraft(key, value) {
        try {
            sessionStorage.setItem(key, value);
        } catch (_err) {
            /* ignore quota errors */
        }
    }

    function clearDraft(key) {
        try {
            sessionStorage.removeItem(key);
        } catch (_err) {
            /* ignore */
        }
    }

    window.grillkitCodingEditor = {
        init: function (container, options) {
            const opts = options || {};
            const interviewId = opts.interviewId || "";
            const taskId = opts.taskId || "";
            const round = opts.round != null ? opts.round : 0;
            const starterCode = opts.starterCode || "";
            const language = opts.language || "python";
            const key = draftKey(interviewId, taskId, round);
            const saved = readDraft(key);
            const initialValue = saved != null ? saved : starterCode;

            return loadMonaco().then(function (monaco) {
                if (editor) {
                    editor.dispose();
                    editor = null;
                }
                editor = monaco.editor.create(container, {
                    value: initialValue,
                    language: language,
                    theme: "vs-dark",
                    automaticLayout: true,
                    minimap: { enabled: false },
                    fontSize: 14,
                    scrollBeyondLastLine: false,
                });
                editor.onDidChangeModelContent(function () {
                    writeDraft(key, editor.getValue());
                });
                return editor;
            });
        },

        getValue: function () {
            if (editor) {
                return editor.getValue();
            }
            const textarea = document.getElementById("coding-explanation-input");
            if (textarea && !textarea.hidden) {
                return textarea.value;
            }
            return "";
        },

        setValue: function (value) {
            if (editor) {
                editor.setValue(value || "");
            }
        },

        setFollowUpMode: function (mode, text) {
            const wrap = document.getElementById("coding-editor-wrap");
            const monacoEl = document.getElementById("coding-editor");
            const textarea = document.getElementById("coding-explanation-input");
            if (!wrap || !monacoEl || !textarea) {
                return;
            }
            if (mode === "explanation") {
                monacoEl.hidden = false;
                textarea.hidden = false;
                wrap.classList.add("coding-session__editor-shell--explanation");
                textarea.value = text || "";
                textarea.focus();
                if (editor) {
                    editor.layout();
                }
            } else {
                monacoEl.hidden = false;
                textarea.hidden = true;
                wrap.classList.remove("coding-session__editor-shell--explanation");
                if (editor && text) {
                    editor.setValue(text);
                }
                if (editor) {
                    editor.layout();
                }
            }
        },

        isMonacoVisible: function () {
            const monacoEl = document.getElementById("coding-editor");
            return Boolean(monacoEl && !monacoEl.hidden);
        },

        layout: function () {
            if (editor) {
                editor.layout();
            }
        },

        clearDraftForTask: function (interviewId, taskId, round) {
            clearDraft(draftKey(interviewId, taskId, round));
        },

        renderRunResult: function (container, result) {
            if (!container || !result) {
                return;
            }
            let html = '<div class="coding-run-result">';
            html +=
                '<div class="coding-run-header">Attempt #' +
                escapeHtml(String(result.attempt_no)) +
                " &mdash; " +
                escapeHtml(result.status) +
                "</div>";
            if (result.tests_total > 0) {
                html +=
                    '<div class="coding-run-tests">Tests: ' +
                    escapeHtml(String(result.tests_passed)) +
                    " / " +
                    escapeHtml(String(result.tests_total)) +
                    "</div>";
            }
            if (Array.isArray(result.test_results)) {
                html += '<ul class="coding-test-list">';
                result.test_results.forEach(function (testCase) {
                    const css = testCase.passed ? "test-pass" : "test-fail";
                    html +=
                        '<li class="' +
                        css +
                        '"><strong>' +
                        escapeHtml(testCase.name) +
                        "</strong>";
                    if (testCase.passed) {
                        html += " passed";
                    } else {
                        html += " failed";
                        if (testCase.actual_stdout != null) {
                            html +=
                                '<pre class="coding-run-pre">got: ' +
                                escapeHtml(testCase.actual_stdout) +
                                "</pre>";
                        }
                        if (testCase.expected_stdout != null) {
                            html +=
                                '<pre class="coding-run-pre">expected: ' +
                                escapeHtml(testCase.expected_stdout) +
                                "</pre>";
                        }
                    }
                    html += "</li>";
                });
                html += "</ul>";
            }
            if (result.compile_output) {
                html +=
                    '<pre class="coding-run-pre coding-run-error">' +
                    escapeHtml(result.compile_output) +
                    "</pre>";
            }
            if (result.stderr) {
                html +=
                    '<pre class="coding-run-pre coding-run-error">' +
                    escapeHtml(result.stderr) +
                    "</pre>";
            }
            if (result.stdout) {
                html +=
                    '<pre class="coding-run-pre">' +
                    escapeHtml(result.stdout) +
                    "</pre>";
            }
            html += "</div>";
            container.insertAdjacentHTML("beforeend", html);
            container.scrollTop = container.scrollHeight;
            syncRunsPanel(container);
        },

        renderRunHistory: function (container, attempts) {
            if (!container || !Array.isArray(attempts)) {
                return;
            }
            container.innerHTML = "";
            attempts.forEach(function (attempt) {
                window.grillkitCodingEditor.renderRunResult(container, attempt);
            });
            syncRunsPanel(container);
        },

        renderFeedback: function (container, feedbackText) {
            if (!container || !feedbackText) {
                return;
            }
            const block = document.createElement("div");
            block.className = "coding-feedback-block";
            block.innerHTML =
                "<strong>Feedback:</strong> " + escapeHtml(feedbackText);
            container.appendChild(block);
            container.scrollTop = container.scrollHeight;
            syncRunsPanel(container);
        },

        syncRunsPanel: syncRunsPanel,
    };
})();
