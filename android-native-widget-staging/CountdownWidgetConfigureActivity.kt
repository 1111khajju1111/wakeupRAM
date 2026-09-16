package com.wakeupram.app.widget

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.os.AsyncTask
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.ListView
import android.widget.ProgressBar
import android.widget.TextView
import androidx.work.Data
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.wakeupram.app.R

/**
 * Shown by Android automatically when the user drags this widget onto a
 * home screen (wired via android:configure in countdown_widget_info.xml —
 * see that file and the manifest snippet). Must call setResult(RESULT_OK)
 * or Android removes the widget it was about to place; that's standard
 * AppWidgetProvider contract, not specific to this app.
 *
 * Fetches the user's real countdown list from the backend for the picker —
 * never a placeholder/hardcoded list, consistent with section 17/22's "no
 * countdown may ever be hardcoded."
 */
class CountdownWidgetConfigureActivity : Activity() {

    private var appWidgetId: Int = AppWidgetManager.INVALID_APPWIDGET_ID

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_widget_configure)

        // Standard AppWidgetProvider contract: default to CANCELED so a
        // swipe-back or crash mid-setup doesn't leave a broken widget
        // placed on the home screen — only the explicit "Save" path below
        // sets RESULT_OK.
        setResult(RESULT_CANCELED)

        appWidgetId = intent?.extras?.getInt(
            AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID
        ) ?: AppWidgetManager.INVALID_APPWIDGET_ID

        if (appWidgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            finish()
            return
        }

        val listView = findViewById<ListView>(R.id.configure_countdown_list)
        val progressBar = findViewById<ProgressBar>(R.id.configure_loading)
        val emptyLabel = findViewById<TextView>(R.id.configure_empty_label)
        val soonestButton = findViewById<Button>(R.id.configure_use_soonest_active)

        soonestButton.setOnClickListener { saveAndFinish(countdownId = null) }

        // AsyncTask is deprecated but dependency-free and adequate for a
        // single short-lived fetch in a rarely-opened configuration screen
        // — not worth pulling in a coroutines/RxJava dependency for. If
        // this project already has kotlinx-coroutines wired in elsewhere
        // by the time this is integrated, swap this for a
        // lifecycleScope.launch instead; noted rather than silently
        // assumed either way.
        object : AsyncTask<Void, Void, List<CountdownApiClient.WidgetCountdown>>() {
            override fun doInBackground(vararg params: Void?): List<CountdownApiClient.WidgetCountdown> {
                return CountdownApiClient.fetchActiveCountdowns(applicationContext)
            }

            override fun onPostExecute(result: List<CountdownApiClient.WidgetCountdown>) {
                progressBar.visibility = android.view.View.GONE
                if (result.isEmpty()) {
                    emptyLabel.visibility = android.view.View.VISIBLE
                    return
                }
                val labels = result.map { "${it.title} (${it.priority})" }
                listView.adapter = ArrayAdapter(
                    this@CountdownWidgetConfigureActivity,
                    android.R.layout.simple_list_item_1,
                    labels,
                )
                listView.setOnItemClickListener { _, _, position, _ ->
                    saveAndFinish(countdownId = result[position].id)
                }
            }
        }.execute()
    }

    private fun saveAndFinish(countdownId: String?) {
        CountdownWidgetPrefs.saveSelection(applicationContext, appWidgetId, countdownId)

        // Paint real data immediately instead of leaving the freshly-placed
        // widget on its loading/empty state until the next periodic tick
        // (up to 30 minutes away).
        val request = OneTimeWorkRequestBuilder<CountdownWidgetUpdateWorker>()
            .setInputData(Data.Builder().putIntArray(CountdownWidgetUpdateWorker.KEY_WIDGET_IDS, intArrayOf(appWidgetId)).build())
            .build()
        WorkManager.getInstance(applicationContext).enqueue(request)

        val resultValue = android.content.Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
        setResult(Activity.RESULT_OK, resultValue)
        finish()
    }
}
