/**
 * Local call recording (section 13): user-controlled, on-device by
 * default, no automatic upload — this module never sends audio anywhere,
 * only ever produces a local Blob and writes/saves it locally.
 *
 * `saveRecordingLocally` branches on `Capacitor.isNativePlatform()`, same
 * pattern as `nativeNotifications.ts`:
 *   - **Native (Android/Capacitor)**: writes the actual file via
 *     `@capacitor/filesystem`, under `Directory.Data` — Capacitor's
 *     app-private internal storage directory (deleted on uninstall, no
 *     runtime permission prompt needed on any Android version). This is a
 *     deliberate choice, not the more obvious-sounding `Directory.Documents`:
 *     that one is actually the *public* Documents folder on Android,
 *     visible to other apps, and requires either the legacy-external-storage
 *     manifest flag (Android 10) or an explicit runtime permission request
 *     (`Filesystem.requestPermissions()`) before every write — worth reading
 *     the plugin's own type definitions closely here, since the name alone
 *     suggests the opposite of what it does. `Directory.Data` keeps a
 *     user's call recordings genuinely private to this app, matching
 *     section 21's "protect sensitive local files where practical" and the
 *     master prompt's design-decision ordering ("security... then visual
 *     polish"), with no extra permission plumbing required. The file is
 *     still genuinely local-only, still never uploaded, and still under the
 *     `Wake Up Ram/Calls/YYYY-MM-DD/HH-MM-SS.<ext>` structure section 13
 *     suggests — just under the app's own private storage root rather than
 *     a shared public folder.
 *   - **Web (dev/browser, not under Capacitor)**: no Filesystem API exists,
 *     so this falls back to a browser download — same behavior as before
 *     this file had native support at all.
 *
 * Honest gap that this change does NOT close: the container format.
 * `MediaRecorder` (in `startRecording` below) produces webm/ogg on every
 * platform Capacitor's WebView runs on — real `.m4a` capture needs a
 * native audio-recording plugin (there's no MediaRecorder-to-m4a
 * transcoding happening here, and adding one is a separate, non-trivial
 * follow-up, not something to fake by just renaming the file extension).
 * So even after this native-storage change, a completed call's recording
 * is a genuinely local, correctly-placed, but `.webm`/`.ogg` file — the
 * naming *structure* matches section 13, the file *extension* honestly
 * doesn't yet.
 */
import { Capacitor } from "@capacitor/core";
import { Directory, Filesystem } from "@capacitor/filesystem";

export function isRecordingSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof window !== "undefined" &&
    "MediaRecorder" in window
  );
}

export interface ActiveRecording {
  stop(): Promise<{ blob: Blob; durationSeconds: number; mimeType: string }>;
}

export async function startRecording(): Promise<ActiveRecording> {
  if (!isRecordingSupported()) {
    throw new Error("Recording is not supported in this environment.");
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/ogg";
  const recorder = new MediaRecorder(stream, { mimeType });
  const chunks: BlobPart[] = [];
  const startedAt = Date.now();

  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };

  recorder.start();

  return {
    stop: () =>
      new Promise((resolve) => {
        recorder.onstop = () => {
          stream.getTracks().forEach((track) => track.stop());
          const durationSeconds = Math.round((Date.now() - startedAt) / 1000);
          resolve({ blob: new Blob(chunks, { type: mimeType }), durationSeconds, mimeType });
        };
        recorder.stop();
      }),
  };
}

/** `Filesystem.writeFile` takes base64 data (no `encoding` given means
 * binary), not a Blob directly — this converts via FileReader rather than
 * a manual byte-to-base64 loop, since FileReader.readAsDataURL is the
 * standard, well-supported way to do this in a WebView. */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Unexpected FileReader result type."));
        return;
      }
      // result is "data:<mime>;base64,<data>" — Filesystem.writeFile wants
      // just <data>.
      const commaIndex = result.indexOf(",");
      resolve(commaIndex === -1 ? result : result.slice(commaIndex + 1));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read recording data."));
    reader.readAsDataURL(blob);
  });
}

/** Saves the recording locally — natively via Filesystem on Android,
 * or a browser download otherwise — using the naming convention from
 * section 13, and returns the reference string reported back to the
 * backend as VoiceCall.recording_local_reference. The backend never
 * receives the audio itself, only this text reference, on either path. */
export async function saveRecordingLocally(blob: Blob, mimeType: string, startedAt: Date): Promise<string> {
  const extension = mimeType.includes("ogg") ? "ogg" : "webm";
  const datePart = startedAt.toISOString().slice(0, 10);
  const timePart = startedAt.toTimeString().slice(0, 8).replace(/:/g, "-");
  const reference = `Wake Up Ram/Calls/${datePart}/${timePart}.${extension}`;

  if (Capacitor.isNativePlatform()) {
    const base64Data = await blobToBase64(blob);
    await Filesystem.writeFile({
      path: reference,
      data: base64Data,
      directory: Directory.Data,
      recursive: true,
    });
    return reference;
  }

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${datePart}_${timePart}.${extension}`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);

  return reference;
}
