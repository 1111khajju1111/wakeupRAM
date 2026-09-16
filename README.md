# Wake Up Ram

Personal AI companion, discipline system and life-intelligence platform.

## Status: Phases 1-10 complete, Phase 13 (security/observability/deployment) underway, Phase 11 still blocked on a real native build

Then, generated CI YAML that references `sqlite:///:memory:` as an env var
value: caught during validation that plain YAML parses the bare
`sqlite:///:memory:` as a nested mapping (the colons inside the URL confuse
the block-mapping parser), which would have failed CI on its very first
run with an obscure YAML error nowhere near the actual test code. Fixed by
quoting the value; re-validated `render.yaml`, `docker-compose.yml`, and
`ci.yml` all parse cleanly with `yaml.safe_load` and `vercel.json` with
`json.load` before finalizing this pass.

### This pass: Phase 13 security hardening, observability, and deployment scaffolding

Picked up from the prior pass's own "What's not built yet" list rather than
re-deriving scope from the master doc. Two constraints shaped everything in
this pass and are worth being upfront about: this sandbox has no network
access (no `pip install`, `npm install`, or `npx cap add android`) and no
pre-existing `node_modules`/Python venv. Every file below was written and
hand/`py_compile`-verified for syntax, but **none of it has actually been
executed** — run the real test suites and `docker compose up` locally
before trusting this pass fully. That's a materially different confidence
level than the prior passes' README entries, which generally could run
`pytest` for real; said so plainly rather than implying otherwise.

Added:
- `backend/app/core/logging.py` — structured JSON logging to stdout, with
  secret redaction (a `RedactingFilter` that scrubs known-sensitive field
  names even from `extra={...}` payloads) and a per-request correlation id
  propagated via a contextvar. Deliberately does not log request/response
  bodies — health/finance/conversation content must never reach log storage
  (section 21/27).
- `backend/app/models/audit_log.py` + `migrations/versions/0011_audit_logs.py`
  — a durable `audit_logs` table, separate from the operational request
  logs above, scoped to account/security-relevant events (section 21:
  "Maintain audit logs for sensitive actions").
- `backend/app/services/audit_service.py` — a fail-safe writer (its own
  commit, swallows its own exceptions) so a bug in audit logging can never
  break the login/register flow it's describing.
- Wired audit events into `POST /auth/register`, `/login`, and `/refresh`
  (success and failure both recorded) and wired request/exception logging
  into `main.py`. Failed-login audit entries deliberately don't record
  *which* check failed (unknown email vs. wrong password) — logging that
  distinction would hand an attacker an account-enumeration oracle.
- `backend/tests/test_audit_log.py` — 4 new tests covering the above.
- `frontend/eslint.config.js` — **`npm run lint` referenced this file since
  Phase 1 and it never existed**; `eslint .` was a silent no-op the entire
  time. Added the flat config (ESLint 9) plus the plugin devDependencies it
  needs (`@eslint/js`, `typescript-eslint`, `eslint-plugin-react`,
  `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`) to
  `package.json`. Includes a rule that flags hardcoded `localhost`/`127.0.0.1`
  URLs, as a lightweight automated check for the zero-hardcoding requirement
  (section 22) on the one violation most likely to slip through review.
- `frontend/vite.config.ts` — added the `test` block (jsdom environment,
  setup file) vitest needs; it was listed as a devDependency and had a
  `package.json` script since Phase 1 but was never actually configured to
  run.
- `frontend/src/services/tokenStorage.test.ts` and
  `frontend/src/store/AuthContext.test.tsx` — first real frontend tests in
  the repo, covering the two modules most load-bearing for security
  (token round-trip/clearing, and the full login/logout state-machine).
  This closes a small slice of the "no frontend tests" gap flagged since
  Phase 6, not all of it — every other feature screen still has zero test
  coverage.
