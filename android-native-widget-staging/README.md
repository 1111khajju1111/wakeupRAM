# Native countdown widget — staged, unverified

Same reasoning as `android-native-plugin-staging/` (Phase 11's call
recorder): nothing here has been compiled — this sandbox still has no
`javac`, no Gradle, no Android SDK, and **`android/` still doesn't exist
in this repo** (confirmed again this pass — no `frontend/android`
directory anywhere in the uploaded project). So this is staged outside
`frontend/` rather than spliced into a project that doesn't exist yet.

## What this is

The master doc's actual Phase 12 (section 29/"ANDROID" in the Claude
Build Prompt): a native home-screen widget showing a countdown, "content
must be dynamic and user-configurable... do not hardcode one countdown."

- `CountdownWidgetProvider.kt` — the `AppWidgetProvider`. Lifecycle only
  (enqueue/cancel WorkManager jobs, clean up prefs on removal) — never
  touches the network directly, since its callbacks run on the main
  thread.
- `CountdownWidgetUpdateWorker.kt` — the only place that calls the
  network or paints `RemoteViews`. Runs on WorkManager's background
  executor, both periodically (every 30 min — see "why 30 minutes" below)
  and once immediately after configuration finishes.
- `CountdownWidgetConfigureActivity.kt` — shown when a user places the
  widget. Fetches their real countdown list
  (`GET /api/v1/countdowns?active_only=true`) and lets them pick a
  specific one, or "always show soonest active"
  (`GET /api/v1/today`'s `active_countdown`) — this is what satisfies
  "user-configurable... do not hardcode one countdown," not a cosmetic
  choice.
- `CountdownWidgetPrefs.kt` — per-placed-instance storage of which
  countdown (or "soonest active") each widget on the home screen shows.
- `CountdownApiClient.kt` — dependency-free HTTP client
  (`HttpURLConnection` + `org.json`, both bundled with the Android SDK)
  against the real, already-built `/api/v1/countdowns`,
  `/api/v1/today`, and `/api/v1/auth/refresh` endpoints — verified
  against those endpoints' actual source files this pass, not guessed.
- `CountdownTimeFormatter.kt` — deliberately mirrors
  `frontend/src/features/countdowns/CountdownsScreen.tsx`'s
  `formatTimeRemaining()` exactly (same day/hour/minute breakpoints, same
  "Overdue" behavior) so a countdown reads identically in the app and on
  the widget.
- `res/` — widget layout, config-screen layout, `AppWidgetProviderInfo`
  metadata, and strings in **both English and Telugu** (matching the
  project's existing bilingual discipline — a native widget can't reach
  the JS i18n system, so it needs its own `values`/`values-te` pair),
  plus light/dark drawables and colors that follow the system theme via
  `-night` qualifiers (section 15's "light theme, dark theme, system
  theme," even at the native layer).
- `AndroidManifest.snippet.xml` — the `<receiver>` and `<activity>`
  entries to merge in.
- `build.gradle.snippet.md` — the one new dependency
  (`androidx.work:work-runtime`) and how the widget gets a real,
  non-hardcoded API base URL via a Gradle `buildConfigField` reading from
  gitignored `local.properties` (mirroring how the JS side reads
  `VITE_API_BASE_URL`) — not a URL baked into the `.kt` file, which
  section 22 rules out.

## Real design decisions worth knowing before integrating

- **Why 30 minutes, not live-ticking:** Android's own
  `AppWidgetProviderInfo` clamps `updatePeriodMillis` below 30 minutes up
  to 30 minutes regardless — a home-screen widget genuinely cannot
  update sub-30-min through the OS's own mechanism. `updatePeriodMillis`
  is set to `0` here specifically to hand the whole job to WorkManager's
  own periodic scheduler instead of running two competing timers. The
  displayed "remaining time" is accurate to within ~30 minutes, not a
  live clock — an honest constraint of the platform, not a shortcut
  taken here.
- **Why a plain `Worker`, not `CoroutineWorker`:** avoids needing
  `kotlinx-coroutines-android` as an additional dependency purely for
  this. `work-runtime` (not `-ktx`) is the one new Gradle line needed —
  see `build.gradle.snippet.md`.
- **Why `AsyncTask` in the configure activity despite being
  deprecated:** dependency-free, and this is a single short-lived fetch
  in a rarely-opened screen — not worth a coroutines/RxJava dependency
  for. Noted as a reasonable-but-not-ideal choice in the file itself; if
  this project already has coroutines wired in by integration time,
  swapping to `lifecycleScope.launch` is a fine simplification.
- **Why the widget reads the app's JWT from Capacitor's own
  `SharedPreferences` rather than having its own login:** a home-screen
  widget has no UI for the user to sign in through, and shouldn't need
  a second credential — it should just use whatever session the app
  itself is already authenticated with. The refresh-on-401 logic in
  `CountdownApiClient.kt` mirrors `frontend/src/services/apiClient.ts`'s
  `tryRefreshToken()` exactly, including the same one-retry guard,
  because with `ACCESS_TOKEN_EXPIRE_MINUTES=30` (current `.env.example`
  value) and a 30-minute widget refresh interval, the widget will
  frequently need to refresh before nearly every fetch — this isn't an
  edge case for this feature, it's close to the common case.

## Before trusting this — the one genuinely uncertain piece

Everything above was checked against this repo's actual source files
(the countdown schemas, `apiClient.ts`, `tokenStorage.ts`, the auth
endpoints). The one thing that could **not** be checked that way:
**`CountdownApiClient.kt`'s `CAPACITOR_PREFS_FILE = "CapacitorStorage"`
constant** — this is Capacitor's documented default SharedPreferences
group name for the `@capacitor/preferences` plugin, from reading
Capacitor's own documentation/behavior from memory, not from inspecting
the actual compiled plugin class (this sandbox has no way to open the
`.aar`/compiled plugin source). Before relying on this widget reading
real login tokens:

1. Once `android/` exists for real (Phase 11, still not done — see
   below), grep
   `frontend/node_modules/@capacitor/preferences/android/**/*.kt` (or
   `.java`, depending on the installed version) for the actual
   `getSharedPreferences(...)` call and confirm the file name matches.
   If it doesn't, that's the one constant to fix — everything else in
   `CountdownApiClient.kt` follows from it correctly once it's right.
2. A quick way to sanity-check without reading plugin source: after
   logging into the app on a device/emulator, pull
   `/data/data/com.wakeupram.app/shared_prefs/` (via `adb shell run-as
   com.wakeupram.app ls shared_prefs/` on a debug build) and look at
   which `.xml` file actually holds `wake_up_ram.auth_tokens`.

## Integration checklist

1. **Finish Phase 11 first.** This widget's `CountdownApiClient.kt`
   depends on Phase 11's token-storage work (`tokenStorage.ts`'s
   Preferences-based storage) actually running on a real device to
   produce a real `SharedPreferences` file to read — there's nothing to
   verify against until `android/` exists and the app has been signed
   into at least once. Confirmed again this pass: no `android/`
   directory in this repo yet.
2. Confirm the real package name the same way
   `android-native-plugin-staging/README.md` describes (check
   `applicationId` in the generated `build.gradle` and `MainActivity`'s
   package line) — every file here assumes `com.wakeupram.app`.
3. Move `CountdownWidgetProvider.kt`, `CountdownWidgetUpdateWorker.kt`,
   `CountdownWidgetConfigureActivity.kt`, `CountdownWidgetPrefs.kt`, and
   `CountdownApiClient.kt` into
   `android/app/src/main/java/com/wakeupram/app/widget/` (adjusting the
   package if step 2 found something different — and adjusting every
   `import com.wakeupram.app.R` accordingly too).
4. Copy everything under `res/` into
   `android/app/src/main/res/` (it merges cleanly — none of these
   filenames should collide with anything `cap add android` generates).
5. Apply `AndroidManifest.snippet.xml`'s `<receiver>` and `<activity>`
   into the real manifest.
6. Apply `build.gradle.snippet.md`'s dependency and `buildConfigField`
   changes.
7. Verify the `CapacitorStorage` constant per the section above.
8. Build, then actually place the widget on a home screen (or emulator
   launcher) and confirm: the configure screen shows real countdowns,
   picking one paints real data within seconds (not up to 30 minutes),
   the empty state shows correctly with zero countdowns, and light/dark
   system theme switching changes the widget's colors.

## Why staged separately, not wired in now

Same reasoning as the Phase 11 plugin: splicing untested Kotlin into a
project that doesn't exist yet would trade a known, bounded gap ("Phase
12 not started") for an unknown one (a build failure discovered whenever
`android/` is finally generated, tangled in with whatever else changed
around it). Keeping this staged means the day `android/` is built for
the first time, this is the one clearly-labeled new thing to compile and
verify against real Capacitor/AppWidget classes — not several unrelated
changes to untangle at once.
