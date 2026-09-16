package com.wakeupram.app.widget

import android.content.Context

/**
 * Maps each placed widget instance (appWidgetId, assigned by Android when
 * the user adds it to a home screen) to either a specific countdown_id the
 * user picked in CountdownWidgetConfigureActivity, or "soonest active"
 * mode (no countdown_id stored — falls back to GET /api/v1/today's
 * active_countdown). This is what satisfies the master doc's "Widget
 * content must be dynamic and user-configurable. Do not hardcode one
 * countdown." — two widgets on the same home screen can show two
 * different countdowns, or either can track "whatever's soonest" and
 * follow it automatically as countdowns are added/completed/expire.
 *
 * Deliberately a separate SharedPreferences file from Capacitor's own
 * ("CapacitorStorage", read in CountdownApiClient) — this is
 * widget-instance config, not app auth state, and keeping them apart
 * means clearing one can never accidentally corrupt the other.
 */
object CountdownWidgetPrefs {
    private const val PREFS_FILE = "countdown_widget_config"
    private fun keyFor(appWidgetId: Int) = "countdown_id_for_widget_$appWidgetId"

    fun saveSelection(context: Context, appWidgetId: Int, countdownId: String?) {
        val prefs = context.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
        val editor = prefs.edit()
        if (countdownId == null) {
            editor.remove(keyFor(appWidgetId)) // absence = "soonest active" mode
        } else {
            editor.putString(keyFor(appWidgetId), countdownId)
        }
        editor.apply()
    }

    /** Null return means "soonest active" mode, not "unconfigured error". */
    fun getSelection(context: Context, appWidgetId: Int): String? {
        val prefs = context.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
        return prefs.getString(keyFor(appWidgetId), null)
    }

    fun clearSelection(context: Context, appWidgetId: Int) {
        context.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
            .edit()
            .remove(keyFor(appWidgetId))
            .apply()
    }
}
