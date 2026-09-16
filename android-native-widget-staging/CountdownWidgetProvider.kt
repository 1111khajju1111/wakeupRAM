package com.wakeupram.app.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import androidx.work.Data
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * Intentionally thin: onUpdate/onEnabled/onDeleted only enqueue or cancel
 * WorkManager jobs and clean up SharedPreferences — they never touch the
 * network directly, since AppWidgetProvider callbacks run on the main
 * thread and a blocking HTTP call there would throw
 * NetworkOnMainThreadException. See CountdownWidgetUpdateWorker for the
 * actual fetch + RemoteViews paint logic.
 */
class CountdownWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        val request = OneTimeWorkRequestBuilder<CountdownWidgetUpdateWorker>()
            .setInputData(Data.Builder().putIntArray(CountdownWidgetUpdateWorker.KEY_WIDGET_IDS, appWidgetIds).build())
            .build()
        WorkManager.getInstance(context).enqueue(request)
    }

    /** Called once, when the first widget instance of this type is placed
     * — this is where the recurring refresh schedule gets registered, not
     * per-instance (WorkManager's periodic work here refreshes every
     * placed instance each tick, per CountdownWidgetUpdateWorker.doWork's
     * "no specific IDs requested -> refresh all" branch). */
    override fun onEnabled(context: Context) {
        val periodicRequest = PeriodicWorkRequestBuilder<CountdownWidgetUpdateWorker>(30, TimeUnit.MINUTES)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            CountdownWidgetUpdateWorker.PERIODIC_WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            periodicRequest,
        )
    }

    /** Called once the last instance is removed — cancel the now-pointless
     * periodic schedule rather than leave it running forever in the
     * background for widgets nobody has on a home screen anymore. */
    override fun onDisabled(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(CountdownWidgetUpdateWorker.PERIODIC_WORK_NAME)
    }

    /** Clean up each removed instance's stored countdown selection — an
     * appWidgetId can be reassigned to a different widget placement later,
     * and a stale selection under a reused ID would silently show the
     * wrong countdown rather than the "soonest active" default. */
    override fun onDeleted(context: Context, appWidgetIds: IntArray) {
        for (appWidgetId in appWidgetIds) {
            CountdownWidgetPrefs.clearSelection(context, appWidgetId)
        }
    }
}
