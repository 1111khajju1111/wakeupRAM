package com.wakeupram.app.widget

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.widget.RemoteViews
import androidx.work.Worker
import androidx.work.WorkerParameters
import com.wakeupram.app.R

/**
 * Plain (non-Coroutine) Worker so the only new Gradle dependency needed is
 * androidx.work:work-runtime — not work-runtime-ktx, which would pull in
 * kotlinx-coroutines-android as well. WorkManager already runs doWork() on
 * a background thread from its own executor, so a blocking network call
 * here is safe (unlike in AppWidgetProvider.onUpdate, which runs on the
 * main thread and would throw NetworkOnMainThreadException).
 *
 * Two trigger paths, both enqueueing this same Worker (see
 * CountdownWidgetProvider.kt and CountdownWidgetConfigureActivity.kt):
 *   1. Periodic, via WorkManager's periodic work request registered in
 *      onEnabled() — refreshes every currently-placed widget instance.
 *      Android widget updates realistically can't be sub-15-minute (that's
 *      WorkManager's own enforced minimum periodic interval), so this is
 *      a "remaining time, accurate to within ~15-30 min" display, not a
 *      live ticking clock — an honest constraint of home-screen widgets in
 *      general, not a shortcut specific to this implementation.
 *   2. One-off, enqueued immediately after the user finishes configuring a
 *      widget, so it paints real data on the very first frame instead of
 *      sitting on the loading state until the next periodic tick.
 */
class CountdownWidgetUpdateWorker(
    context: Context,
    params: WorkerParameters,
) : Worker(context, params) {

    override fun doWork(): Result {
        val appWidgetManager = AppWidgetManager.getInstance(applicationContext)
        val requestedIds = inputData.getIntArray(KEY_WIDGET_IDS)
        val appWidgetIds = if (requestedIds != null && requestedIds.isNotEmpty()) {
            requestedIds
        } else {
            appWidgetManager.getAppWidgetIds(
                ComponentName(applicationContext, CountdownWidgetProvider::class.java)
            )
        }

        for (appWidgetId in appWidgetIds) {
            updateOne(appWidgetManager, appWidgetId)
        }

        // Always success: a per-widget network failure is handled inside
        // updateOne() as an "unavailable" RemoteViews state, not a Worker
        // failure — retrying the whole batch because one countdown's
        // request timed out would be wasteful, and WorkManager's own
        // periodic schedule already provides the next retry.
        return Result.success()
    }

    private fun updateOne(appWidgetManager: AppWidgetManager, appWidgetId: Int) {
        val views = RemoteViews(applicationContext.packageName, R.layout.widget_countdown)
        val selectedId = CountdownWidgetPrefs.getSelection(applicationContext, appWidgetId)

        val countdown = try {
            if (selectedId != null) {
                CountdownApiClient.fetchCountdown(applicationContext, selectedId)
            } else {
                CountdownApiClient.fetchSoonestActiveCountdown(applicationContext)
            }
        } catch (e: Exception) {
            null
        }

        when {
            countdown == null && selectedId == null -> {
                // Real, honest empty state — not an error. Matches
                // CountdownsScreen.tsx's noCountdownsYet copy in spirit:
                // nothing here is ever pre-populated, so "none yet" is an
                // expected state, not a failure to explain away.
                views.setTextViewText(R.id.widget_countdown_title, applicationContext.getString(R.string.widget_no_active_countdown))
                views.setTextViewText(R.id.widget_countdown_remaining, "")
            }
            countdown == null -> {
                // A specific countdown_id was configured but couldn't be
                // fetched (deleted since, deactivated, network/auth
                // failure) — distinct copy from "no countdowns exist at
                // all", so the user knows to reopen the app and
                // reconfigure rather than assume everything's fine.
                views.setTextViewText(R.id.widget_countdown_title, applicationContext.getString(R.string.widget_unavailable))
                views.setTextViewText(R.id.widget_countdown_remaining, "")
            }
            else -> {
                views.setTextViewText(R.id.widget_countdown_title, countdown.title)
                val remaining = CountdownTimeFormatter.formatRemaining(
                    countdown.targetDatetimeIso,
                    overdueLabel = applicationContext.getString(R.string.widget_overdue),
                    daysHoursFmt = applicationContext.getString(R.string.widget_remaining_days_hours),
                    hoursMinutesFmt = applicationContext.getString(R.string.widget_remaining_hours_minutes),
                    minutesFmt = applicationContext.getString(R.string.widget_remaining_minutes),
                )
                views.setTextViewText(
                    R.id.widget_countdown_remaining,
                    remaining ?: applicationContext.getString(R.string.widget_unavailable)
                )
            }
        }

        appWidgetManager.updateAppWidget(appWidgetId, views)
    }

    companion object {
        const val KEY_WIDGET_IDS = "widget_ids"
        const val PERIODIC_WORK_NAME = "countdown_widget_periodic_refresh"
    }
}
