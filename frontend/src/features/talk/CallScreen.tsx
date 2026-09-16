import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../store/AuthContext";
import { callsApi, conversationsApi } from "../../services/domainApi";
import {
  createSpeechRecognizer,
  isSpeechRecognitionSupported,
  speak,
  stopSpeaking,
  registerSpeechAudio,
  unlockSpeechAudio,
  type CallLanguage,
  type SpeechErrorReason,
  type SpeechRecognizer,
} from "../../services/speech";
import {
  isRecordingSupported,
  saveRecordingLocally,
  startRecording,
  type ActiveRecording,
} from "../../services/callRecorder";
import type { VoiceCall } from "../../types/domain";
import { CallGlyph, type GlyphPhase } from "./CallGlyph";

type Screen = "setup" | "starting" | "active" | "ending" | "ended" | "error";
// Sub-state of the call itself once active — drives both the glyph
// animation and which controls make sense to show.
type CallPhase = "idle" | "listening" | "processing" | "speaking";

function formatTimer(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/**
 * The phone-call-like voice experience (section 13): a setup screen with a
 * recording opt-in, then an active call with the glyph, timer, mic/speaker
 * controls, end call, and a visible recording indicator. STT/TTS run
 * through the browser Web Speech API (see services/speech.ts) with a
 * manual-text fallback when that API isn't available.
 *
 * Every function in the listen -> transcribe -> reply -> listen-again loop
 * below takes the active VoiceCall as an explicit parameter rather than
 * reading it from `call` state/closure. That's deliberate: the loop is
 * kicked off from `startCall` in the same tick the call is created, before
 * the state update from `setCall` has re-rendered the component, so a
 * closure over `call` state at that point would still see null. Threading
 * the object through explicitly avoids relying on render timing at all.
 */
export function CallScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [screen, setScreen] = useState<Screen>("setup");
  const [call, setCall] = useState<VoiceCall | null>(null);
  const [callPhase, setCallPhase] = useState<CallPhase>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isMicMuted, setIsMicMuted] = useState(false);
  const [isSpeakerMuted, setIsSpeakerMuted] = useState(false);
  const [wantsRecording, setWantsRecording] = useState(false);
  const [isRecordingActive, setIsRecordingActive] = useState(false);
  const [savedRecordingReference, setSavedRecordingReference] = useState<string | null>(null);
  const [manualDraft, setManualDraft] = useState("");
  // A real (non-"no_speech") recognition failure — permission denied, no
  // network, no mic hardware, or unknown. Section 27: "voice failures must
  // explain microphone, network, or audio-state problems," so this drives
  // a specific visible message plus the manual composer, rather than the
  // call silently going quiet. "no_speech" (an ordinary pause) never sets
  // this — see startListening's onEnd handler below.
  const [speechErrorReason, setSpeechErrorReason] = useState<SpeechErrorReason | null>(null);
  // Defaults to the profile's standing preference, but — unlike text chat —
  // a call can be started in a different language just for this call
  // without changing that global preference (section 13 explicitly asks
  // for a "mixed" Telugu-English option, which a Profile can never itself
  // be set to). See the language selector in the setup screen below.
  const [selectedLanguage, setSelectedLanguage] = useState<CallLanguage>(
    (user?.profile?.preferred_language as CallLanguage | undefined) ?? "en",
  );

  const recognizerRef = useRef<SpeechRecognizer | null>(null);
  const recognizerGenerationRef = useRef(0);
  // Set by onError, consumed by onEnd (which always fires after onerror in
  // the Web Speech API) — lets onEnd decide whether this was an ordinary
  // "no_speech" pause (silently restart) or a real failure (surface it,
  // don't auto-retry). Not component state: it's read-and-cleared within a
  // single recognizer lifecycle, never rendered directly.
  const lastSpeechErrorRef = useRef<SpeechErrorReason | null>(null);
  const activeRecordingRef = useRef<ActiveRecording | null>(null);
  const recordingStartedAtRef = useRef<Date | null>(null);
  const isMicMutedRef = useRef(isMicMuted);
  const isSpeakerMutedRef = useRef(isSpeakerMuted);
  const screenRef = useRef(screen);
  // Breaks the startListening <-> handleFinalTranscript circular reference
  // without either depending on component state for correctness.
  const handleFinalTranscriptRef = useRef<(text: string, activeCall: VoiceCall) => void>(() => {});
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    isMicMutedRef.current = isMicMuted;
  }, [isMicMuted]);
  useEffect(() => {
    isSpeakerMutedRef.current = isSpeakerMuted;
  }, [isSpeakerMuted]);
  useEffect(() => {
    screenRef.current = screen;
  }, [screen]);

  useEffect(() => {
    registerSpeechAudio(audioRef.current);
    return () => registerSpeechAudio(null);
  }, []);

  const language: CallLanguage = selectedLanguage;
  const sttSupported = isSpeechRecognitionSupported();
  const recordingSupported = isRecordingSupported();

  // ---- Call timer ----
  useEffect(() => {
    if (screen !== "active" || !call) return;
    const startedAt = new Date(call.started_at).getTime();
    const interval = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(interval);
  }, [screen, call]);

  const stopListening = useCallback(() => {
    // Invalidate every callback belonging to the current recognizer before
    // stopping it. Web Speech may fire onerror/onend asynchronously.
    recognizerGenerationRef.current += 1;
    const recognizer = recognizerRef.current;
    recognizerRef.current = null;
    recognizer?.stop();
  }, []);

  const startListening = useCallback(
    (activeCall: VoiceCall) => {
      if (!sttSupported || isMicMutedRef.current || screenRef.current !== "active") return;

      stopListening();
      const generation = recognizerGenerationRef.current;
      setCallPhase("listening");
      setInterimTranscript("");
      lastSpeechErrorRef.current = null;
      let finalHandled = false;

      try {
        const recognizer = createSpeechRecognizer(language, {
          onInterimResult: (text) => {
            if (generation === recognizerGenerationRef.current && !finalHandled) {
              setInterimTranscript(text);
            }
          },
          onFinalResult: (text) => {
            if (generation !== recognizerGenerationRef.current || finalHandled) return;
            finalHandled = true;
            setSpeechErrorReason(null);
            handleFinalTranscriptRef.current(text, activeCall);
          },
          onError: (reason) => {
            if (generation === recognizerGenerationRef.current && !finalHandled) {
              lastSpeechErrorRef.current = reason;
            }
          },
          onEnd: () => {
            if (generation !== recognizerGenerationRef.current) return;
            const reason = lastSpeechErrorRef.current;
            lastSpeechErrorRef.current = null;

            if (finalHandled) return;

            if (reason === "no_speech") {
              if (screenRef.current === "active" && !isMicMutedRef.current) {
                window.setTimeout(() => {
                  if (generation === recognizerGenerationRef.current) startListening(activeCall);
                }, 60);
              } else {
                setCallPhase("idle");
              }
              return;
            }

            if (reason) {
              setSpeechErrorReason(reason);
              setCallPhase("idle");
              return;
            }

            // Some Android WebViews stop recognition after a silence or an
            // internal lifecycle event without reporting an error. Re-arm it
            // only if this is still the active generation.
            if (screenRef.current === "active" && !isMicMutedRef.current) {
              window.setTimeout(() => {
                if (generation === recognizerGenerationRef.current) startListening(activeCall);
              }, 60);
            }
          },
        });

        recognizerRef.current = recognizer;
        recognizer.start();
      } catch (error) {
        recognizerRef.current = null;
        console.error("Unable to start speech recognition", error);
        setSpeechErrorReason("audio_capture");
        setCallPhase("idle");
      }
    },
    [sttSupported, language, stopListening],
  );

  const handleFinalTranscript = useCallback(
    async (text: string, activeCall: VoiceCall) => {
      stopListening();
      setInterimTranscript("");
      if (!text.trim()) {
        if (screenRef.current === "active" && !isMicMutedRef.current) startListening(activeCall);
        return;
      }

      setCallPhase("processing");

      try {
        const exchange = await conversationsApi.sendMessage(activeCall.conversation_id, text);
        if (screenRef.current !== "active") return;

        if (!isSpeakerMutedRef.current) {
          setCallPhase("speaking");
          await speak(exchange.assistant_message.content, language);
        }

        if (screenRef.current === "active" && !isMicMutedRef.current) {
          startListening(activeCall);
        } else {
          setCallPhase("idle");
        }
      } catch (error) {
        console.error("Voice conversation turn failed", error);
        setCallPhase("idle");
        if (screenRef.current === "active" && !isMicMutedRef.current) {
          setSpeechErrorReason("network");
        }
      }
    },
    [stopListening, startListening, language],
  );

  useEffect(() => {
    handleFinalTranscriptRef.current = handleFinalTranscript;
  }, [handleFinalTranscript]);

  // ---- Starting the call ----
  const startCall = useCallback(async () => {
    setScreen("starting");
    screenRef.current = "starting";
    setSpeechErrorReason(null);
    stopListening();
    stopSpeaking();
    await unlockSpeechAudio();
    try {
      const created = await callsApi.start({ language, recording_enabled: wantsRecording });
      setCall(created);
      setElapsedSeconds(0);
      // Keep the ref in sync immediately. React state effects run later, and
      // startListening intentionally checks this ref to prevent stale
      // recognizer callbacks from starting after a call has ended.
      screenRef.current = "active";
      setScreen("active");

      if (wantsRecording && recordingSupported) {
        try {
          const recording = await startRecording();
          activeRecordingRef.current = recording;
          recordingStartedAtRef.current = new Date();
          setIsRecordingActive(true);
        } catch {
          // Mic permission denied or otherwise unavailable for recording
          // specifically — the call itself still proceeds. No fabricated
          // "recording started" state.
          setIsRecordingActive(false);
        }
      }

      setCallPhase("idle");
      if (sttSupported) {
        startListening(created);
      }
    } catch {
      setScreen("error");
    }
  }, [language, wantsRecording, recordingSupported, sttSupported, startListening, stopListening]);

  // ---- Ending the call ----
  const endCall = useCallback(async () => {
    if (!call) return;
    setScreen("ending");
    screenRef.current = "ending";
    stopListening();
    stopSpeaking();

    let recordingReference: string | null = null;
    let recordingDurationSeconds: number | null = null;
    if (activeRecordingRef.current) {
      try {
        const { blob, mimeType } = await activeRecordingRef.current.stop();
        const startedAt = recordingStartedAtRef.current ?? new Date();
        recordingReference = await saveRecordingLocally(blob, mimeType, startedAt);
        recordingDurationSeconds = Math.round((Date.now() - startedAt.getTime()) / 1000);
        setSavedRecordingReference(recordingReference);
      } catch {
        // Stopping/saving failed — the call still ends cleanly; no
        // recording metadata is reported rather than a fabricated one.
      }
      activeRecordingRef.current = null;
    }

    try {
      const ended = await callsApi.end(call.id, {
        ...(recordingReference ? { recording_local_reference: recordingReference } : {}),
        ...(recordingDurationSeconds !== null ? { recording_duration_seconds: recordingDurationSeconds } : {}),
      });
      setCall(ended);
    } catch {
      // Even if reporting the end-of-call metadata fails, the call is over
      // from the user's perspective — show the ended screen regardless.
    }
    setScreen("ended");
  }, [call, stopListening]);

  // Release mic/recognizer/speech on unmount regardless of how the screen
  // was left (navigating away mid-call, browser back button, etc.) — a
  // hot microphone left running after the user leaves the screen would be
  // exactly the kind of unclear recording state section 13 rules out.
  useEffect(() => {
    return () => {
      recognizerRef.current?.stop();
      stopSpeaking();
      if (activeRecordingRef.current) {
        void activeRecordingRef.current.stop();
      }
    };
  }, []);

  function toggleMic() {
    const next = !isMicMutedRef.current;
    isMicMutedRef.current = next;
    setIsMicMuted(next);

    if (next) {
      stopListening();
      setCallPhase("idle");
      return;
    }

    if (screenRef.current === "active" && call) {
      setSpeechErrorReason(null);
      startListening(call);
    }
  }

  function toggleSpeaker() {
    const next = !isSpeakerMutedRef.current;
    isSpeakerMutedRef.current = next;
    setIsSpeakerMuted(next);

    if (next) {
      stopSpeaking();
      if (screenRef.current === "active" && call && !isMicMutedRef.current) {
        startListening(call);
      }
    }
  }

  function retryVoice() {
    if (!call) return;
    setSpeechErrorReason(null);
    if (!isMicMutedRef.current && screenRef.current === "active") {
      startListening(call);
    }
  }

  async function handleManualSend(event: FormEvent) {
    event.preventDefault();
    if (!manualDraft.trim() || !call) return;
    const text = manualDraft.trim();
    setManualDraft("");
    await handleFinalTranscript(text, call);
  }

  const glyphPhase: GlyphPhase =
    callPhase === "listening"
      ? "listening"
      : callPhase === "processing"
        ? "processing"
        : callPhase === "speaking"
          ? "speaking"
          : "idle";

  return (
    <main className="call-screen">
      <audio ref={audioRef} aria-hidden="true" playsInline />
      {screen === "setup" && (
        <div className="call-screen__setup">
          <CallGlyph phase="idle" />
          <h1>{t("call.title")}</h1>
          {!sttSupported && <p className="call-screen__note">{t("call.noVoiceSupportNote")}</p>}
          <div className="call-screen__language-select">
            <span>{t("call.languageLabel")}</span>
            <div className="call-screen__language-options">
              {(["en", "te", "mixed"] as CallLanguage[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`call-screen__language-option ${
                    selectedLanguage === option ? "call-screen__language-option--active" : ""
                  }`}
                  onClick={() => setSelectedLanguage(option)}
                >
                  {t(`call.language.${option}`)}
                </button>
              ))}
            </div>
          </div>
          {recordingSupported && (
            <label className="call-screen__recording-toggle">
              <input
                type="checkbox"
                checked={wantsRecording}
                onChange={(event) => setWantsRecording(event.target.checked)}
              />
              {t("call.enableRecording")}
            </label>
          )}
          <button type="button" className="call-screen__start-button" onClick={() => void startCall()}>
            {t("call.startCall")}
          </button>
          <button type="button" className="call-screen__cancel-link" onClick={() => navigate("/")}>
            {t("common.cancel")}
          </button>
        </div>
      )}

      {screen === "starting" && (
        <div className="call-screen__setup">
          <CallGlyph phase="idle" />
          <p className="empty-state">{t("common.loading")}</p>
        </div>
      )}

      {screen === "error" && (
        <div className="call-screen__setup">
          <p className="empty-state empty-state--error">{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void startCall()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {(screen === "active" || screen === "ending") && call && (
        <div className="call-screen__active">
          <div className="call-screen__header">
            <span className="call-screen__caller">{t("call.callerName")}</span>
            <span className="call-screen__timer">{formatTimer(elapsedSeconds)}</span>
            {isRecordingActive && (
              <span className="call-screen__recording-indicator" aria-label={t("call.recordingIndicator")}>
                ● {t("call.recordingIndicator")}
              </span>
            )}
          </div>

          <CallGlyph phase={glyphPhase} />

          <p className="call-screen__status">
            {callPhase === "listening" && (interimTranscript || t("call.listening"))}
            {callPhase === "processing" && t("call.thinking")}
            {callPhase === "speaking" && t("call.speaking")}
            {callPhase === "idle" && !speechErrorReason && t("call.idle")}
          </p>

          {speechErrorReason && (
            <div className="call-screen__speech-error" role="alert">
              <p>{t(`call.speechError.${speechErrorReason}`)}</p>
              {sttSupported && speechErrorReason !== "permission_denied" && speechErrorReason !== "audio_capture" && (
                <button type="button" onClick={retryVoice}>
                  {t("call.tryVoiceAgain")}
                </button>
              )}
            </div>
          )}

          {(!sttSupported || speechErrorReason) && (
            <form onSubmit={handleManualSend} className="call-screen__manual-composer">
              <input
                type="text"
                value={manualDraft}
                onChange={(event) => setManualDraft(event.target.value)}
                placeholder={t("talk.composerPlaceholder")}
              />
              <button type="submit" disabled={!manualDraft.trim()}>
                {t("talk.send")}
              </button>
            </form>
          )}

          <div className="call-screen__controls">
            {sttSupported && (
              <button
                type="button"
                className={`call-screen__control ${isMicMuted ? "call-screen__control--muted" : ""}`}
                onClick={toggleMic}
              >
                {isMicMuted ? t("call.unmute") : t("call.mute")}
              </button>
            )}
            <button
              type="button"
              className={`call-screen__control ${isSpeakerMuted ? "call-screen__control--muted" : ""}`}
              onClick={toggleSpeaker}
            >
              {isSpeakerMuted ? t("call.speakerOff") : t("call.speakerOn")}
            </button>
            <button
              type="button"
              className="call-screen__end-button"
              disabled={screen === "ending"}
              onClick={() => void endCall()}
            >
              {t("call.endCall")}
            </button>
          </div>
        </div>
      )}

      {screen === "ended" && call && (
        <div className="call-screen__setup">
          <CallGlyph phase="idle" />
          <h1>{t("call.callEnded")}</h1>
          <p className="call-screen__summary">
            {t("call.callDuration")}: {formatTimer(call.duration_seconds ?? elapsedSeconds)}
          </p>
          {savedRecordingReference && <p className="call-screen__summary">{t("call.recordingSaved")}</p>}
          <button type="button" className="call-screen__start-button" onClick={() => navigate("/")}>
            {t("nav.home")}
          </button>
        </div>
      )}
    </main>
  );
}
