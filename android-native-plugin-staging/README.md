# Native call-recording plugin — staged, unverified

This folder is deliberately **outside** `frontend/src`. Nothing in here is
wired into the app, and nothing already-verified (`callRecorder.ts`,
`CallScreen.tsx`) has been touched to accommodate it. That's intentional:
`CallRecorderNativePlugin.kt` has never been compiled — this sandbox has no
`javac`, no Gradle, no Android SDK — so it doesn't belong mixed in with
code that's actually been checked.

## What this closes

The one honestly-open Phase 11 audio gap: `callRecorder.ts`'s WebView
`MediaRecorder` can only produce `.webm`/`.ogg`, never section 13's
`.m4a`. `CallRecorderNativePlugin.kt` uses Android's native
`MediaRecorder` with `OutputFormat.MPEG_4` + `AudioEncoder.AAC`, which is
what genuinely produces `.m4a` — not a renamed webm file.

## Before trusting this file

Written by reading Capacitor's documented Android plugin API
(`@CapacitorPlugin`, `PluginCall`, the `@Permission`/`getPermissionState`/
`requestPermissionForAlias`/`@PermissionCallback` runtime-permission
pattern) and Android's `MediaRecorder` API from memory, cross-checked
against each other for consistency, but **never compiled against real
`capacitor-android` classes**. Likely-correct, not confirmed-correct.
Before relying on it:

1. Generate `android/` for real (`scripts/generate-android.sh`, or
   `npx cap add android` by hand).
2. Confirm the actual generated package name — check
   `android/app/build.gradle`'s `applicationId` and
   `android/app/src/main/java/**/MainActivity.java`'s `package` line.
   This file assumes `com.wakeupram.app` (matching `capacitor.config.ts`'s
   `appId`), but confirm against the generated project rather than this
   comment.
3. Move this file to
   `android/app/src/main/java/com/wakeupram/app/CallRecorderNativePlugin.kt`
   (adjusting the path to the real package if step 2 found something
   different).
4. Register the plugin in the generated `MainActivity` — Capacitor's
   documented pattern is calling `registerPlugin()` **before**
   `super.onCreate()`:
   ```java
   package com.wakeupram.app;

   import android.os.Bundle;
   import com.getcapacitor.BridgeActivity;

   public class MainActivity extends BridgeActivity {
       @Override
       public void onCreate(Bundle savedInstanceState) {
           registerPlugin(CallRecorderNativePlugin.class);
           super.onCreate(savedInstanceState);
       }
   }
   ```
5. Build (`./gradlew assembleDebug` or Android Studio) and actually fix
   whatever the compiler says needs fixing — treat this file as a draft
   that needs that pass, not a finished artifact.
6. Only after it compiles and records a real file on a device/emulator,
   wire the JS side in — see `callRecorder.native-bridge.example.ts` in
   this same folder for exactly how that call site would look. That
   example is equally unverified and equally not wired into
   `frontend/src` yet, for the same reason.

## Why not just wire it in now and mark it "best-effort"

Because `callRecorder.ts` currently has a documented, honest gap
(webm/ogg instead of m4a) — a known, bounded shortcoming. Splicing in a
call to an uncompiled native method would trade that for an *unknown*
one: a runtime crash, a silent no-op, or a build failure, discovered only
whenever someone finally builds `android/` for the first time, at a point
where it's harder to tell which of several new things broke it. Keeping
this staged and separate means the day someone builds `android/` for the
first time, this is the one new, clearly-labeled thing to compile and
verify — not one of several changes tangled into files that were
previously trustworthy.
