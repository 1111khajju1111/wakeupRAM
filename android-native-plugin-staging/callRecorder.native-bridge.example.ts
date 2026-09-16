// EXAMPLE ONLY — not imported anywhere, not part of the build.
// Shows how `callRecorder.ts` would call CallRecorderNativePlugin.kt
// once that file has actually been compiled and verified (see README.md
// in this folder). Do not copy this into frontend/src until then.

import { registerPlugin } from "@capacitor/core";

interface CallRecorderNativePlugin {
  start(): Promise<{ started: boolean }>;
  stop(): Promise<{ path: string }>;
}

const CallRecorderNative = registerPlugin<CallRecorderNativePlugin>("CallRecorderNative");

// Illustrative only — the real startRecording()/saveRecordingLocally() in
// callRecorder.ts would gain a native-first branch something like:
//
//   if (Capacitor.isNativePlatform()) {
//     await CallRecorderNative.start();
//     // ... later, on call end:
//     const { path } = await CallRecorderNative.stop();
//     return path; // already a real on-device .m4a path — no blob/base64
//                  // round-trip needed, unlike the current
//                  // Filesystem.writeFile path for the WebView recorder.
//   }
//   // existing WebView MediaRecorder → webm/ogg path stays as the
//   // non-native (web/dev) fallback, unchanged.
