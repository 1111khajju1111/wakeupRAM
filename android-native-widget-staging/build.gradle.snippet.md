# Changes needed in android/app/build.gradle

## 1. New dependency (the only one this widget needs)

In the `dependencies { ... }` block:

    implementation "androidx.work:work-runtime:2.9.1"

Deliberately `work-runtime`, not `work-runtime-ktx` — the Worker here
(CountdownWidgetUpdateWorker) is a plain `Worker` subclass, not a
`CoroutineWorker`, specifically to avoid also needing
kotlinx-coroutines-android as a transitive dependency. If coroutines are
already in this project for other reasons by the time this is integrated,
switching to work-runtime-ktx + CoroutineWorker is a reasonable
simplification — just isn't necessary for this to work.

## 2. API base URL — config-driven, not hardcoded

The JS frontend gets its backend URL from `VITE_API_BASE_URL` (a
build-time Vite env var — see frontend/src/services/apiClient.ts). Native
Kotlin code has no access to that; it needs its own equivalent so
CountdownApiClient.kt's `BuildConfig.API_BASE_URL` reference resolves to
something real rather than being hardcoded in the .kt file itself (which
section 22 explicitly rules out for production URLs).

In `android { defaultConfig { ... } }`, inside the generated build.gradle:

    buildConfigField "String", "API_BASE_URL", "\"${project.findProperty('apiBaseUrl') ?: 'http://10.0.2.2:8000'}\""

And in `android { ... }` (sibling to defaultConfig), if not already present:

    buildFeatures {
        buildConfig true
    }

`project.findProperty('apiBaseUrl')` reads from `android/local.properties`
(gitignored — see the root .gitignore added in a previous pass) or a
`-PapiBaseUrl=...` command-line flag, so the real production URL never
needs to be committed. `10.0.2.2` is the Android emulator's alias for the
host machine's `localhost` — a sensible default for local development
against `uvicorn` running on the host, matching what `VITE_API_BASE_URL`'s
own fallback effectively does for the web build. For a real device (not
emulator) hitting a local backend, override via local.properties with the
host machine's LAN IP instead; for a Render-deployed backend, override
with that URL.

Add to `android/local.properties` (never committed — already covered by
the root `.gitignore`'s `frontend/android/local.properties` line):

    apiBaseUrl=https://your-backend.onrender.com
