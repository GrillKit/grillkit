(function () {
    const HANDSHAKE_TIMEOUT_MS = 15000;
    const TARGET_SAMPLE_RATE = 16000;

    function bootDictation() {
        const section = document.getElementById("answer-section");
        if (!section || section.getAttribute("data-dictation-enabled") !== "true") {
            return;
        }

        const interviewId = section.getAttribute("data-interview-id");
        const micBtn = document.getElementById("dictation-mic-btn");
        const textarea = document.getElementById("answer_text");
        const dictationHint = document.getElementById("dictation-hint");

        if (!interviewId || !micBtn || !textarea) {
            reportDictationSetupError(
                "Voice input could not start (page setup is incomplete). Refresh the page."
            );
            return;
        }

        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const dictationUrl =
            wsProtocol +
            "//" +
            window.location.host +
            "/interview/" +
            encodeURIComponent(interviewId) +
            "/dictation";

        let dictationWs = null;
        let audioContext = null;
        let mediaStream = null;
        let sourceNode = null;
        let processorNode = null;
        let isRecording = false;
        let handshakeComplete = false;
        let textBeforeDictation = "";

        micBtn.addEventListener("click", function () {
            if (isRecording) {
                stopDictation();
            } else {
                startDictation().catch(function (err) {
                    reportDictationError(err.message || String(err));
                    abortDictation();
                });
            }
        });

        async function startDictation() {
            if (window.isSubmitting) {
                reportDictationError(
                    "Please wait until the current answer finishes processing."
                );
                return;
            }

            if (!window.isSecureContext) {
                reportDictationError(
                    "Microphone access requires HTTPS or localhost."
                );
                return;
            }

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                reportDictationError("This browser does not support microphone capture.");
                return;
            }

            textBeforeDictation = textarea.value;
            setMicState("connecting");
            await connectDictationSocket();
            await startMicrophoneCapture();
            setMicState("recording");
        }

        function connectDictationSocket() {
            return new Promise(function (resolve, reject) {
                handshakeComplete = false;
                let settled = false;

                function finishResolve() {
                    if (settled) {
                        return;
                    }
                    settled = true;
                    clearTimeout(timeoutId);
                    handshakeComplete = true;
                    resolve();
                }

                function finishReject(err) {
                    if (settled) {
                        return;
                    }
                    settled = true;
                    clearTimeout(timeoutId);
                    if (dictationWs) {
                        dictationWs.close();
                        dictationWs = null;
                    }
                    reject(err);
                }

                const timeoutId = setTimeout(function () {
                    finishReject(
                        new Error(
                            "Dictation connection timed out. Re-open Configuration and ensure the speech model is ready."
                        )
                    );
                }, HANDSHAKE_TIMEOUT_MS);

                dictationWs = new WebSocket(dictationUrl);
                dictationWs.binaryType = "arraybuffer";

                dictationWs.onopen = function () {
                    dictationWs.send(JSON.stringify({ type: "start" }));
                };

                dictationWs.onmessage = function (event) {
                    const data = JSON.parse(event.data);
                    if (data.type === "ready") {
                        finishResolve();
                        return;
                    }
                    if (data.type === "error") {
                        finishReject(new Error(data.message || "Dictation failed"));
                    }
                };

                dictationWs.onerror = function () {
                    finishReject(new Error("Dictation connection failed"));
                };

                dictationWs.onclose = function () {
                    if (!handshakeComplete) {
                        finishReject(
                            new Error(
                                "Dictation connection closed before recording could start."
                            )
                        );
                        return;
                    }
                    if (isRecording || micBtn.disabled) {
                        abortDictation();
                    }
                };
            });
        }

        async function startMicrophoneCapture() {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
            if (audioContext.state === "suspended") {
                await audioContext.resume();
            }

            sourceNode = audioContext.createMediaStreamSource(mediaStream);
            processorNode = audioContext.createScriptProcessor(4096, 1, 1);
            const silentGain = audioContext.createGain();
            silentGain.gain.value = 0;

            processorNode.onaudioprocess = function (event) {
                if (!isRecording || !dictationWs || dictationWs.readyState !== WebSocket.OPEN) {
                    return;
                }
                const channel = event.inputBuffer.getChannelData(0);
                const pcm = encodePcm16(channel, audioContext.sampleRate);
                dictationWs.send(pcm);
            };

            sourceNode.connect(processorNode);
            processorNode.connect(silentGain);
            silentGain.connect(audioContext.destination);

            isRecording = true;
            setComposerEnabled(false);

            dictationWs.onmessage = function (event) {
                handleDictationMessage(JSON.parse(event.data));
            };
        }

        function handleDictationMessage(data) {
            if (data.type === "final") {
                applyFinalTranscript(data.text || "");
                cleanupAudio();
                if (dictationWs) {
                    dictationWs.close();
                    dictationWs = null;
                }
                resetMicUi();
                setComposerEnabled(true);
            } else if (data.type === "error") {
                reportDictationError(data.message || "Dictation failed");
                abortDictation();
            }
        }

        function stopDictation() {
            if (!dictationWs || dictationWs.readyState !== WebSocket.OPEN) {
                abortDictation();
                return;
            }
            isRecording = false;
            cleanupAudio();
            dictationWs.send(JSON.stringify({ type: "stop" }));
            micBtn.disabled = true;
            setMicState("finishing");
        }

        function abortDictation() {
            isRecording = false;
            handshakeComplete = false;
            cleanupAudio();
            if (dictationWs) {
                dictationWs.close();
                dictationWs = null;
            }
            resetMicUi();
            setComposerEnabled(true);
        }

        function cleanupAudio() {
            if (processorNode) {
                processorNode.disconnect();
                processorNode.onaudioprocess = null;
                processorNode = null;
            }
            if (sourceNode) {
                sourceNode.disconnect();
                sourceNode = null;
            }
            if (mediaStream) {
                mediaStream.getTracks().forEach(function (track) {
                    track.stop();
                });
                mediaStream = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
        }

        function resetMicUi() {
            micBtn.classList.remove("is-recording");
            micBtn.setAttribute("aria-pressed", "false");
            micBtn.disabled = false;
            if (dictationHint) {
                dictationHint.hidden = true;
                dictationHint.textContent =
                    "Listening… transcription appears when you stop";
            }
        }

        function setMicState(state) {
            if (state === "connecting") {
                micBtn.disabled = true;
                if (dictationHint) {
                    dictationHint.hidden = false;
                    dictationHint.textContent = "Connecting…";
                }
                return;
            }
            if (state === "recording") {
                micBtn.disabled = false;
                micBtn.classList.add("is-recording");
                micBtn.setAttribute("aria-pressed", "true");
                if (dictationHint) {
                    dictationHint.hidden = false;
                    dictationHint.textContent =
                        "Listening… click Voice again to stop";
                }
                return;
            }
            if (state === "finishing" && dictationHint) {
                dictationHint.hidden = false;
                dictationHint.textContent = "Finishing transcription…";
            }
        }

        function applyFinalTranscript(finalText) {
            const final = (finalText || "").trim();
            textarea.value = combineDictationText(textBeforeDictation, final);
        }

        function combineDictationText(prefix, dictated) {
            const left = (prefix || "").trimEnd();
            const right = (dictated || "").trim();
            if (!left) {
                return right;
            }
            if (!right) {
                return left;
            }
            return left + (left.endsWith(" ") ? "" : " ") + right;
        }

        function encodePcm16(floatSamples, sourceSampleRate) {
            const samples =
                sourceSampleRate === TARGET_SAMPLE_RATE
                    ? floatSamples
                    : resampleFloat32(floatSamples, sourceSampleRate, TARGET_SAMPLE_RATE);
            const buffer = new ArrayBuffer(samples.length * 2);
            const view = new DataView(buffer);
            for (let i = 0; i < samples.length; i++) {
                const clamped = Math.max(-1, Math.min(1, samples[i]));
                view.setInt16(
                    i * 2,
                    clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff,
                    true
                );
            }
            return buffer;
        }

        function resampleFloat32(input, fromRate, toRate) {
            if (fromRate === toRate) {
                return input;
            }
            const ratio = fromRate / toRate;
            const outputLength = Math.floor(input.length / ratio);
            const output = new Float32Array(outputLength);
            for (let i = 0; i < outputLength; i++) {
                const index = Math.floor(i * ratio);
                output[i] = input[index];
            }
            return output;
        }

        function setComposerEnabled(enabled) {
            textarea.readOnly = !enabled;
            const submitBtn = document.getElementById("submit-btn");
            const endBtn = document.getElementById("end-btn");
            if (submitBtn) {
                submitBtn.disabled = !enabled;
            }
            if (endBtn && enabled) {
                endBtn.disabled = false;
            }
        }

        window.grillkitAbortDictation = abortDictation;
    }

    function reportDictationError(message) {
        if (typeof window.showError === "function") {
            window.showError(message);
            return;
        }
        alert(message);
    }

    function reportDictationSetupError(message) {
        reportDictationError(message);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootDictation);
    } else {
        bootDictation();
    }
})();