- Deployment scaffolding, all previously entirely absent from the repo:
  - `backend/Dockerfile` (multi-stage, non-root user, runs `alembic upgrade
    head` before serving so a broken migration fails the deploy instead of
    serving against a mismatched schema) + `backend/.dockerignore`.
  - `render.yaml` — Render Blueprint for the backend. Every secret/
    environment-specific value is `sync: false` (Render prompts for it in
    the dashboard) rather than a placeholder committed here; `DATABASE_URL`
    is never `fromDatabase` since production uses Aiven, not Render's own
    Postgres (section 25).
  - `frontend/vercel.json` — SPA rewrite plus baseline security headers
    (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`).
    `VITE_API_BASE_URL` still needs to be set as a Vercel *environment*
    variable in the dashboard — it's not a secret, but it is
    environment-specific, so it doesn't belong hardcoded in this file
    either.
  - `docker-compose.yml` — local-dev-only Postgres + backend, so
    `docker compose up` gives a working stack without anyone needing real
    Aiven credentials just to develop. The frontend isn't containerized
    here on purpose — `npm run dev`'s hot reload is faster for daily work.
  - `.gitignore` at the repo root — **also didn't exist until this pass**.
    With Docker/CI/deploy configs now in the repo, a missing `.gitignore`
    stops being a minor gap and starts being a real risk of `.env`/
    `node_modules`/`.venv` getting committed by accident.
  - `.github/workflows/ci.yml` — runs backend `pytest` (SQLite, no external
    services) and frontend `lint`/`build`/`test` on every push and PR. This
    is the first time anything in this repo runs automatically rather than
    only when a future pass remembers to run it by hand.

### What's not built yet (updated)
Same Android/production gaps as the prior pass, unchanged by this pass:
the native Android home-screen widget's `android/` project doesn't exist
yet (needs `npx cap add android` with real npm/Java/Gradle — this sandbox
still doesn't have one), Phase 9's recording-format gap (webm/ogg vs.
`.m4a`) is unchanged, and the notification engine is still on-demand rather
than scheduled (still explicitly deferred — see the scoped-decisions note
below, unchanged from before).

New from this pass, specifically because nothing in it has actually run:
- **No file in this pass has been executed.** The backend syntax-checks
  (`py_compile`) cleanly; the frontend has no way to even syntax-check
  without `npm install`. Run `pytest` and `npm run lint && npm run build &&
  npm test` for real before merging any of it.
- Refresh-token rotation and a revocation list (flagged as a TODO in
  `auth.py` since before this pass) are still not implemented — a stolen
  refresh token is valid until natural expiry. Worth prioritizing in the
  next security pass now that audit logging would actually let you notice
  the pattern that flags a token as stolen in the first place.
- CI runs tests but doesn't yet gate deploys on them passing, build/push a
  Docker image to a registry, or run the Android build — those are
  reasonable follow-ups once `android/` exists and this pass's YAML has
  been confirmed to actually run green.
- No frontend tests exist yet for anything beyond auth (dashboard, health,
  finance, smoking, countdowns, notifications, talk/voice screens are all
  still zero-coverage).

### Prior pass: staged (unverified) Phase 12 native countdown widget — `android-native-widget-staging/`


Asked to continue Phase 12 per the master doc. Checked first whether
Phase 11 is actually done, since a widget depends on Phase 11's
token-storage work running on a real device — it isn't: no `android/`
directory exists anywhere in this repo yet, same as every prior pass.
Staged the widget the same way Phase 11's call-recorder plugin was
staged (`android-native-plugin-staging/`) rather than either blocking
entirely on Phase 11 or silently pretending it's done — see
`android-native-widget-staging/README.md` for the full breakdown:
architecture (`AppWidgetProvider` + `WorkManager` periodic Worker +
config activity + a dependency-free HTTP client sharing the app's own
JWT via Capacitor's `SharedPreferences`), every real design decision
(why 30-minute refresh, why a plain `Worker` over `CoroutineWorker`, why
`AsyncTask` in the config screen), the one genuinely unverifiable piece
(the exact Capacitor `SharedPreferences` file name — flagged with a
concrete way to confirm it once `android/` exists), and a numbered
integration checklist.

Two real mistakes caught and fixed *during this same pass*, before
calling any of it done — both the kind of thing that only surfaces from
actually re-checking against a platform's real rules rather than
pattern-matching:
- The widget's `<receiver>` in the manifest snippet was initially written
  `android:exported="false"` — wrong. A home-screen widget's
  `AppWidgetProvider` is invoked by the system launcher process, a
  different process from the app itself, so it must be
  `android:exported="true"` or the OS can never deliver the update
  broadcast to it. Caught on review, fixed before finalizing.
- `CountdownApiClient.kt` referenced `BuildConfig.API_BASE_URL` from the
  `com.wakeupram.app.widget` subpackage without importing
  `com.wakeupram.app.BuildConfig` — Kotlin doesn't auto-resolve across
  sibling/parent packages. Would have failed to compile on the first
  real build; fixed with an explicit import.

Every JSON field `CountdownApiClient.kt` parses (`id`, `title`,
`target_datetime`, `category`, `priority`) and every endpoint it calls
(`/api/v1/countdowns`, `/api/v1/today`, `/api/v1/auth/refresh`) was
checked against the actual backend schema/service source files in this
repo, not written from memory of what Phase 8 probably built.

### Prior pass: AI provider wiring for `.env` (Groq + Google config fields), and a roadmap correction

Two unrelated things happened in this pass — noting both since they land in
the same file.

**1. Backend now actually reads the `.env` values that had been built up
across several prior turns of conversation, not just documented them:**
- Added `GroqProvider` (`app/ai/providers_groq.py`) — a real adapter against
  Groq's OpenAI-compatible chat completions endpoint, same JSON-envelope
  contract as `AnthropicProvider` (reply + memory_updates in one round
  trip). `RESPONSE_FORMAT_INSTRUCTIONS` and the parsing logic were
  duplicated between what would've been two provider files; pulled both
  into `app/ai/provider.py` as `parse_json_envelope_response` so Anthropic
  and Groq share one implementation instead of two copies that could drift.
- `ram_core.get_provider()` now branches on `AI_PROVIDER=groq` in addition
  to `anthropic`, falling back to the deterministic provider for a missing
  key or an unrecognized value — same "never a silent fake response"
  posture as before.
- `Settings` gained `STT_MODEL_NAME`, `TTS_MODEL_NAME`, `GOOGLE_API_KEY` —
  previously undeclared, so `extra="ignore"` was silently dropping them
  even though they were sitting right there in `.env.example`.
- 5 new tests (`tests/test_ai_provider_selection.py`) covering the
  selection branch directly (Anthropic/Groq/fallback-on-missing-key/
  fallback-on-unrecognized-provider), not just through the HTTP layer where
  `get_provider` is normally patched away. **122/122 backend tests pass.**
- Added a root `.gitignore` — there wasn't one anywhere in the repo, which
  matters now that `.env.example` has a real Aiven hostname in it (see
  below) and a real `.env` needs to never follow it into version control.

**Known naming mismatch, left as-is on purpose:** `settings.ANTHROPIC_API_KEY`
now holds a Groq key (or would hold a Google key, if `AI_PROVIDER` becomes
`google`) — the field name is a misnomer. This was an explicit choice
across several turns of conversation (keep `.env`'s key *placement* stable
across provider swaps) rather than an oversight; `get_provider()` has a
comment pointing at this. Rename it — and the one read site — together if
that decision changes.

**Also worth flagging in `.env.example`, not changed:** `DATABASE_URL`
contains a real Aiven hostname
(`pg-6d30a19-bheemasenaa123-2b22.b.aivencloud.com`). The password portion
is the literal word `password`, not a working credential, but the hostname
itself is real infrastructure sitting in a file meant to be committed. If
this repo is or becomes public, swap `.env.example` back to a generic
placeholder host and keep the real one only in the git-ignored `.env` — the
`.gitignore` added this pass protects that file going forward, but doesn't
retroactively fix what's already in the example.

**2. Roadmap correction:** a separate message in this pass proposed
"Phase 12: Production Deployment (AWS ECS/Railway, Redis, iOS)," "Phase 13:
Offline-first," "Phase 14: Hardware integrations + wake-word," "Phase 15:
guardrails," opening with "with Phase 11 completed." None of that matches
this repo or the master doc: Phase 11 is not complete (no `android/`
directory exists in this repo — see below), the master doc's own Phase 12
is the native countdown widget (not deployment), Phase 13 is security
hardening + tests + deployment (not offline-first), Phase 14 is production
QA (not hardware integrations), and the doc has no Phase 15. The proposed
plan also introduces Redis, AWS ECS/Railway, and iOS builds — none of
which appear anywhere in the master doc, which explicitly locks the stack
("CORE STACK — DO NOT CHANGE WITHOUT A TECHNICAL BLOCKER": Render for
backend, no Redis, Android-only via Capacitor with no iOS mentioned once
in 31 pages). Flagged this rather than silently adopting or silently
ignoring it; the explicit decision was to finish Phase 11 for real first,
then do the master doc's actual Phase 12 (native widget) next — not the
alternate roadmap. Noting this here so it doesn't resurface as a silent
assumption in a future pass.

### Prior pass: staged (unverified) native `.m4a` plugin — `android-native-plugin-staging/`

Checked first whether this environment has *more* than the previous
pass's no-network limit, since the user asked to continue: no `javac`,
no `gradle`, no Android SDK, only a headless JRE. So both remaining
Phase 11 gaps (the `android/` project itself, and `.m4a` recording) are
still blocked here, and neither script output nor hand-authored native
code can be compiled or run in this sandbox to confirm it's correct.

Given that, the honest next increment was preparing — not integrating —
source for the `.m4a` gap: `android-native-plugin-staging/` holds a
Kotlin `CallRecorderNativePlugin.kt` (native `MediaRecorder` with
`OutputFormat.MPEG_4` + `AudioEncoder.AAC`, which is what actually
produces `.m4a`, plus Capacitor's documented runtime-permission
annotation pattern for `RECORD_AUDIO`), a README explaining exactly what
still needs verifying and where the file belongs once `android/` exists,
and an example (not wired in) showing how `callRecorder.ts`'s native
branch would eventually call it. Deliberately kept outside
`frontend/src` and not touching `callRecorder.ts` at all — that file
currently has one known, bounded gap (webm/ogg instead of m4a); splicing
in a call to never-compiled native code would trade a known gap for an
unknown one (crash / silent no-op / build failure) discovered later and
harder to isolate. Full reasoning for that choice is in the staging
folder's own README.

**Still exactly what it was**: neither gap is closed. This pass produced
a well-reasoned draft for one of them, explicitly marked unverified, not
a working implementation.

### Prior pass: `scripts/generate-android.sh` (the actual `android/` gap, addressed the honest way)

This sandbox has no network access either — confirmed empirically, not
assumed: `curl -sI https://registry.npmjs.org` returned `403` with
`x-deny-reason: host_not_allowed`, and `pip install -r requirements.txt`
failed the same way (`No matching distribution found for fastapi==0.115.0`,
no index reachable). So the prior pass's reasoning still holds here —
`npx cap add android` cannot be run in this environment, and hand-authoring
`android/`'s Gradle files, manifest, and wrapper jars without ever running
the real generator would still be fabrication, not implementation.

What's genuinely new this pass instead of re-stating that gap: a script
that removes any remaining manual-transcription risk once someone *does*
run it somewhere with real tooling. `scripts/generate-android.sh` chains
`npm install` → `npm run build` → `npx cap add android` (or `cap sync` if
`android/` already exists, so re-running is safe) → patches the generated
`AndroidManifest.xml` with the three permission lines this file already
documented in prose (below). The patch step is idempotent (checked by
simulating it against a representative manifest: first run adds
`RECORD_AUDIO`/`POST_NOTIFICATIONS`, second run reports both "already
present," no duplicate lines) and inserts each `<uses-permission>` as a
sibling of `<application>` right before `</manifest>`, which is valid
regardless of where Capacitor's template places `<application>`. This
turns "read the docs, find the right file, hand-edit XML correctly" into
"run one script" — smaller than actually generating the project, but a
real reduction in what's left to get wrong by hand.

**Verification honestly available in this pass**: `python3 -m py_compile`
across every backend `.py` file (clean — but this only proves syntax
validity, not the `pytest` suite the prior network-enabled pass actually
ran) and `bash -n` on the new script (clean), plus the manual manifest-patch
simulation above. No `pytest`, no `tsc`, no `npm install` — this pass could
not re-confirm those without network, so it doesn't claim to have.

**Still exactly what it was**: the native Android Gradle project itself
doesn't exist in this repo. Nothing in this pass changes that — it only
makes the eventual one-time generation step less error-prone.

### Prior pass: `callRecorder.ts` Filesystem implementation (the flagged next step)

Re-verified the incoming state first rather than trusting the prior pass's
numbers at face value: fresh venv, `pip install -r requirements.txt &&
pytest` (**117/117**, run twice back-to-back to rule out flakiness — both
clean), `npm install && tsc -b --force && vite build` (clean, 91 modules).
All matched what was reported.

Then did the one concrete thing the prior pass flagged as its next step:
made `saveRecordingLocally` actually write the file via
`@capacitor/filesystem` on native Android, instead of only adding the
dependency. `startRecording`/`isRecordingSupported` are untouched.

- **`Capacitor.isNativePlatform()` branch**, same pattern as the existing
  `nativeNotifications.ts`: native writes through `Filesystem.writeFile`
  (base64 via `FileReader.readAsDataURL`, since the plugin doesn't accept a
  `Blob` directly); web (no Filesystem API) keeps the prior pass's browser
  download unchanged.
- **Caught a real mistake before it shipped**: the natural first choice,
  `Directory.Documents`, sounds like private app storage but isn't — per
  the plugin's own type definitions, on Android it's the *public* Documents
  folder (visible to other apps) and needs either a legacy-storage manifest
  flag or an explicit runtime permission request before every write, neither
  of which existed anywhere in this codebase. Switched to `Directory.Data`
  (genuinely app-private, deleted on uninstall, no permission needed on any
  Android version) — a better fit for "protect sensitive local files where
  practical" (section 21) than the public folder would have been, and it
  avoids a permission-handling feature this change didn't otherwise need to
  add. Worth remembering if this ever needs revisiting: don't trust a
  Capacitor directory name at face value, read what it actually maps to per
  platform.
- Updated `CallScreen.tsx`'s one call site to `await` the now-`async`
  `saveRecordingLocally` (`endCall` was already `async`, so no further
  signature changes needed there).
- `tsc -b --force` and `vite build` both clean after the change (94
  modules now, up from 91). `pytest` unaffected (frontend-only change,
  117/117 held). i18n key parity unaffected (204/204, no new UI strings —
  this was a pure service-layer change).

**Still honestly open, unchanged from before**: the container format gap.
`MediaRecorder` still produces webm/ogg, not the `.m4a` section 13
describes — that needs a native audio-capture plugin, not a Filesystem
change, and isn't attempted here. The `Wake Up Ram/Calls/YYYY-MM-DD/
HH-MM-SS.<ext>` *structure* is honored (and now genuinely native-stored);
the *extension* still isn't `.m4a`. The actual native Android Gradle
project (`android/`, `AndroidManifest.xml`) is also still unbuilt — it
needs `npx cap add android` with real Java/Gradle access, which this
environment doesn't have.

### Prior pass: real toolchain verification + three Phase 11 items completed

Unlike the prior Phase 10/11 pass (no network access, verified by
`py_compile`/hand-simulation/`tsc` diffing only), this pass had full network
access and ran the actual toolchain end to end:

- **Backend**: `pip install -r requirements.txt && pytest` — **117/117
  tests pass**. This is the first real confirmation (not static analysis)
  that the prior pass's Phase 10 duplicate-`ModelVersion` fix and Phase 11
  notification-ID hash fix both genuinely hold.
- **Frontend**: `npm install && tsc --noEmit && npm run build` — clean, no
  errors, 91 modules built.
- **i18n**: verified programmatically after every addition below —
  204/204 keys, zero mismatches between `en.json` and `te.json`.

**Completed in that pass:**

1. **`CallScreen.tsx` speech-error wiring** — the item the prior pass left
   half-done. `speech.ts` already normalized real STT errors into
   `permission_denied | network | no_speech | audio_capture | unknown`;
   this pass wires that signal through the call UI itself:
   - `no_speech` (an ordinary pause mid-conversation) now restarts
     listening silently — never surfaced as a failure.
   - Every other reason shows a specific, translated message (section 27:
     "voice failures must explain microphone, network, or audio-state
     problems") and reveals the manual-text composer, which previously
     only appeared when STT wasn't supported at all, never when it failed
     mid-call.
   - `network`/`unknown` get a "try voice again" retry button;
     `permission_denied`/`audio_capture` don't, since retrying immediately
     would just fail identically until the user changes an OS/browser
     setting or plugs in a mic — a button that always re-fails isn't
     honest affordance.
   - Implementation detail worth knowing: the fix runs the restart-vs-
     surface decision inside the recognizer's `onEnd` handler (deferred
     via a ref set in `onError`), not inside `onError` directly — the Web
     Speech API always fires `onend` after `onerror`, and restarting a new
     recognizer from inside the old one's own `onerror` risked a
     start/stop race on some browsers.
2. **Wired `nativeNotifications.ts` into `NotificationsScreen.tsx`** — this
   bridge existed since the prior pass but nothing called it. Every load
   now schedules `pending` notifications and cancels `dismissed`/
   `actioned` ones as real Android OS notifications, best-effort (a
   scheduling failure is swallowed since the in-app list is already the
   source of truth and renders regardless — see the docstring in
   `NotificationsScreen.tsx`).
3. **Android back-button handling** — new `app/AndroidBackButton.tsx` using
   `@capacitor/app`'s `backButton` event (already a dependency, previously
   unused): navigates back within the SPA's router history, or exits the
   app at the root route (`/`), where there's no further router history to
   go back to and a Capacitor WebView has no browser history before the
   app's own root either. No-ops on web, mounted once in `App.tsx`.

**Was started-not-finished as of that pass; now finished** — see the top
of this file ("This pass: `callRecorder.ts` Filesystem implementation") for
the completed `Filesystem.writeFile` work and the `Directory.Documents` vs
`Directory.Data` correction made along the way.

**Still not reviewed/built for Phase 11** (unchanged from the prior pass):
the actual native Android Gradle project (`android/`,
`AndroidManifest.xml`) — this cannot be honestly hand-authored without
running `npx cap add android` in an environment with real npm/Java/Gradle
access. Once generated, add the permission lines documented further below
in this file.

### Fixed in the Phase 10 + Phase 11 review pass (prior pass)

**Phase 10 — one real, confirmed bug:**

`prediction_service._run_prediction` retrained and persisted a brand-new
`ModelVersion`, plus a full duplicate set of `ModelFeature` rows, on
**every single prediction request** — even when nothing about the user's
underlying data had changed since the last training run. Calling "what's
my craving risk right now?" repeatedly (an entirely normal usage pattern
for exactly this feature) would grow both tables without bound. The tell
was in the test suite itself: `test_smoking_risk_with_enough_events_trains_a_model_and_separates_risk`
asserted `len(versions) >= 1` instead of `== 1` — exactly what you'd write
to avoid a test failing on a duplication bug rather than fix the bug.
Confirmed by tracing the code path directly (two predict calls against an
unchanged 16-event training set → two separate `ModelVersion` rows, 32
`ModelFeature` rows instead of 16). Fixed by reusing the latest
`ModelVersion` for a (user, prediction_type) whenever its
`training_sample_count` matches the current training set size, and only
retraining (and persisting new `ModelFeature` rows) when it's genuinely
grown. Tightened the original test to `== 1` plus an explicit
`ModelFeature` count check, and added
`test_repredicting_after_a_new_event_creates_exactly_one_new_version` to
prove the fix doesn't overcorrect into never retraining. Documented as a
known simplification (not hidden): reuse is keyed on sample count, not a
full content hash, so an edit to a historical event's label/features
without a change in count would go undetected — the far more common case
(new events accumulating) is handled correctly.

Everything else in Phase 10 held up well: the two implemented prediction
types (smoking risk, habit adherence), point-in-time feature-engineering
correctness (trigger-repeat and streak counts only ever see strictly
earlier occurrences), the four-tier honest confidence system
(no_data / baseline_low_data / model_limited_data / model), Laplace-smoothed
baselines for small samples, and `record_feedback`'s refreshingly candid
docstring admitting it doesn't currently feed back into either model's
training set (both already have automatic ground truth from
SmokingEvent/HabitLog) rather than pretending a fuller loop exists.

**Phase 11 — one bug fixed, one significant gap found and only partially
addressed:**

- **Fixed**: `nativeNotifications.ts`'s notification-ID hash had a genuine
  edge case — the rolling hash is coerced into the full 32-bit signed
  range (via `| 0`), which includes exactly `Int32.MIN`
  (`-2147483648`). `Math.abs()` of that is `2147483648`, one past
  `Int32.MAX`, the actual valid range for a native Android notification
  ID. Fixed with a bitmask (`Math.abs(hash) & 0x7fffffff`) instead of a
  plain `Math.abs`, verified against that exact edge case plus normal
  cases.
- **Found, only partially fixed**: `CallScreen.tsx`'s speech-recognition
  error handler discarded every failure outright
  (`onError: () => setCallPhase("idle")`) — any STT error, including the
  completely ordinary "no speech detected during a short pause in
  conversation" case, silently killed listening with zero indication to
  the user. This directly contradicts section 27 ("voice failures must
  explain microphone, network, or audio-state problems"), and in practice
  means any real call with a brief pause would silently stop responding.
  Fixed the lower layer: `speech.ts` now captures the browser's actual
  `SpeechRecognitionErrorEvent.error` code and normalizes it to
  `permission_denied | network | no_speech | audio_capture | unknown`
  instead of discarding it. **Not yet done**: wiring this through
  `CallScreen.tsx` itself — treating `no_speech` as a normal silent
  restart (not a failure) versus surfacing the other reasons as a visible,
  specific message with a fallback to the manual text composer (which
  already exists in the component but is currently only shown when STT
  isn't supported at all, never when it fails mid-call). The current
  `onError: () => setCallPhase("idle")` still compiles and runs fine
  (a callback ignoring its argument is a valid subtype), it just doesn't
  yet take advantage of the improved signal — this is the top item to pick
  up next.

**Confirmed solid, re-verified this pass**: `tokenStorage.ts`'s migration
to Capacitor `Preferences` (grepped every call site —
`apiClient.ts`/`AuthContext.tsx` — to confirm all were correctly updated
to `await` the now-async API), `capacitor.config.ts`, the
`package.json` Capacitor dependencies, and the notification permission
bridge's check-then-request flow. All fixes from every prior review pass
(Phases 1-9) remain intact — re-checked via grep against each fix's
signature, not assumed.

**Not yet reviewed/built for Phase 11**: whether an actual native Android
project (`android/`, `AndroidManifest.xml`) has been generated and declares
the required permissions (`RECORD_AUDIO`, notifications). The Capacitor
Filesystem integration for call recordings (this section used to flag it as
pending) is now done — see the top of this file. This remaining item is
the next thing to pick up.


### Phase 11 progress

- Token storage moved from plain `localStorage` to Capacitor's
  `Preferences` plugin (Android SharedPreferences-backed) — this required
  converting `getAuthTokens`/`setAuthTokens`/`clearAuthTokens` from sync to
  async and updating both call sites (`apiClient.ts`, `AuthContext.tsx`,
  including `AuthContextValue.logout`'s type). **Not** hardware-backed
  encryption — that would be a further step to `@capacitor/secure-storage`
  or the Android Keystore directly, noted as future hardening rather than
  silently assumed.
- `capacitor.config.ts` written (appId/appName/webDir, a default
  notification channel).
- `app/services/nativeNotifications.ts`: a thin bridge that turns backend-
  computed `Notification` rows into real Android OS notifications via
  `@capacitor/local-notifications` — deliberately does none of the
  eligibility/dedup/quiet-hours logic itself (that stays server-side in
  `notification_service.py`); no-ops safely on web rather than throwing.
  **Now wired into `NotificationsScreen.tsx`** (see the top of this file) —
  every load schedules/cancels native notifications to match backend
  status.
- **Android back-button handling** (`app/AndroidBackButton.tsx`, see top of
  this file) — done.
- **`CallScreen.tsx` speech-error handling** (see top of this file) — done.
- **Capacitor Filesystem-backed call-recording storage** (see top of this
  file) — done. `saveRecordingLocally` writes to `Directory.Data` natively,
  falls back to a browser download on web. The container-format gap
  (webm/ogg, not `.m4a`) is separate and still open — see below.

**Still open for Phase 11:**
- The actual native Android Gradle project (`android/` directory:
  `AndroidManifest.xml`, `build.gradle`, `MainActivity.java`, gradle
  wrapper, etc.) does not exist in this repo and **cannot be honestly
  hand-authored here** — it's normally generated by running
  `npx cap add android` in an environment with real npm/Java/Gradle access
  (which no pass so far, including this one, has had). Fabricating that
  file tree without ever running the generator risks subtly-wrong
  Gradle/manifest content that looks plausible but doesn't actually build.
  Run `bash scripts/generate-android.sh` from `frontend/` once you have
  that access — it runs `npx cap add android` for real, then patches the
  generated manifest with the permission lines below itself (idempotently,
  safe to re-run). Documented here too in case you'd rather do it by hand:
  ```xml
  <uses-permission android:name="android.permission.RECORD_AUDIO" />
  <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
  <uses-permission android:name="android.permission.INTERNET" />
  ```
  (`RECORD_AUDIO` for the call screen's local recording via
  `getUserMedia`/`MediaRecorder`, already built in Phase 9;
  `POST_NOTIFICATIONS` is required at runtime on Android 13+ for the
  local-notifications bridge above; `INTERNET` is included in Capacitor's

  default template already but is listed here for completeness.)
- No home-screen widget yet — that's explicitly Phase 12 per the doc's own
  phase breakdown, not part of Phase 11.



This is a real starting codebase, not a mockup — every file here is working
implementation code.

### Phase 10: personal ML + prediction feedback (this pass)

**Backend** — four new tables per section 19 (`app/models/prediction.py`):
`ModelVersion`, `ModelFeature`, `Prediction`, `PredictionFeedback`.
`migrations/0010_predictions.py`. Endpoints under `/api/v1/predictions`:
`POST /smoking-risk`, `POST /habit-adherence/{habit_id}`, `GET` (history),
`GET /model-versions`, `POST /{id}/feedback`.

**Two concrete prediction types**, proving the framework generalizes rather
than being special-cased to one domain:
- `smoking_risk` — "how likely am I to smoke if I don't intervene right
  now," predicted *before* the outcome is logged, from `trigger` +
  `craving_intensity` + optional `stress_level` (the same fields
  `SmokingEventCreate` asks for). This is the section 10 intervention
  moment made concrete: ask before the craving resolves, not after.
- `habit_adherence` — likelihood of completing a given habit today, from
  day-of-week, rolling 14-day completion rate, and current streak.

Feature engineering (`app/ml/features.py`) deliberately reuses
`smoking_service`'s existing `_time_of_day_bucket`/`_normalized_trigger`
helpers and `habit_service.is_due_today`, rather than redefining "evening"
or "the same trigger" or "which days a habit is due" a second time.

**Why a hand-rolled logistic regression instead of scikit-learn**
(`app/ml/model.py`): section 9 asks for "logistic regression for
interpretable probabilities" — a model class, not a specific library. At
the sample sizes a single user's own history produces (tens to low
hundreds of rows per prediction_type), a ~100-line pure-Python
implementation (standardize → gradient descent → L2 regularization →
sigmoid) trains in milliseconds and adds zero new dependencies — no
compiled-wheel/build concerns for whoever deploys this, nothing to pin
against a numpy/scipy ABI. Verified against synthetic data before wiring
it in (not just unit-tested after the fact): fed clearly-separable
two-feature data and confirmed the trained model correctly assigns high
risk to the high-risk case and low risk to the low-risk case, in both a
noisy 60-sample synthetic set and the exact 16-sample scenario
`test_predictions.py` exercises. If a later phase needs a genuinely
nonlinear model (section 9 also mentions random forest/gradient boosting
"for nonlinear tabular behavior"), that's the point to add scikit-learn as
a real dependency — introducing it now for a linear model this size would
solve a problem this app doesn't have yet.

**The confidence-tier system is the actual safety mechanism here**, not a
UI nicety — every prediction carries one of four tiers, and the frontend
never shows a bare number without it:
- `no_data` — zero relevant history. `predicted_probability` is `null`,
  never a fabricated number.
- `baseline_low_data` (1-9 labeled examples) — too few to fit a model
  responsibly. Returns the user's own Laplace-smoothed empirical rate
  instead — real history, just not conditioned on today's specific context.
- `model_limited_data` (10-29 examples) — a trained model, explicitly
  labeled as still thin.
- `model` (30+ examples) — a personal model on a reasonably-sized personal
  history. Still labeled with its training sample count and accuracy in
  `Prediction.explanation` every time — never presented as a bare percentage.

This is the direct implementation of the master prompt's "if ML has
insufficient observations, say so and use a deterministic baseline rather
than fabricating a prediction," and of section 9's "must never present an
inference as a fact" principle already established for Memory in Phase 3 —
applied here to predictions instead of memories.

**Retraining happens fresh on every prediction request** rather than on a
schedule or cached model reuse — documented in
`prediction_service.py`'s module docstring, since this is a real design
tradeoff worth being able to revisit: at these data volumes (predictions
are requested explicitly, not on every chat message — nothing like
"retraining a large neural network after every response") a full
gradient-descent run costs milliseconds, so there's no benefit to managing
cache invalidation for a stale model. Every run is still persisted as its
own `ModelVersion` row regardless, so the training history stays
inspectable per section 9's "store model versions and metrics" even though
nothing currently reuses an old version's weights.

**Feedback loop**: `POST /predictions/{id}/feedback` records the actual
outcome once per prediction (enforced via a unique constraint on
`prediction_feedback.prediction_id` — a prediction is about one specific
future moment, not something that gets re-graded). Nothing yet *uses* the
recorded feedback to adjust future predictions beyond it becoming a future
labeled training example next time that prediction_type is retrained
(which happens automatically, since retraining always runs on the latest
data) — an explicit calibration/evaluation step on top of accumulated
feedback (e.g. tracking predicted-vs-actual over time) is a reasonable
Phase 13+ QA addition, not implemented here.

**Frontend**: `InsightsScreen.tsx` — a smoking-risk check form, a
habit-adherence check per active habit, a prediction history list (each
entry shows its confidence tier and explanation, never a bare percentage),
inline yes/no feedback buttons, and a model-version history list. Wired
into nav (`nav.insights` already existed as an i18n key from an earlier
pass but had no route — this pass adds the actual screen). Full en/te i18n
parity verified programmatically (199 keys, zero mismatches).

**Verification note**: this pass, like the Phase 6 pass, had no network
access, so `pip install`/`npm install` and therefore `pytest`/`tsc -b`
weren't possible. Verification instead relied on: `python -m py_compile`
on every backend file (all pass); hand-simulating the exact feature vectors
`test_predictions.py`'s scenarios produce and running them through the real
`app/ml/model.py` functions directly with plain Python (confirmed the
Laplace-smoothing baseline test computes exactly 0.6 as asserted, and the
16-sample model-training test achieves clean separation — 0.93 vs 0.07
predicted probability — before the test was ever written to assert it, not
after); and a global `tsc` binary (without this project's `node_modules`)
diffed against the pre-existing missing-module baseline established in the
Phase 6 pass, confirming zero new syntax or type errors. Please run the
real `pytest` and `npm install && tsc -b && vite build` once you have
network access — I'd expect them to pass, but say so with the same
humility as the Phase 6 note.

### Fixed this pass, found while auditing Phase 1-9 before starting Phase 10

Two real, non-cosmetic bugs, neither related to Phase 10 itself:

1. **`VoiceCall` (Phase 9) was never imported in `app/models/__init__.py`.**
   Every other domain model is imported there specifically so Alembic's
   `autogenerate` — which imports `app.models`, not `app.main` (see
   `migrations/env.py`) — sees the complete schema. With `VoiceCall`
   missing, a real `alembic revision --autogenerate` run could have
   silently proposed dropping the `voice_calls` table, since SQLAlchemy's
   metadata wouldn't have known it exists as a model. The test suite
   passed anyway, by accident: `tests/conftest.py` imports `app.main`
   *before* `app.models`, and importing `app.main` pulls in the full
   router chain (including the `calls` endpoint → `voice_call_service` →
   `VoiceCall`) as a side effect, registering it on `Base.metadata` before
   `create_all` ever runs. Fixed by adding the missing import.
2. **Hardcoded `aria-label` strings across four screens**
   (Finance/Health/Smoking/Home — 18 instances total), flagged in
   conversation during the Phase 6 review but never actually fixed in the
   repo, and repeated again in the Phase 7-9 `SmokingScreen.tsx` rather
   than caught. These violate section 22/23's "every static UI string
   through i18n" — a Telugu-language user's screen reader would announce
   these in English regardless of language setting, since `aria-label`
   attributes were checked for visible text and placeholders in earlier
   i18n audits but not for `aria-label`s specifically. Fixed all 18: wrapped
   in `t(...)`, reusing existing keys where the same label already existed
   as visible `<h2>` text in that section, adding 5 new keys
   (`finance.summaryLabel`, `health.summaryLabel`, `smoking.summaryLabel`,
   `home.currentTimeLabel`, `home.activeCountdownLabel`) where nothing
   reusable existed. Re-verified full en/te key parity and zero new `tsc`
   errors afterward.

### Phase 9: voice calls (previous pass)

**Backend** — `VoiceCall` model/schema/service/endpoints
(`POST/GET /calls`, `GET /calls/{id}`, `POST /calls/{id}/end`),
`migrations/0008_voice_calls.py`. A call wraps the existing Phase 3
`Conversation`/`Message` pipeline unchanged rather than forking it — the
turn-by-turn exchange during a call goes through the exact same
`POST /conversations/{id}/messages` endpoint every other message uses
(`tests/test_calls.py` proves the two are actually wired together, not just
individually correct). `VoiceCall` only ever stores local recording
*metadata* (a client-reported reference string + duration) — never receives
or stores audio bytes itself, matching section 13's "local device storage
by default... no automatic cloud upload."

**Why there's no backend STT/TTS provider abstraction**, unlike the
Anthropic text-generation provider: there's no credentialed service to
abstract. The browser/WebView's built-in `SpeechRecognition` /
`SpeechSynthesis` APIs are free and on-device — they *are* "the real
adapter" here, and they live entirely client-side
(`frontend/src/services/speech.ts`), feature-detected at runtime. When
they're unavailable (most desktop browsers besides Chrome, and any
test/headless environment), `CallScreen.tsx` falls back to a manual
text-input composer instead of silently doing nothing — that fallback path
is also how this flow is exercisable without live audio hardware.

**Recording** (`frontend/src/services/callRecorder.ts`) uses
`MediaRecorder` to capture locally and triggers a browser download with the
section-13 naming convention (`Wake Up Ram/Calls/YYYY-MM-DD/HH-MM-SS.<ext>`).
Documented, not hidden: in this web/PWA context `MediaRecorder` produces
webm/ogg, not the `.m4a` the doc describes, and "save locally" is a browser
download rather than a write into a real native folder — both are honest
placeholders for Phase 11's Capacitor `Filesystem` integration, not a fake
version of it. (Historical note: the "browser download vs. native folder"
half of this was later closed — see "This pass: `callRecorder.ts`
Filesystem implementation" at the top of this file. The container-format
half, webm/ogg vs. `.m4a`, is still open.)

**A real bug found and fixed while building this**, unrelated to voice
itself: adding `test_calls.py`'s requests pushed the test suite's *total*
request count within a rolling 60-second window over the app's
`RATE_LIMIT_DEFAULT` (100/minute) for the first time, and `tests/test_smoking.py`
/ `tests/test_tasks.py` — nothing to do with calls — started failing
intermittently with 429s partway through the run. Root cause: `app.main.limiter`
is a single module-level instance shared by *every* test in the process (they
all import the same `app`), so its in-memory counters never reset between
tests. This was latent since Phase 1 — it just took the suite growing this
large to trigger. Fixed with an autouse `conftest.py` fixture that calls
`limiter.reset()` before each test, so tests stay isolated regardless of run
order or how many requests earlier tests made. Confirmed stable across two
full back-to-back runs (100/100 both times) after the fix. Worth noting for
production too: 100/minute per IP is tight enough that a single legitimate
user doing rapid-fire logging (a quick burst of habit/task/health entries)
could plausibly hit it — not fixed here since it's a product tuning
decision, not a bug, but flagging it for whoever sets the real production
value.

### Independent re-verification pass (before starting Phase 9)

Actually ran the full toolchain fresh rather than trusting the notes below at
face value: `pip install -r requirements.txt` into a clean venv, `pytest`,
`npm install`, `tsc -b --force`, `vite build`, a programmatic i18n key-parity
diff, and a repo-wide grep for hardcoded UI strings/secrets/mock data.

- **One real discrepancy found**: the Phase 6-8 note below claims
  `test_a_growing_pattern_updates_memory_instead_of_piling_up_duplicates`
  passes — it didn't; `pytest` failed it (`assert 2 == 1`). Investigated by
  reproducing the scenario directly against the service layer (bypassing
  the API) and printing every resulting memory: the production fix
  (`memory_service.supersede_stale_variants`) is actually correct — after
  4 matching events there is exactly one active "plain trigger" pattern
  memory, updated in place. The test itself was wrong: its filter
  (`"after coffee" in content.lower()`) also matched a second, legitimately
  distinct pattern — the trigger-*and*-time-of-day combo pattern, which
  independently and correctly mentions "after coffee" in its own
  description. Two different real patterns aren't a duplicate. Narrowed the
  test's filter to the plain-trigger pattern's actual identity prefix and
  added an explicit "no stale count variant survives" assertion across all
  pattern types. **No production code changed** — this was a test-only fix.
- **Everything else held up**: 90/90 backend tests pass, frontend typechecks
  and builds clean (73 modules), i18n key parity is 152/152 with no
  identical-value (untranslated-looking) entries, and the hardcoding sweep
  (secrets/keys, mock/placeholder data, hardcoded dates/deadlines) came back
  clean — the few hits were comments explaining why the code avoids those
  patterns, not violations.

### Verification note (Phase 8 pass)

Same full-toolchain verification as the Phase 7 pass, run before and after
building Phase 8.

- **Audit of Phases 0-7 first**: ran `pip install -r requirements.txt` +
  `pytest` (65/65 passing), `npm install` + `tsc --noEmit` + `vite build`
  (clean), and a programmatic i18n key-parity diff (111/111 `en.json`/
  `te.json` keys matched) before writing any Phase 8 code. No issues found
  in Phases 0-7.
- **Backend**: 88 tests pass (`pytest`) — the 65 from Phases 1-7 plus 23 new
  ones for Phase 8 (countdowns + notification engine), including cross-user
  authorization, dedupe-on-repeat-refresh, the daily cap, and quiet-hours
  deferral.
- **Frontend**: typechecks clean (`tsc --noEmit`) and builds clean (`npm run
  build`, 73 modules, no errors).
- **i18n parity**: verified programmatically after adding the new
  `countdowns` and `notifications` namespaces plus two `nav.*` keys —
  152/152 keys match between `en.json` and `te.json`, no gaps either
  direction, with real Telugu translations (not transliteration).
- **Real bug found and fixed during this pass**: the same SQLite
  naive-vs-aware-datetime issue documented in the Phase 7 note above
  recurred in `countdown_service.get_next_active_countdown` — it compared
  an offset-aware "now" against `target_datetime` as read back from SQLite
  (naive), which would raise on first real use. Fixed with the same
  `_as_aware_utc()` normalizer pattern already used in `smoking_service`.
  Worth grep-ing for any *new* raw datetime comparisons a future phase adds
  against model fields — this class of bug will keep recurring under the
  SQLite test database unless comparisons are normalized every time.
- **Known pre-existing gaps, not introduced this pass, flagged for
  visibility**: (1) there is no ESLint config file anywhere in the
  frontend (`npx eslint .` fails immediately with "couldn't find an
  eslint.config.js") even though `eslint` itself is a devDependency —
  section 26 calls for this tooling to exist but it was never wired up in
  Phases 1-7. (2) there are no frontend component/route tests at all
  (`npx vitest run` finds zero test files) — section 26 explicitly asks for
  "frontend component and route tests." Neither blocks Phase 8's own
  functionality (backend tests + manual/typecheck verification cover it),
  but both are real section-26 shortfalls that should be closed out before
  Phase 13's "security hardening + tests" is called done — flagging now
  rather than letting them silently persist for another 5+ phases.

### Fixed in this review pass (Phase 9 audit)
Read through Phase 9 end to end before starting Phase 10. Found three real
bugs — all now fixed:

- **Call language override was completely inert.** `VoiceCall.language`
  could be set to something different from the user's
  `Profile.preferred_language` — `test_explicit_language_overrides_profile_preference`
  even proved the row stored it correctly — but the actual message-sending
  endpoint (`POST /conversations/{id}/messages`, reused unchanged by calls
  per this phase's own design) only ever read
  `current_user.profile.preferred_language` when building the AI's system
  prompt. It had no way to know a call-specific override existed. A call
  explicitly started in English while the profile default was Telugu would
  still generate Telugu-instructed replies — the stored language was purely
  cosmetic, and "mixed" (section 13's third required option) had nothing to
  map onto at all. Fixed by adding `Conversation.language_override`
  (migration `0009_conversation_language_override.py`, `NULL` for ordinary
  text chat), setting it in `voice_call_service.start_call`, and having
  `ram_core.handle_user_message` prefer it over the profile default —
  `"mixed"` correctly maps onto the existing Telugu/code-switching
  instruction rather than needing a new branch. Added four tests to
  `test_calls.py`, including one that patches `app.ai.ram_core.get_provider`
  to capture the actual `system_prompt` string sent for generation — proving
  the fix changes real AI behavior, not just the stored row — plus a
  regression test confirming ordinary (non-call) conversations are
  unaffected by the new column.
- **Recording metadata could be stored for calls that never had recording
  enabled.** `voice_call_service.end_call` wrote
  `recording_local_reference`/`recording_duration_seconds` from the client's
  payload unconditionally, so a careless or buggy client could report a
  "recording" for a call started with `recording_enabled=False`, leaving an
  internally inconsistent row (`recording_enabled=False` alongside a
  populated reference). Fixed by guarding both writes on
  `call.recording_enabled`; added
  `test_recording_metadata_is_ignored_if_recording_was_never_enabled`.
- **"Mixed" was never actually selectable in the UI.** `CallScreen`
  derived its language purely from `user.profile.preferred_language`
  (which is only ever `"en"`/`"te"` — a Profile can never itself be
  `"mixed"`), with no selector control at all, even though the backend
  schema (`VoiceCallCreate.language`) fully supported the third option.
  Added an En/Telugu/Mixed selector to the call setup screen backed by new
  `selectedLanguage` state, plus the `call.languageLabel` /
  `call.language.{en,te,mixed}` i18n keys in both `en.json` and `te.json`
  (real Telugu translations, not transliteration; re-verified 176/176 key
  parity with no gaps either direction after adding them).

Everything else in Phase 9 held up under review: the recording-stays-
client-side architecture, reusing Phase 3's exact `handle_user_message`
pipeline for call turns with zero forked AI logic, the `AlreadyEndedError`
-> 409 handling, and ownership boundaries on every new endpoint. All fixes
from every prior review pass remain intact — re-checked, not assumed.

### Fixed in this review pass (Phase 6-8 audit)
Read through Phases 6-8 end to end before touching Phase 9. Found two real,
confirmed bugs — both now fixed:

- **Finance affordability double-counting**
  (`finance_service.check_affordability`): a recurring expense (e.g. this
  month's rent, logged with `frequency="monthly"`) was being subtracted
  twice — once via its normalized monthly share
  (`estimated_recurring_monthly_expenses`), and again in full via
  `expenses_this_month` if it happened to be logged this calendar month.
  That silently understated how much money was actually available, which
  is the opposite of the "transparent, not fake-certain" math section 12
  asks for. Confirmed by the test suite itself: `test_finance.py` had a
  test whose own comment described the double-count as expected behavior
  ("same entry, counted once in the recurring estimate and once as this
  month's actual logged spend") rather than catching it as a bug. Fixed the
  calculation to only add **one-time** expenses logged this month on top of
  the recurring baseline — a recurring bill already represented in the
  baseline is never subtracted a second time just because this month's
  occurrence has been logged. Rewrote the misleading test and added a new
  one (`test_affordability_adds_one_time_expenses_on_top_of_recurring_baseline`)
  covering the corrected behavior.
- **Smoking pattern memories piling up instead of updating**
  (`smoking_service.detect_patterns`): each detected pattern's description
  embeds a live count (`"...3 times in the last 30 days"` →
  `"...4 times..."` on the next qualifying event). `memory_service._upsert`
  dedups on **exact** content match, so every time the count changed, the
  lookup missed and a brand-new "active" memory was inserted instead of
  updating the existing one — a user with a recurring trigger would
  accumulate a growing pile of near-duplicate `behavior_pattern` memories
  (3 times / 4 times / 5 times, all simultaneously "active"), which is
  exactly the "uncontrolled archive" the master doc's memory section (8)
  rules out, and directly contradicts `_upsert`'s own docstring intent
  ("refreshes... instead of piling up near-duplicate memories"). Added
  `memory_service.supersede_stale_variants()`: called with a stable prefix
  (the part of the description that doesn't change) right before
  `store_inferred_pattern`, it marks any earlier variant of the *same*
  pattern as `superseded` so the exact-match upsert starts clean and only
  one current row stays active. Added
  `test_a_growing_pattern_updates_memory_instead_of_piling_up_duplicates`
  to `test_smoking.py` proving a 4th matching event replaces the 3-event
  variant rather than sitting alongside it.

Everything else in Phases 6-8 held up under review: countdown repeat-rule
rollover (including month-end/leap-year edge cases), the notification
engine's priority ordering / daily cap / quiet-hours deferral / dedupe-key
idempotency, and ownership boundaries across every new endpoint. All prior
fixes from the Phase 1-5 and Phase 8 verification passes below remain
intact — re-checked as part of this pass, not just assumed.

### Fixed in the Phase 1-5 review pass
- **`tests/conftest.py`**: `from app.main import app` followed by
  `import app.models` silently rebound the local name `app` from the FastAPI
  instance to the top-level `app` *package*, so `app.dependency_overrides`
  didn't exist and every single test errored at setup. Fixed by importing
  the submodule without shadowing the name (`from app import models as
  _models`).
- **Production-breaking dependency gap**: `requirements.txt` never pinned
  `bcrypt`, so a fresh install resolves the latest bcrypt (5.x), which is
  incompatible with the unmaintained `passlib` 1.7.4 — passlib's own
  backend self-test crashes on load, meaning **every password hash/verify
  call would fail in production**, not just locally. Pinned
  `bcrypt==4.0.1`.
- **Cross-dialect UUID type**: every model used
  `sqlalchemy.dialects.postgresql.UUID`, which only reliably round-trips as
  a Python `uuid.UUID` on the Postgres dialect — reading a row back under
  SQLite (or any non-Postgres path) can hand back a plain string, which
  then fails on the next query that uses it as a bind parameter. Replaced
  with SQLAlchemy's generic `sqlalchemy.Uuid` type everywhere (still
  compiles to native `UUID` on Postgres in production; migrations
  targeting Postgres directly are untouched).
- **Message ordering bug**: `Message.created_at` (and the shared
  `TimestampMixin` used by every other model) relied solely on
  `server_default=func.now()`. On SQLite this only has whole-second
  resolution, so messages saved in the same request burst got identical
  timestamps and sorted unpredictably — this also matters on Postgres
  under bursty writes, just less often. Added a Python-side
  microsecond-precision default (`datetime.now(timezone.utc)`) alongside
  the server default.
- A test in `test_memory.py` passed the JSON-string form of a user id where
  every real call site passes an actual `uuid.UUID` — fixed the test to
  match production usage.
- **Frontend**: `src/vite-env.d.ts` (the file that declares
  `ImportMetaEnv`/`ImportMeta` for Vite) was missing entirely, so
  `import.meta.env.VITE_API_BASE_URL` — the one thing standing between
  this app and a hardcoded backend URL — didn't typecheck. Added it;
  `tsc -b` and `vite build` are now clean.
- **i18n / zero-hardcoding audit**: `TodayScreen`, `HabitsScreen`,
  `TalkScreen`, and especially `HealthScreen` had a substantial amount of
  hardcoded English UI text (section headers, button labels, empty-state
  copy, form placeholders, meal/mood option labels) that bypassed i18n
  entirely — a Telugu user would have seen raw English on those screens
  regardless of language setting. Added the missing keys to both
  `en.json` and `te.json` (with real Telugu translations, not
  transliteration) and wired every screen to `useTranslation`. Ran a
  repo-wide grep sweep afterward (`>text<` not wrapped in `t(...)`, plus
  raw `placeholder="..."` attributes) — no further hardcoded UI copy found
  outside the Phase 6+ screens that don't exist yet.
- Verified the rest of the zero-hardcoding requirement by inspection: no
  hardcoded secrets/API keys, no hardcoded production URLs (only
  documented localhost dev fallbacks in `config.py`/`apiClient.ts`, both
  overridable by environment variable), no mock/placeholder dashboard
  data, no seeded user content.

All 43 backend tests pass (`pytest`), and the frontend typechecks and
builds cleanly (`tsc -b`, `vite build`) as of this pass.


### What's implemented
- **Personal ML + predictions (Phase 10):** `ModelVersion`/`ModelFeature`/
  `Prediction`/`PredictionFeedback` (section 19) under `/api/v1/predictions/*`.
  Two prediction types — `smoking_risk` (predicted before the outcome is
  logged, from trigger/intensity/stress) and `habit_adherence` (today's
  completion odds, from day-of-week/rolling completion rate/streak) — both
  backed by a hand-rolled, dependency-free logistic regression
  (`app/ml/model.py`) rather than scikit-learn, verified against synthetic
  data before being wired in. Every prediction carries one of four honestly-
  labeled confidence tiers (`no_data`/`baseline_low_data`/
  `model_limited_data`/`model`) so a thin-data guess is never presented with
  the same confidence as a well-trained one — see the Phase 10 section above
  for the full reasoning. A one-time-per-prediction feedback endpoint closes
  section 9's extract→train→predict→feedback loop. Frontend: `InsightsScreen`
  (risk/adherence checks, prediction history with confidence + explanation
  always shown together, feedback buttons, model-version history), full
  en/te i18n parity.
- **Voice calls (Phase 9):** `VoiceCall` model/endpoints wrapping the
  existing Phase 3 conversation pipeline unchanged; browser-native
  `SpeechRecognition`/`SpeechSynthesis` (no server-side STT/TTS credential
  to abstract) with a manual text-composer fallback when unavailable;
  local-only recording via `MediaRecorder` with the section-13 naming
  convention (documented as an honest placeholder for Phase 11's native
  `Filesystem` API, not a fake version of local storage). See the Phase 9
  section above for the full writeup, including the rate-limiter test-
  isolation bug found and fixed while building it.
- **Countdowns + notification engine (Phase 8):** `Countdown` (section 17) —
  completely user-created, database-driven CRUD under
  `/api/v1/countdowns/*` (title, target date/time, category, notes,
  priority, repeat rule, per-countdown notification offsets). No
  countdown/exam/hackathon/deadline is ever seeded — a brand-new user sees
  an empty list, verified by test. A repeating countdown (daily/weekly/
  monthly/yearly) that's passed its target rolls forward automatically
  (plain, capped date arithmetic — not a full RFC 5545 engine, documented
  in `app/services/countdown_service.py`). The soonest active countdown
  surfaces on `/api/v1/today` for the home screen's "active countdown"
  element (section 16).
  - `Notification` + `NotificationPreference` (section 18) —
    `app/services/notification_service.py` is the actual intervention/
    reminder engine, not a static reminder list. It generates three kinds
    of notification from a user's own data, each idempotent via a
    dedupe key so re-running never duplicates: **deadline** (from
    countdown offsets), **habit_intervention** (a habit due today, still
    unlogged, once the day passes a risk hour — reuses `habit_service`
    rather than re-deriving due/streak logic), and **behavioral**, which
    wires directly into Phase 7's `smoking_service.detect_patterns` — the
    exact follow-up the Phase 7 README note flagged. Non-spam is enforced
    by real per-user preferences, not a suggestion: a daily cap
    (deadlines prioritized first when the cap is tight), per-type
    enable/disable, and quiet hours that *defer* a notification's
    trigger time rather than dropping it.
  - Generation is on-demand (`POST /api/v1/notifications/refresh`), not a
    background cron — there's no task scheduler/worker anywhere in this
    codebase yet (that's Phase 13 infra). `generate_for_user` is exactly
    the function a future scheduled job would call per user; nothing about
    its logic changes when that scheduler exists, only what calls it and
    how often. This is stated plainly in the code and on the frontend
    ("Check for new notifications" button), not hidden behind a fake
    always-on notification feed.
  - Frontend: a Countdowns screen (create/list/deactivate/delete, live
    time-remaining display) and a Notifications screen (refresh, feed with
    dismiss/mark-handled actions, and real persisted preferences for daily
    cap/quiet hours/per-type toggles), both wired into home nav. The
    home screen's previously-placeholder "active countdown" section now
    shows the real soonest countdown from `/today`. Full i18n parity
    (en/te, 152/152 keys) verified programmatically.
- **Smoking intervention (Phase 7):** `SmokingEvent` — trigger (free text),
  craving intensity (1-10), optional stress level and context, outcome
  (resisted | alternative_used | smoked), optional alternative action, and
  an optional reflection note added after the fact. `smoking_events`,
  `cravings`, and `triggers` from sections 10/19 are modeled as one table —
  same reasoning as the Memory merge (Phase 3) and FinancialGoal merge
  (Phase 6), documented in `app/models/smoking.py`. A "smoked" outcome is
  recorded through the exact same code path, validation, and status code as
  any other outcome — no shaming logic anywhere, per section 5's failure
  protocol.
  - `/api/v1/smoking/summary`: 30-day counts (total/resisted/
    alternative_used/smoked), a smoke-free streak in days since the last
    "smoked" event (`null`, not 0, when nothing's ever been logged — same
    honest-unknown convention as `HealthTodaySummary.calories_total`), the
    most recent event overall, and detected patterns.
  - **Pattern detection** (`smoking_service.detect_patterns`): the first
    domain past plain CRUD logging. A deterministic, transparent frequency
    count — explicitly *not* ML (that's Phase 10) — over a user's own
    "smoked" events in the last 30 days, looking for a recurring trigger, a
    recurring time-of-day, or the two combined recurring together at least
    3 times. Every pattern returned states its own evidence (occurrences,
    window) rather than a bare confidence score.
  - **The RAM Core hook**: when a pattern clears the threshold, it's written
    into the existing `Memory` table via the new
    `memory_service.store_inferred_pattern` (category=`behavior_pattern`,
    source=`ai_inferred`, confidence capped at 0.85 and scaled by
    occurrence count). Because `ram_core.py` already retrieves active
    memories into every conversation's system prompt, a detected pattern
    surfaces to Ram in the very next conversation — labeled INFERRED, never
    a settled fact — with **no smoking-specific code added to
    `ram_core.py` or `personality.py`**. This is the "detect and intervene
    earlier" behavior section 10 describes, built on infrastructure that
    already existed.
  - Frontend: a working Smoking screen (streak/count stats, a plain-language
    list of detected patterns with an honest empty state when there isn't
    enough data yet, craving/outcome logging, and a no-shame reflection
    prompt — "no excuses, no judgment — just understanding" — that appears
    under any event without a reflection yet), wired into home nav. Full
    i18n parity (en/te) verified programmatically.
- **Finance (Phase 6):** `Income`, `Expense`, `Budget`, `FinancialGoal` —
  full CRUD under `/api/v1/finance/*`. `Budget` is upserted per
  `(user, category)`, same idempotency pattern as `SleepLog` (Phase 5),
  enforced with a DB unique constraint as well as in the service layer.
  `savings` and `debt` from section 12/19 are modeled as one
  `FinancialGoal` table distinguished by `goal_type` (savings |
  debt_payoff) — same reasoning as the Memory/lessons/behavior_patterns
  merge in Phase 3, documented in `app/models/finance.py`.
  - `/api/v1/finance/summary`: current-month snapshot — estimated monthly
    income/recurring-expenses (recurring entries normalized to a monthly
    figure: weekly x 52/12, biweekly x 26/12, yearly / 12; one-time entries
    aren't counted as recurring), what's actually been logged this
    calendar month, per-category budget status (limit vs. spent vs.
    remaining, computed from real logged expenses), and active financial
    goals.
  - `/api/v1/finance/affordability`: the "Can I afford this?" calculation
    from section 12. Returns the estimated available amount alongside the
    assumptions used and caveats about what it doesn't know — never a bare
    yes/no. If no income has been logged yet, it returns `null` for the
    verdict and available-amount fields rather than fabricating a number,
    with a caveat explaining why.
  - Frontend: a working Finance screen (summary stats, budget/goal
    lists, an affordability checker showing its assumptions and caveats,
    income/expense logging), wired into home nav. Full i18n parity
    (en/te) verified programmatically — no missing or extra keys between
    the two locale files.
- **Health tracking (Phase 5):** `DietLog`, `WaterLog`, `SleepLog`,
  `WorkoutLog`, `MoodLog` — full CRUD under `/api/v1/health/*`, plus a
  `/api/v1/health/today` aggregation (water total, calories total — `null`,
  not a fabricated 0, when nothing logged calories — last night's sleep,
  today's workouts, latest mood). Sleep is upserted per `(user, sleep_date)`,
  same idempotency pattern as habit logging, enforced with a DB unique
  constraint as well as in the service layer. Duration is derived from
  bedtime/wake_time when both are given, or taken directly when the user
  only knows the total. Nothing here diagnoses anything — mood/journal
  entries are self-report only, consistent with the safety boundaries RAM
  Core already enforces. Frontend: a working Health screen (quick-add water,
  mood check-in, meal/workout/sleep logging, today's summary), wired into
  home nav.
- **Foundation (Phase 1-2):** JWT auth, `User`/`Profile`, environment-driven
  config, restricted CORS, rate limiting, i18n (en/te), theme system.
- **Goals/Tasks/Habits (Phase 4):** full CRUD, completion/skip logging,
  single-daily-mission enforcement, streak calculation, `/today` aggregation.
- **RAM Core — AI conversation + structured memory (Phase 3):**
  - `Conversation`/`Message` models; `/api/v1/conversations` endpoints for
    creating a conversation and exchanging messages.
  - `Memory` model with category (fact/preference/goal_context/
    habit_context/lesson/behavior_pattern/context), source (user_stated vs.
    conversation_extracted), confidence, relevance, and status — plus
    `/api/v1/memories` for the user to view/archive/delete what's stored
    about them.
  - `app/ai/personality.py` encodes the product's original personality and
    safety boundaries (never a doctor/therapist/financial fiduciary, no
    diagnosing, no manipulation, crisis situations point to real support)
    and explicitly labels every retrieved memory KNOWN or INFERRED in the
    prompt so the model can't present a guess as a settled fact.
  - `app/ai/ram_core.py` orchestrates: save user message → retrieve memory →
    build prompt → call provider → save reply → write back proposed memory
    updates (always as inferred/extracted, never as user-stated).
  - Provider abstraction: a real `AnthropicProvider` (httpx call to the
    Messages API, model/tokens all config-driven) and a `DeterministicProvider`
    fallback used automatically when no `ANTHROPIC_API_KEY` is set — so the
    whole pipeline runs in tests/dev without network, and production failures
    degrade to a clearly-labeled fallback message instead of losing the
    user's input or crashing.
  - Frontend: a working Talk screen (text chat wired to the real endpoint,
    optimistic send, honest fallback-message styling) plus, as of Phase 9,
    a separate Call screen for the actual phone-call experience — see the
    Phase 9 section above.
- Pytest coverage across every domain, including cross-user authorization
  tests and a simulated-provider-outage test proving the user's message
  survives even when generation fails.

### Scoped decisions worth knowing about
- Countdown repeat rollover (section 17) is plain date arithmetic for the
  four rules the master doc asks for (daily/weekly/monthly/yearly), not a
  full RFC 5545 recurrence engine — see `countdown_service._add_interval`.
  Good enough for what's asked; worth swapping for a real recurrence
  library only if a future phase needs rules beyond these four.
- The notification engine runs on-demand (a `/refresh` endpoint the
  frontend calls), not on a schedule — there's no cron/worker
  infrastructure in this codebase yet. That's explicitly Phase 13 scope
  ("security hardening + tests + deployment" is where infra like this
  would land); `notification_service.generate_for_user` is written so a
  future scheduled job can call it per-user with zero logic changes.
- Quiet hours defer a notification's `trigger_at` to the end of the quiet
  window rather than skipping generation — chosen so a real deadline never
  silently gets lost because it happened to compute at 2am, at the cost of
  the notification not being exactly "generated in real time" during quiet
  hours. `smoking_events`, `cravings`, and `triggers` (sections 10/19) are one
  `SmokingEvent` table with `trigger` as free text rather than three tables
  with a trigger lookup table — see `app/models/smoking.py`. Same reasoning
  as the two merges below.
- Pattern detection is a plain frequency count with a fixed threshold
  (3 occurrences in 30 days), not a statistical or ML model — an honest
  placeholder for Phase 10's actual personal ML work, not a claim of
  smarter detection than it does. The thresholds/window are constants at
  the top of `smoking_service.py`, not hardcoded inline, if they need
  tuning later.
- The master doc lists `memories`, `lessons`, and `behavior_patterns` as
  separate tables. They're modeled as one `Memory` table distinguished by
  `category` for now, since they share identical metadata and access
  patterns — noted in `app/models/memory.py` if this needs revisiting.
- Memory retrieval for the prompt is relevance/recency-based, not semantic/
  embedding search. That's honestly a placeholder pending the Phase 10
  personal ML work, not a claim of smarter retrieval than it does.
- Similarly, `savings` and `debt` (section 12/19) are one `FinancialGoal`
  table distinguished by `goal_type` rather than two tables — see
  `app/models/finance.py`.
- `FinancialGoal.current_amount` is updated directly via `PATCH` rather than
  through a separate contribution-log table. This mirrors how `Goal`
  (Phase 2) works — plain CRUD, no log table — rather than the
  `Habit`/`HabitLog` pattern. If an auditable history of contributions
  matters later, that's a straightforward addition on top of the existing
  `FinancialGoal` CRUD, not a redesign.

### What's not built yet
The native Android home-screen widget, and production security
hardening/deployment (Phases 11-13). Also flagged above as pre-existing
gaps to close before Phase 13 is called done: no ESLint config, no frontend
component/route tests (Phase 10 added `InsightsScreen.tsx` and
`app/ml/model.py`/`app/ml/features.py` without dedicated frontend tests,
for the same reason). Phase 9 (voice calls)'s two honestly-scoped gaps
still stand: the recording container format is webm/ogg rather than
`.m4a`, and "save locally" is a browser download rather than a write into
a real native folder — both genuinely need Phase 11's Capacitor
`Filesystem` integration to close. Phase 10's prediction-feedback loop is
one step short of section 9's full "outcome feedback → model evaluation"
description: feedback is recorded and does flow back in as a labeled
training example next time that prediction_type is retrained (which
happens automatically), but there's no explicit calibration/evaluation
report (e.g. predicted-vs-actual accuracy over time) — a reasonable
Phase 13+ QA addition.

## Running the backend locally

### Option A: Docker Compose (Postgres + backend, closest to production shape)

```bash
cp backend/.env.example backend/.env   # edit JWT_SECRET_KEY at minimum
docker compose up --build
```

### Option B: plain virtualenv (matches every prior pass's instructions)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set a real DATABASE_URL (local Postgres), a random
# JWT_SECRET_KEY, and — to get real AI replies instead of the deterministic
# placeholder — a real ANTHROPIC_API_KEY

alembic upgrade head
uvicorn app.main:app --reload
```

Run tests (uses an in-memory SQLite engine and the deterministic AI
provider, no Postgres or Anthropic credentials required):

```bash
pytest
```

## Running the frontend locally

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev
```

Voice calls need a real browser (Chrome/Android WebView) over HTTPS or
`localhost` for `SpeechRecognition`/`getUserMedia` to work — the manual
text-input fallback in `CallScreen.tsx` covers everything else.

## Next recommended step

First, actually run what this pass added — nothing in it has executed yet
(no network in the sandbox that wrote it):

```bash
cd backend && pip install -r requirements.txt && pytest
cd ../frontend && npm install && npm run lint && npm run build && npm test
```

Fix whatever that surfaces before trusting the Phase 13 work above. Once
it's green, push to a repo with the `.github/workflows/ci.yml` in place so
it stays green automatically.

Then, finish Phase 11 by generating the actual native Android project:
`npx cap add android` in an environment with real npm/Java/Gradle access
(this sandbox doesn't have one), then add the permission lines documented
above (`RECORD_AUDIO`, notifications) to the generated
`AndroidManifest.xml`. Everything on the JS/TS side that Phase 11 needed —
token storage via `Preferences`, native notifications, back-button
handling, speech-error UX, and `Filesystem`-backed call recording — is
done; what's left is specifically the native build artifacts themselves,
which can't be honestly hand-authored without running the real generator.
The container-format gap (webm/ogg vs. the doc's `.m4a`) is a separate,
smaller follow-up once the Android project exists — it needs a native
audio-capture plugin, not anything in `callRecorder.ts`'s current
Filesystem-writing logic.

Once the Android project builds, Phase 12's staged widget
(`android-native-widget-staging/`) can be integrated for real, and the
remaining Phase 13 items (refresh-token rotation/revocation, a real
deployment run against the `render.yaml`/`vercel.json` added this pass, and
confirming CI is actually green) close out the phase.

Separately from phase sequencing: broader frontend test coverage (every
screen past auth is still untested) is cheap to close incrementally and
worth doing opportunistically rather than in one large pass.
