(function () {
    const TARGET_SAMPLE_RATE = 16000;

    function bootAudioAnswer() {
        const section = document.getElementById("answer-section");
        if (!section || section.getAttribute("data-audio-answer-enabled") !== "true") {
            return;
        }

        const interviewId = section.getAttribute("data-interview-id");
        const recordBtn = document.getElementById("audio-record-btn");
        const cancelBtn = document.getElementById("audio-cancel-btn");
        const sendBtn = document.getElementById("audio-send-btn");
        const recordHint = document.getElementById("audio-record-hint");

        if (!interviewId || !recordBtn || !cancelBtn || !sendBtn) {
            reportAudioError(
                "Audio answer controls could not start (page setup is incomplete). Refresh the page."
            );
            return;
        }

        let audioContext = null;
        let mediaStream = null;
        let sourceNode = null;
        let processorNode = null;
        let isRecording = false;
        let captureGeneration = 0;
        let pcmChunks = [];
        let pendingAnswerBubble = null;

        recordBtn.addEventListener("click", function () {
            startRecording().catch(function (err) {
                reportAudioError(err.message || String(err));
                abortRecording();
            });
        });

        cancelBtn.addEventListener("click", function () {
            abortRecording();
        });

        sendBtn.addEventListener("click", function () {
            submitRecording().catch(function (err) {
                reportAudioError(err.message || String(err));
                resetAfterFailure();
            });
        });

        async function startRecording() {
            if (window.isSubmitting) {
                reportAudioError(
                    "Please wait until the current answer finishes processing."
                );
                return;
            }

            if (typeof window.grillkitAbortDictation === "function") {
                window.grillkitAbortDictation();
            }

            if (!window.isSecureContext) {
                reportAudioError("Microphone access requires HTTPS or localhost.");
                return;
            }

            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                reportAudioError("This browser does not support microphone capture.");
                return;
            }

            pcmChunks = [];
            const generation = ++captureGeneration;
            recordBtn.disabled = true;

            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                if (generation !== captureGeneration) {
                    mediaStream.getTracks().forEach(function (track) {
                        track.stop();
                    });
                    mediaStream = null;
                    recordBtn.disabled = false;
                    return;
                }
                audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
                if (audioContext.state === "suspended") {
                    await audioContext.resume();
                }

                sourceNode = audioContext.createMediaStreamSource(mediaStream);
                processorNode = audioContext.createScriptProcessor(4096, 1, 1);
                const silentGain = audioContext.createGain();
                silentGain.gain.value = 0;

                processorNode.onaudioprocess = function (event) {
                    if (!isRecording) {
                        return;
                    }
                    const channel = event.inputBuffer.getChannelData(0);
                    const pcm = encodePcm16(channel, audioContext.sampleRate);
                    pcmChunks.push(new Uint8Array(pcm));
                };

                sourceNode.connect(processorNode);
                processorNode.connect(silentGain);
                silentGain.connect(audioContext.destination);
                isRecording = true;
                setRecordingUi(true);
                setComposerEnabled(false);
            } catch (err) {
                captureGeneration += 1;
                recordBtn.disabled = false;
                throw err;
            }
        }

        function abortRecording() {
            captureGeneration += 1;
            isRecording = false;
            cleanupAudio();
            pcmChunks = [];
            pendingAnswerBubble = null;
            setRecordingUi(false);
            setComposerEnabled(true);
        }

        async function submitRecording() {
            if (!isRecording || pcmChunks.length === 0) {
                abortRecording();
                reportAudioError("No audio was captured. Try recording again.");
                return;
            }

            isRecording = false;
            cleanupAudio();

            const wavBytes = buildWavFromChunks(pcmChunks, TARGET_SAMPLE_RATE);
            pcmChunks = [];

            if (wavBytes.byteLength <= 44) {
                setRecordingUi(false);
                setComposerEnabled(true);
                reportAudioError("Recording was too short. Try again.");
                return;
            }

            const context =
                typeof window.grillkitGetSubmissionContext === "function"
                    ? window.grillkitGetSubmissionContext()
                    : null;
            const questionId = context && context.questionId;
            if (!questionId) {
                setRecordingUi(false);
                setComposerEnabled(true);
                reportAudioError("Could not determine the current question.");
                return;
            }

            if (typeof window.grillkitSetSubmitting === "function") {
                window.grillkitSetSubmitting(true);
            } else {
                window.isSubmitting = true;
            }
            setRecordingUi(false);
            setComposerEnabled(false);
            showPendingAnswerBubble();

            if (window.grillkitQuestionTimer) {
                window.grillkitQuestionTimer.stop();
            }

            const formData = new FormData();
            formData.append("question_id", questionId);
            formData.append(
                "file",
                new Blob([wavBytes], { type: "audio/wav" }),
                "answer.wav"
            );

            const url =
                "/interview/" +
                encodeURIComponent(interviewId) +
                "/theory/audio-answer";

            const response = await fetch(url, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                let detail = response.statusText || "Audio answer failed";
                try {
                    const body = await response.json();
                    if (body && body.detail) {
                        detail =
                            typeof body.detail === "string"
                                ? body.detail
                                : String(body.detail);
                    }
                } catch (_err) {
                    /* ignore JSON parse errors */
                }
                throw new Error(detail);
            }

            await consumeNdjsonStream(response);
        }

        async function consumeNdjsonStream(response) {
            if (!response.body) {
                throw new Error("Audio answer stream is unavailable.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        break;
                    }
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split("\n");
                    buffer = lines.pop() || "";
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (!line) {
                            continue;
                        }
                        dispatchInterviewEvent(JSON.parse(line));
                    }
                }

                const tail = buffer.trim();
                if (tail) {
                    dispatchInterviewEvent(JSON.parse(tail));
                }
            } catch (err) {
                throw new Error(
                    err && err.message ? err.message : "Audio answer stream failed"
                );
            }
        }

        function dispatchInterviewEvent(data) {
            if (typeof window.grillkitHandleInterviewEvent === "function") {
                window.grillkitHandleInterviewEvent(data);
            }
        }

        function showPendingAnswerBubble() {
            const chatContainer = document.getElementById("chat-container");
            if (!chatContainer) {
                return;
            }
            pendingAnswerBubble = document.createElement("div");
            pendingAnswerBubble.className = "chat-message answer";
            pendingAnswerBubble.innerHTML =
                '<div class="chat-bubble answer-bubble"><strong>You:</strong> <em>Processing audio…</em></div>';
            chatContainer.appendChild(pendingAnswerBubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        function updatePendingAnswerBubble(text) {
            if (!pendingAnswerBubble) {
                if (typeof window.grillkitShowAnswerBubble === "function") {
                    window.grillkitShowAnswerBubble(text);
                }
                return;
            }
            const bubble = pendingAnswerBubble.querySelector(".answer-bubble");
            if (bubble) {
                bubble.innerHTML =
                    "<strong>You:</strong> " + escapeHtml(text || "");
            }
            pendingAnswerBubble = null;
        }

        function resetAfterFailure() {
            if (typeof window.grillkitSetSubmitting === "function") {
                window.grillkitSetSubmitting(false);
            } else {
                window.isSubmitting = false;
            }
            pendingAnswerBubble = null;
            setRecordingUi(false);
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

        function setRecordingUi(recording) {
            recordBtn.hidden = recording;
            cancelBtn.hidden = !recording;
            sendBtn.hidden = !recording;
            if (recordHint) {
                recordHint.hidden = !recording;
            }
            cancelBtn.disabled = !isRecording;
            sendBtn.disabled = !isRecording;
            if (recording) {
                recordBtn.classList.remove("is-recording");
            }
        }

        function setComposerEnabled(enabled) {
            const textarea = document.getElementById("answer_text");
            const submitBtn = document.getElementById("submit-btn");
            const endBtn = document.getElementById("end-btn");
            const dictationBtn = document.getElementById("dictation-mic-btn");
            if (textarea) {
                textarea.disabled = !enabled;
                if (enabled) {
                    textarea.readOnly = false;
                }
            }
            if (submitBtn) {
                submitBtn.disabled = !enabled;
            }
            if (endBtn && enabled) {
                endBtn.disabled = false;
            }
            if (dictationBtn) {
                dictationBtn.disabled = !enabled;
            }
            recordBtn.disabled = !enabled;
            if (cancelBtn.hidden) {
                cancelBtn.disabled = true;
                sendBtn.disabled = true;
            } else {
                cancelBtn.disabled = !isRecording;
                sendBtn.disabled = !isRecording;
            }
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

        function buildWavFromChunks(chunks, sampleRate) {
            let totalBytes = 0;
            for (let i = 0; i < chunks.length; i++) {
                totalBytes += chunks[i].byteLength;
            }

            const pcm = new Uint8Array(totalBytes);
            let offset = 0;
            for (let i = 0; i < chunks.length; i++) {
                pcm.set(chunks[i], offset);
                offset += chunks[i].byteLength;
            }

            const header = new ArrayBuffer(44);
            const view = new DataView(header);
            writeAscii(view, 0, "RIFF");
            view.setUint32(4, 36 + pcm.byteLength, true);
            writeAscii(view, 8, "WAVE");
            writeAscii(view, 12, "fmt ");
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, 1, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeAscii(view, 36, "data");
            view.setUint32(40, pcm.byteLength, true);

            const wav = new Uint8Array(44 + pcm.byteLength);
            wav.set(new Uint8Array(header), 0);
            wav.set(pcm, 44);
            return wav.buffer;
        }

        function writeAscii(view, offset, text) {
            for (let i = 0; i < text.length; i++) {
                view.setUint8(offset + i, text.charCodeAt(i));
            }
        }

        function escapeHtml(text) {
            if (!text) {
                return "";
            }
            const div = document.createElement("div");
            div.textContent = text;
            return div.innerHTML;
        }

        window.grillkitUpdateAudioAnswerBubble = updatePendingAnswerBubble;
        window.grillkitAbortAudioRecording = abortRecording;
        window.grillkitIsAudioRecording = function () {
            return isRecording;
        };
    }

    function reportAudioError(message) {
        if (typeof window.showError === "function") {
            window.showError(message);
            return;
        }
        alert(message);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootAudioAnswer);
    } else {
        bootAudioAnswer();
    }
})();
