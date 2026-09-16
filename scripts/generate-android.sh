#!/usr/bin/env bash
#
# Generates the real Capacitor Android project for Wake Up Ram and patches
# its manifest with the permissions Phase 11's JS/TS side already relies on.
#
# Why this script exists instead of a checked-in android/ directory:
# `npx cap add android` needs to download @capacitor/android's template
# and Gradle wrapper jars from the npm registry, then have Capacitor CLI
# read this project's actual package.json/capacitor.config.ts to generate
# a matching native project. No sandbox without real npm/Java/Gradle
# access can do that faithfully — hand-authoring the output risks
# subtly-wrong Gradle/manifest content that looks plausible but doesn't
# build. This script runs the real generator; it does not replace it.
#
# Run this from frontend/ with real network + npm + Java + Gradle access:
#   bash ../scripts/generate-android.sh
#
# It is safe to re-run: every step is idempotent (npm install is always
# idempotent; `cap add android` is skipped if android/ already exists —
# use `npx cap sync android` directly if you just want to pull in a
# package.json change; the manifest patch checks for each permission
# line before adding it).

set -euo pipefail

if [ ! -f "package.json" ] || [ ! -f "capacitor.config.ts" ]; then
  echo "Run this from the frontend/ directory (needs package.json + capacitor.config.ts)." >&2
  exit 1
fi

for cmd in node npm npx java; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required tool: $cmd" >&2
    exit 1
  fi
done

echo "==> Installing dependencies"
npm install

echo "==> Building web bundle (capacitor.config.ts webDir: dist)"
npm run build

if [ -d "android" ]; then
  echo "==> android/ already exists, syncing instead of re-adding"
  npx cap sync android
else
  echo "==> Generating native Android project (npx cap add android)"
  npx cap add android
  npx cap sync android
fi

MANIFEST="android/app/src/main/AndroidManifest.xml"
if [ ! -f "$MANIFEST" ]; then
  echo "Expected manifest not found at $MANIFEST — cap add android may have failed above." >&2
  exit 1
fi

echo "==> Patching $MANIFEST with required permissions"

# Each permission is a single self-closing line; adding it just before
# </manifest> is valid regardless of where Capacitor's template puts the
# <application> block. grep -qF (fixed string) both checks presence and
# avoids treating the permission string as a regex.
add_permission() {
  local perm_line="$1"
  if grep -qF "$perm_line" "$MANIFEST"; then
    echo "    already present: $perm_line"
  else
    # Insert before the closing </manifest> tag.
    local tmp
    tmp="$(mktemp)"
    sed "s#</manifest>#    ${perm_line}\n</manifest>#" "$MANIFEST" > "$tmp"
    mv "$tmp" "$MANIFEST"
    echo "    added: $perm_line"
  fi
}

# RECORD_AUDIO: call screen's local recording via getUserMedia/MediaRecorder
# (Phase 9, see src/services/callRecorder.ts).
add_permission '<uses-permission android:name="android.permission.RECORD_AUDIO" />'
# POST_NOTIFICATIONS: required at runtime on Android 13+ for the
# local-notifications bridge (src/services/nativeNotifications.ts), which
# already calls LocalNotifications.requestPermissions() at runtime — this
# manifest line is what makes that runtime prompt possible in the first
# place, not a substitute for it.
add_permission '<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
# INTERNET: Capacitor's default template already includes this; listed
# here too so the script is a complete, idempotent record of what this
# app manifest needs.
add_permission '<uses-permission android:name="android.permission.INTERNET" />'

echo "==> Done. Next steps:"
echo "    npx cap open android      # open in Android Studio, or"
echo "    cd android && ./gradlew assembleDebug   # build a debug APK directly"
