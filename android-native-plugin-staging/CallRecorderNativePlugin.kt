// STAGED, UNVERIFIED SOURCE — see README.md in this same folder before
// touching this file. No javac/Gradle/Android SDK exists in the sandbox
// that wrote this, so this has been reviewed by eye against Capacitor's
// documented plugin API and Android's MediaRecorder API, but never
// compiled. Treat it as a strong first draft, not finished work.
//
// Purpose: close the one remaining Phase-11 audio gap once android/
// exists — real `.m4a` output via Android's native MediaRecorder
// (MPEG_4 container + AAC encoder is literally what produces .m4a; this
// is not a renamed webm/ogg file the way a lazier fix might be tempted
// to do), replacing the WebView MediaRecorder path in
// src/services/callRecorder.ts for native builds only. Web/dev keeps
// using the existing getUserMedia/MediaRecorder → webm/ogg path
// unchanged — this plugin has no effect there.
//
// Once android/ exists, this file's real home is:
//   android/app/src/main/java/com/wakeupram/app/CallRecorderNativePlugin.kt
// (package name must match whatever applicationId/package
// `npx cap add android` actually generated from capacitor.config.ts's
// appId — check android/app/build.gradle's applicationId and
// android/app/src/main/java/<path>/MainActivity.java's package line
// before assuming "com.wakeupram.app" is exactly right; capacitor.config.ts
// says appId "com.wakeupram.app" so it should match, but confirm against
// the generated file rather than trusting this comment.)

package com.wakeupram.app

import android.Manifest
import android.media.MediaRecorder
import android.os.Build
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback
import com.getcapacitor.PermissionState
import java.io.File

/**
 * Native call recording, producing genuine .m4a files via
 * MediaRecorder(OutputFormat.MPEG_4, AudioEncoder.AAC) — matching
 * section 13's "Wake Up Ram/Calls/YYYY-MM-DD/HH-MM-SS.m4a" naming
 * exactly, unlike the WebView MediaRecorder fallback this replaces on
 * native, which can only produce webm/ogg.
 *
 * Files are written under the app's private files directory
 * (getContext().filesDir), matching the same Directory.Data-equivalent
 * privacy choice callRecorder.ts already made on the JS side for the
 * Filesystem-backed path (see that file's docstring for the
 * Directory.Documents-vs-Directory.Data reasoning — the same "app-private,
 * no extra permission plumbing" logic applies here).
 *
 * Uses Capacitor's annotation-based runtime permission system
 * (@CapacitorPlugin(permissions=...), getPermissionState/
 * requestPermissionForAlias/@PermissionCallback) rather than checking
 * ContextCompat.checkSelfPermission by hand — this is the documented,
 * stable Capacitor pattern for a plugin's own runtime permission prompt,
 * separate from (and not a replacement for) the RECORD_AUDIO manifest
 * declaration scripts/generate-android.sh already adds.
 */
@CapacitorPlugin(
    name = "CallRecorderNative",
    permissions = [
        Permission(strings = [Manifest.permission.RECORD_AUDIO], alias = "microphone")
    ]
)
class CallRecorderNativePlugin : Plugin() {

    private var recorder: MediaRecorder? = null
    private var outputPath: String? = null

    @PluginMethod
    fun start(call: PluginCall) {
        if (recorder != null) {
            call.reject("A native recording is already in progress.")
            return
        }
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            requestPermissionForAlias("microphone", call, "microphonePermissionCallback")
            return
        }
        beginRecording(call)
    }

    @PermissionCallback
    private fun microphonePermissionCallback(call: PluginCall) {
        if (getPermissionState("microphone") == PermissionState.GRANTED) {
            beginRecording(call)
        } else {
            call.reject("Microphone permission was denied.")
        }
    }

    private fun beginRecording(call: PluginCall) {
        val dir = File(context.filesDir, "wake_up_ram_calls")
        if (!dir.exists() && !dir.mkdirs()) {
            call.reject("Could not create local recordings directory.")
            return
        }
        val file = File(dir, "${System.currentTimeMillis()}.m4a")
        outputPath = file.absolutePath

        // MediaRecorder(Context) is the non-deprecated constructor from
        // API 31 (Android 12) onward; the no-arg constructor is deprecated
        // but still required below that. Both produce an equivalent
        // recorder for this plugin's purposes.
        val mr = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }

        try {
            mr.setAudioSource(MediaRecorder.AudioSource.MIC)
            mr.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            mr.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            mr.setOutputFile(outputPath)
            mr.prepare()
            mr.start()
        } catch (e: Exception) {
            // release() before nulling out — prepare()/start() can throw
            // after partially allocating recorder resources.
            mr.release()
            call.reject("Failed to start native recording: ${e.message}", e)
            return
        }

        recorder = mr
        val result = JSObject()
        result.put("started", true)
        call.resolve(result)
    }

    @PluginMethod
    fun stop(call: PluginCall) {
        val mr = recorder
        val path = outputPath
        if (mr == null || path == null) {
            call.reject("No native recording is in progress.")
            return
        }
        try {
            mr.stop()
        } catch (e: Exception) {
            // stop() throws if called too soon after start() with no audio
            // captured yet — a real condition (e.g. user ends a call
            // instantly), not just a theoretical one, so surface it rather
            // than silently returning a bogus success.
            mr.release()
            recorder = null
            outputPath = null
            call.reject("Failed to stop native recording: ${e.message}", e)
            return
        }
        mr.release()
        recorder = null
        outputPath = null

        val result = JSObject()
        result.put("path", path)
        call.resolve(result)
    }
}
