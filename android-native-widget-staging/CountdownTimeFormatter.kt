package com.wakeupram.app.widget

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Deliberately mirrors frontend/src/features/countdowns/CountdownsScreen.tsx's
 * formatTimeRemaining() — same day/hour/minute breakpoints, same "Overdue"
 * behavior — so a countdown reads identically whether the user is looking
 * at the app or the home-screen widget. Verified against that file's actual
 * logic, not written independently and hoped to match.
 */
object CountdownTimeFormatter {

    // Backend sends target_datetime as ISO 8601 with an explicit UTC
    // offset (Pydantic's default datetime serialization) — parse defensively
    // for both "+00:00" and "Z" suffixes since which one shows up can
    // depend on the exact Python/Pydantic version in play.
    private fun parseIso(iso: String): Date? {
        val normalized = if (iso.endsWith("Z")) iso else iso
        val formats = listOf(
            "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
            "yyyy-MM-dd'T'HH:mm:ssXXX",
            "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
            "yyyy-MM-dd'T'HH:mm:ss'Z'",
        )
        for (pattern in formats) {
            try {
                val sdf = SimpleDateFormat(pattern, Locale.US)
                sdf.timeZone = TimeZone.getTimeZone("UTC")
                return sdf.parse(normalized)
            } catch (e: Exception) {
                // try the next pattern
            }
        }
        return null
    }

    /** Returns null if targetIso couldn't be parsed — caller should show a
     * "couldn't load" state, never a silently wrong duration. */
    fun formatRemaining(targetIso: String, overdueLabel: String, daysHoursFmt: String, hoursMinutesFmt: String, minutesFmt: String): String? {
        val target = parseIso(targetIso) ?: return null
        val diffMs = target.time - System.currentTimeMillis()
        if (diffMs <= 0) return overdueLabel

        val totalMinutes = diffMs / 60_000
        val days = totalMinutes / 1440
        val hours = (totalMinutes % 1440) / 60
        val minutes = totalMinutes % 60

        return when {
            days > 0 -> daysHoursFmt.format(days, hours)
            hours > 0 -> hoursMinutesFmt.format(hours, minutes)
            else -> minutesFmt.format(minutes)
        }
    }
}
