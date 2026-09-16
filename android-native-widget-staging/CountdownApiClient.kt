package com.wakeupram.app.widget

import android.content.Context
import com.wakeupram.app.BuildConfig
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Deliberately dependency-free: java.net.HttpURLConnection + org.json, both
 * bundled with the Android SDK. A widget process is small and infrequently
 * run (WorkManager wakes it every 15-30 min at most — see
 * CountdownWidgetUpdateWorker) so pulling in OkHttp/Retrofit purely for
 * this would be a heavier dependency than the job needs.
 *
 * Talks to the exact same /api/v1/countdowns and /api/v1/auth/refresh
 * endpoints the JS frontend calls (see backend/app/api/v1/endpoints/
 * countdowns.py and auth.py, and frontend/src/services/apiClient.ts for
 * the refresh-on-401 pattern this mirrors) — verified against those source
 * files, not guessed.
 */
object CountdownApiClient {

    // TODO(verify): confirmed by reading Capacitor's documented Preferences
    // plugin behavior (stores via platform SharedPreferences, one file per
    // "group", default group name "CapacitorStorage"), NOT by inspecting
    // the actual compiled plugin class — this sandbox can't do that. Before
    // trusting this constant: once android/ exists for real, grep the
    // @capacitor/preferences Android plugin source (under
    // frontend/node_modules/@capacitor/preferences/android/.../
    // PreferencesPlugin.kt or .java, or the compiled AAR if that's already
    // gone) for the actual SharedPreferences file name it opens, and fix
    // this constant to match if it's different.
    private const val CAPACITOR_PREFS_FILE = "CapacitorStorage"

    // Matches frontend/src/services/tokenStorage.ts's STORAGE_KEY exactly —
    // confirmed against that file, not assumed.
    private const val TOKEN_STORAGE_KEY = "wake_up_ram.auth_tokens"

    data class Tokens(val accessToken: String, val refreshToken: String)

    /** Reads the same JSON blob the JS app wrote via Preferences.set(). */
    private fun readTokens(context: Context): Tokens? {
        val prefs = context.getSharedPreferences(CAPACITOR_PREFS_FILE, Context.MODE_PRIVATE)
        val raw = prefs.getString(TOKEN_STORAGE_KEY, null) ?: return null
        return try {
            val json = JSONObject(raw)
            Tokens(json.getString("accessToken"), json.getString("refreshToken"))
        } catch (e: Exception) {
            null
        }
    }

    private fun writeTokens(context: Context, tokens: Tokens) {
        val prefs = context.getSharedPreferences(CAPACITOR_PREFS_FILE, Context.MODE_PRIVATE)
        val json = JSONObject()
            .put("accessToken", tokens.accessToken)
            .put("refreshToken", tokens.refreshToken)
        prefs.edit().putString(TOKEN_STORAGE_KEY, json.toString()).apply()
    }

    /**
     * Mirrors apiClient.ts's tryRefreshToken(): POST /api/v1/auth/refresh
     * with {"refresh_token": ...}, persist the new pair on success.
     */
    private fun refreshTokens(context: Context, refreshToken: String): Tokens? {
        return try {
            val url = URL("${BuildConfig.API_BASE_URL}/api/v1/auth/refresh")
            val connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json")
                doOutput = true
                connectTimeout = 10_000
                readTimeout = 10_000
            }
            OutputStreamWriter(connection.outputStream).use {
                it.write(JSONObject().put("refresh_token", refreshToken).toString())
            }
            if (connection.responseCode != 200) return null

            val body = connection.inputStream.bufferedReader().use(BufferedReader::readText)
            val json = JSONObject(body)
            val newTokens = Tokens(json.getString("access_token"), json.getString("refresh_token"))
            writeTokens(context, newTokens)
            newTokens
        } catch (e: Exception) {
            null
        }
    }

    /** GET with Bearer auth, retrying once through a token refresh on 401 —
     * same one-retry guard as apiClient.ts's isRetry flag, for the same
     * reason (a refreshed token that still 401s means don't loop forever;
     * the account was likely deactivated server-side). */
    private fun authedGet(context: Context, path: String, isRetry: Boolean = false): String? {
        val tokens = readTokens(context) ?: return null

        val url = URL("${BuildConfig.API_BASE_URL}$path")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            setRequestProperty("Authorization", "Bearer ${tokens.accessToken}")
            connectTimeout = 10_000
            readTimeout = 10_000
        }

        return when (connection.responseCode) {
            200 -> connection.inputStream.bufferedReader().use(BufferedReader::readText)
            401 -> {
                if (isRetry) return null
                val refreshed = refreshTokens(context, tokens.refreshToken) ?: return null
                authedGet(context, path, isRetry = true)
            }
            else -> null
        }
    }

    /** Every field here matches backend/app/schemas/countdown.py's
     * CountdownRead exactly — verified against that source file. */
    data class WidgetCountdown(
        val id: String,
        val title: String,
        val targetDatetimeIso: String,
        val category: String?,
        val priority: String,
    )

    private fun parseCountdown(json: JSONObject): WidgetCountdown = WidgetCountdown(
        id = json.getString("id"),
        title = json.getString("title"),
        targetDatetimeIso = json.getString("target_datetime"),
        category = if (json.isNull("category")) null else json.optString("category"),
        priority = json.getString("priority"),
    )

    /** The widget's "soonest active" mode — GET /api/v1/today, take
     * active_countdown (may be null: an honest "nothing upcoming" empty
     * state, not an error). */
    fun fetchSoonestActiveCountdown(context: Context): WidgetCountdown? {
        val body = authedGet(context, "/api/v1/today") ?: return null
        val json = JSONObject(body)
        val countdownJson = json.optJSONObject("active_countdown") ?: return null
        return parseCountdown(countdownJson)
    }

    /** The widget's "specific countdown" mode, chosen in
     * CountdownWidgetConfigureActivity — GET /api/v1/countdowns/{id}. */
    fun fetchCountdown(context: Context, countdownId: String): WidgetCountdown? {
        val body = authedGet(context, "/api/v1/countdowns/$countdownId") ?: return null
        return parseCountdown(JSONObject(body))
    }

    /** For the configuration screen's picker list — GET
     * /api/v1/countdowns?active_only=true. */
    fun fetchActiveCountdowns(context: Context): List<WidgetCountdown> {
        val body = authedGet(context, "/api/v1/countdowns?active_only=true") ?: return emptyList()
        val array = org.json.JSONArray(body)
        return (0 until array.length()).map { parseCountdown(array.getJSONObject(it)) }
    }
}
