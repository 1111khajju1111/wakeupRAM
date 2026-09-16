/**
 * Bridges the backend's already-computed Notification rows (see
 * app/services/notification_service.py — scheduled/contextual/behavioral/
 * deadline/habit-intervention, deduped and rate-limited server-side) to a
 * real OS-level Android notification via @capacitor/local-notifications.
 *
 * Deliberately thin: all the actual "should this notification exist, and
 * is it worth showing" logic already lives server-side in
 * notification_service.py. This module's only job is presentation on the
 * device — never duplicate the eligibility/dedup/quiet-hours logic here.
 *
 * On web (Capacitor.isNativePlatform() === false), every function is a
 * documented no-op rather than silently failing or throwing — the app must
 * keep working in a browser during development without a notification
 * permission prompt appearing where there's no OS notification tray to use
 * it for.
 */
import { Capacitor } from "@capacitor/core";
import { LocalNotifications } from "@capacitor/local-notifications";
import type { NotificationItem } from "../types/domain";

export type PermissionState = "granted" | "denied" | "prompt" | "unsupported";

export async function ensureNotificationPermission(): Promise<PermissionState> {
  if (!Capacitor.isNativePlatform()) return "unsupported";

  const current = await LocalNotifications.checkPermissions();
  if (current.display === "granted") return "granted";
  if (current.display === "denied") return "denied";

  const requested = await LocalNotifications.requestPermissions();
  return requested.display === "granted" ? "granted" : "denied";
}

/**
 * A stable positive 32-bit int ID, required by the local-notifications
 * plugin, derived deterministically from the backend's UUID string —
 * scheduling the same backend Notification twice (e.g. after a refetch)
 * lands on the same native notification ID and simply replaces it rather
 * than duplicating it in the tray.
 */
function stableNotificationId(backendId: string): number {
  let hash = 0;
  for (let i = 0; i < backendId.length; i += 1) {
    hash = (hash * 31 + backendId.charCodeAt(i)) | 0;
  }
  // `| 0` above coerces hash into the full 32-bit signed range, which
  // includes -2147483648 (Int32.MIN) — and Math.abs(-2147483648) is
  // 2147483648, one past Int32.MAX, the actual valid range for a native
  // Android notification ID. Bitwise-AND with the max value instead of a
  // plain Math.abs keeps the result inside range for every possible hash,
  // including that one edge case.
  return (Math.abs(hash) & 0x7fffffff) || 1;
}

export async function scheduleNativeNotification(record: NotificationItem): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;

  const permission = await ensureNotificationPermission();
  if (permission !== "granted") return;

  await LocalNotifications.schedule({
    notifications: [
      {
        id: stableNotificationId(record.id),
        title: record.title,
        body: record.body,
        schedule: { at: new Date(record.trigger_at) },
        channelId: "default",
      },
    ],
  });
}

export async function cancelNativeNotification(backendId: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await LocalNotifications.cancel({ notifications: [{ id: stableNotificationId(backendId) }] });
}
