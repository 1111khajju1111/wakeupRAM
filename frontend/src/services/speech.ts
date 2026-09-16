import { voiceApi } from "./domainApi";

/**
 * Voice adapters for Wake Up Ram.
 *
 * STT uses the browser/WebView SpeechRecognition API.
 * TTS uses the authenticated backend Google/Gemini adapter first, with browser
 * SpeechSynthesis as a desktop fallback. Playback is kept on one persistent
 * HTMLAudioElement so Android/WebView output is predictable and can be
 * stopped immediately when the user mutes the speaker or ends a call.
 */
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
}

interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  }
}

export type CallLanguage = "en" | "te" | "mixed";

const RECOGNITION_LOCALE: Record<CallLanguage, string> = {
  en: "en-US",
  te: "te-IN",
  mixed: "en-IN",
};

export function isSpeechRecognitionSupported(): boolean {
  return typeof window !== "undefined" && !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export type SpeechErrorReason = "permission_denied" | "network" | "no_speech" | "audio_capture" | "unknown";

function normalizeRecognitionError(rawError: string): SpeechErrorReason | null {
  switch (rawError) {
    case "not-allowed":
    case "service-not-allowed":
      return "permission_denied";
    case "network":
      return "network";
    case "no-speech":
      return "no_speech";
    case "audio-capture":
      return "audio_capture";
    case "aborted":
      return null;
    default:
      return "unknown";
  }
}

export interface SpeechRecognizerHandlers {
  onInterimResult?: (transcript: string) => void;
  onFinalResult: (transcript: string) => void;
  onError?: (reason: SpeechErrorReason) => void;
  onEnd?: () => void;
}

export interface SpeechRecognizer {
  start(): void;
  stop(): void;
}

export function createSpeechRecognizer(
  language: CallLanguage,
  handlers: SpeechRecognizerHandlers,
): SpeechRecognizer {
  const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
  if (!Ctor) throw new Error("SpeechRecognition is not supported in this environment.");

  const recognition = new Ctor();
  recognition.lang = RECOGNITION_LOCALE[language];
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      const transcript = result[0].transcript.trim();
      if (!transcript) continue;
      if (result.isFinal) handlers.onFinalResult(transcript);
      else handlers.onInterimResult?.(transcript);
    }
  };

  recognition.onerror = (event) => {
    const reason = normalizeRecognitionError(event.error);
    if (reason) handlers.onError?.(reason);
  };

  recognition.onend = () => handlers.onEnd?.();

  return {
    start: () => recognition.start(),
    stop: () => {
      try {
        recognition.stop();
      } catch {
        // Browser/WebView can throw InvalidStateError when it has already
        // ended. Stopping the call must remain idempotent.
      }
    },
  };
}

let activeAudio: HTMLAudioElement | null = null;
let activeAudioUrl: string | null = null;
let audioUnlocked = false;
let playbackGeneration = 0;

export function registerSpeechAudio(audio: HTMLAudioElement | null): void {
  if (activeAudio && activeAudio !== audio) {
    try { activeAudio.pause(); } catch { /* noop */ }
    activeAudio.removeAttribute("src");
    activeAudio.load();
  }
  activeAudio = audio;
  audioUnlocked = false;
  if (!audio) return;

  audio.preload = "auto";
  audio.autoplay = false;
  audio.controls = false;
  audio.muted = false;
  audio.volume = 1;
  audio.setAttribute("playsinline", "true");
}

/** Prime the persistent audio element during the user's Start Call gesture. */
export async function unlockSpeechAudio(): Promise<void> {
  if (!activeAudio || audioUnlocked) return;

  const audio = activeAudio;
  const silentWav =
    "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=";

  try {
    audio.src = silentWav;
    audio.muted = true;
    await audio.play();
    audio.pause();
    audio.currentTime = 0;
    audio.muted = false;
    audio.removeAttribute("src");
    audio.load();
    audioUnlocked = true;
  } catch {
    audio.muted = false;
    audio.removeAttribute("src");
    audio.load();
    // Browser policy may refuse autoplay. TTS will still try normal playback.
    audioUnlocked = false;
  }
}

/**
 * Speak one assistant response. Calling stopSpeaking invalidates the current
 * playback even if the network request is still in flight.
 */
export async function speak(text: string, language: CallLanguage, onEnd?: () => void): Promise<void> {
  const cleanText = text.trim();
  if (!cleanText) {
    onEnd?.();
    return;
  }

  const generation = ++playbackGeneration;
  stopActiveAudio(false);

  try {
    const blob = await voiceApi.tts(cleanText, language);
    if (generation !== playbackGeneration) return;

    if (activeAudio) {
      const audio = activeAudio;
      const url = URL.createObjectURL(blob);
      activeAudioUrl = url;
      audio.src = url;
      audio.currentTime = 0;
      audio.muted = false;
      audio.volume = 1;

      await new Promise<void>((resolve, reject) => {
        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          resolve();
        };
        const fail = () => {
          if (settled) return;
          settled = true;
          reject(new Error("Audio playback failed."));
        };
        audio.onended = finish;
        audio.onerror = fail;
        void audio.play().catch(fail);
      });

      if (generation === playbackGeneration) onEnd?.();
      return;
    }

    throw new Error("No persistent audio element is registered.");
  } catch (backendError) {
    if (generation !== playbackGeneration) return;

    // Desktop fallback only. Android/Capacitor should use backend audio.
    if (isSpeechSynthesisSupported()) {
      await new Promise<void>((resolve) => {
        if (generation !== playbackGeneration) return resolve();
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = RECOGNITION_LOCALE[language];
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      });
      if (generation === playbackGeneration) onEnd?.();
      return;
    }

    throw backendError;
  } finally {
    if (generation === playbackGeneration && activeAudioUrl) {
      URL.revokeObjectURL(activeAudioUrl);
      activeAudioUrl = null;
      if (activeAudio) {
        activeAudio.onended = null;
        activeAudio.onerror = null;
        activeAudio.removeAttribute("src");
        activeAudio.load();
      }
    }
  }
}

function stopActiveAudio(invalidate: boolean): void {
  if (invalidate) playbackGeneration += 1;
  if (isSpeechSynthesisSupported()) window.speechSynthesis.cancel();
  if (activeAudio) {
    try { activeAudio.pause(); } catch { /* noop */ }
    activeAudio.onended = null;
    activeAudio.onerror = null;
    activeAudio.removeAttribute("src");
    activeAudio.load();
  }
  if (activeAudioUrl) {
    URL.revokeObjectURL(activeAudioUrl);
    activeAudioUrl = null;
  }
}

export function stopSpeaking(): void {
  stopActiveAudio(true);
}
