(function () {
    const config = window.grillkitDictation;
    if (!config || !config.enabled) {
        return;
    }

    const micBtn = document.getElementById("dictation-mic-btn");
    const textarea = document.getElementById("answer_text");
    const dictationHint = document.getElementById("dictation-hint");
    if (!micBtn || !textarea) {
        return;
    }

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const dictationUrl =
        wsProtocol + "//" + window.location.host + "/interview/" + config.interviewId + "/dictation";

    const TARGET_SAMPLE_RATE = 16000;

    let dictationWs = null;
    let audioContext = null;
    let mediaStream = null;
    let sourceNode = null;
    let processorNode = null;
    let isRecording = false;
    let textBeforeDictation = "";

    micBtn.addEventListener("click", function () {
        if (isRecording) {
            stopDictation();
        } else {
            startDictation().catch(function (err) {
                showDictationError(err.message || String(err));
            });
        }
    });

    async function startDictation() {
        if (typeof window.isSubmitting === "boolean" && window.isSubmitting) {
            return;
        }

        textBeforeDictation = textarea.value;
        dictationWs = new WebSocket(dictationUrl);
        dictationWs.binaryType = "arraybuffer";
        dictationWs.onclose = function () {
            if (isRecording || micBtn.disabled) {
                abortDictation();
            }
        };

        await new Promise(function (resolve, reject) {
            dictationWs.onopen = function () {
                dictationWs.send(JSON.stringify({ type: "start" }));
            };
            dictationWs.onmessage = function (event) {
                const data = JSON.parse(event.data);
                if (data.type === "ready") {
                    resolve();
                    return;
                }
                if (data.type === "error") {
                    reject(new Error(data.message || "Dictation failed"));
                }
            };
            dictationWs.onerror = function () {
                reject(new Error("Dictation connection failed"));
            };
        });

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
        micBtn.classList.add("is-recording");
        micBtn.setAttribute("aria-pressed", "true");
        if (dictationHint) {
            dictationHint.hidden = false;
            dictationHint.textContent = "Listening… transcription appears when you stop";
        }
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
            showDictationError(data.message || "Dictation failed");
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
        if (dictationHint) {
            dictationHint.textContent = "Finishing transcription…";
        }
    }

    function abortDictation() {
        isRecording = false;
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
            dictationHint.textContent = "Listening… transcription appears when you stop";
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
            view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
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
        if (enabled) {
            textarea.readOnly = false;
        }
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

    function showDictationError(message) {
        if (typeof window.showError === "function") {
            window.showError(message);
        } else {
            alert(message);
        }
    }
})();
