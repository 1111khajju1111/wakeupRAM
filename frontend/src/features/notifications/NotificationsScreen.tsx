import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { notificationsApi } from "../../services/domainApi";
import { cancelNativeNotification, scheduleNativeNotification } from "../../services/nativeNotifications";
import type { NotificationItem, NotificationPreferences, NotificationType } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

const NOTIFICATION_TYPES: NotificationType[] = [
  "scheduled",
  "contextual",
  "behavioral",
  "deadline",
  "habit_intervention",
];

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => hour);

/**
 * Phase 8 scope: this screen triggers the same on-demand notification
 * engine the backend documents (notification_service.generate_for_user) —
 * there's no background scheduler yet (that's Phase 13 infra), so
 * "Refresh" is the honest, visible stand-in for what a cron job will later
 * do silently. Preferences (quiet hours, daily cap, per-type opt-out) are
 * real and persisted, not decorative.
 *
 * Phase 11 addition: every load also mirrors the fetched notifications into
 * real OS-level Android notifications via
 * services/nativeNotifications.ts — scheduling anything still `pending`
 * and cancelling anything that's moved to `dismissed`/`actioned` (e.g. from
 * another device, or from a previous session's native tray entry that's
 * now stale). That bridge is a documented no-op on web, so this runs
 * unconditionally rather than needing a platform check here. All the
 * eligibility/dedup/quiet-hours logic stays server-side — this only keeps
 * the device's notification tray in sync with what the backend already
 * decided.
 */
export function NotificationsScreen() {
  const { t } = useTranslation();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const syncNativeNotifications = useCallback(async (items: NotificationItem[]) => {
    // Best-effort presentation sync — the in-app list above is already the
    // source of truth and renders regardless, so a native-bridge failure
    // (e.g. permission not yet granted) is swallowed here rather than
    // surfaced as a screen-level error.
    await Promise.all(
      items.map((item) =>
        (item.status === "dismissed" || item.status === "actioned"
          ? cancelNativeNotification(item.id)
          : scheduleNativeNotification(item)
        ).catch(() => undefined),
      ),
    );
  }, []);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const [notificationsData, preferencesData] = await Promise.all([
        notificationsApi.list(),
        notificationsApi.getPreferences(),
      ]);
      setNotifications(notificationsData);
      setPreferences(preferencesData);
      setLoadState("loaded");
      void syncNativeNotifications(notificationsData);
    } catch {
      setLoadState("error");
    }
  }, [syncNativeNotifications]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRefresh() {
    setIsRefreshing(true);
    try {
      await notificationsApi.refresh();
      await load();
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleStatusChange(id: string, status: "dismissed" | "actioned") {
    await notificationsApi.updateStatus(id, status);
    await load();
  }

  async function handlePreferenceChange(patch: Partial<NotificationPreferences>) {
    const updated = await notificationsApi.updatePreferences(patch);
    setPreferences(updated);
  }

  async function handleToggleType(type: NotificationType, enabled: boolean) {
    if (!preferences) return;
    await handlePreferenceChange({ enabled_types: { ...preferences.enabled_types, [type]: enabled } });
  }

  return (
    <main className="notifications-screen">
      <h1>{t("nav.notifications")}</h1>

      {loadState === "loading" && <p className="empty-state">{t("common.loading")}</p>}

      {loadState === "error" && (
        <div className="empty-state empty-state--error">
          <p>{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void load()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {loadState === "loaded" && preferences && (
        <>
          <button className="notifications-screen__refresh" type="button" disabled={isRefreshing} onClick={() => void handleRefresh()}>
            {isRefreshing ? t("common.loading") : t("notifications.refresh")}
          </button>

          <section className="notifications-screen__section" aria-label={t("notifications.feedTitle")}>
            <h2>{t("notifications.feedTitle")}</h2>
            {notifications.length === 0 ? (
              <p className="empty-state">{t("notifications.noNotificationsYet")}</p>
            ) : (
              <ul className="notifications-screen__list">
                {notifications.map((notification) => (
                  <li
                    key={notification.id}
                    className={`notifications-screen__item notifications-screen__item--${notification.status}`}
                  >
                    <div className="notifications-screen__item-header">
                      <span className="notifications-screen__type">{t(`notifications.type.${notification.type}`)}</span>
                      <strong>{notification.title}</strong>
                    </div>
                    <p>{notification.body}</p>
                    {notification.status !== "dismissed" && (
                      <div className="notifications-screen__item-actions">
                        {notification.status !== "actioned" && (
                          <button type="button" onClick={() => void handleStatusChange(notification.id, "actioned")}>
                            {t("notifications.markActioned")}
                          </button>
                        )}
                        <button type="button" onClick={() => void handleStatusChange(notification.id, "dismissed")}>
                          {t("notifications.dismiss")}
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="notifications-screen__section" aria-label={t("notifications.preferencesTitle")}>
            <h2>{t("notifications.preferencesTitle")}</h2>
            <div className="notifications-screen__preferences">
              <label>
                {t("notifications.maxPerDayLabel")}
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={preferences.max_per_day}
                  onChange={(event) => void handlePreferenceChange({ max_per_day: Number(event.target.value) })}
                />
              </label>

              <label>
                {t("notifications.quietHoursStartLabel")}
                <select
                  value={preferences.quiet_hours_start_hour ?? ""}
                  onChange={(event) =>
                    void handlePreferenceChange({
                      quiet_hours_start_hour: event.target.value === "" ? null : Number(event.target.value),
                    })
                  }
                >
                  <option value="">{t("notifications.quietHoursOff")}</option>
                  {HOUR_OPTIONS.map((hour) => (
                    <option key={hour} value={hour}>
                      {hour}:00
                    </option>
                  ))}
                </select>
              </label>

              <label>
                {t("notifications.quietHoursEndLabel")}
                <select
                  value={preferences.quiet_hours_end_hour ?? ""}
                  onChange={(event) =>
                    void handlePreferenceChange({
                      quiet_hours_end_hour: event.target.value === "" ? null : Number(event.target.value),
                    })
                  }
                >
                  <option value="">{t("notifications.quietHoursOff")}</option>
                  {HOUR_OPTIONS.map((hour) => (
                    <option key={hour} value={hour}>
                      {hour}:00
                    </option>
                  ))}
                </select>
              </label>

              <fieldset>
                <legend>{t("notifications.typesLabel")}</legend>
                {NOTIFICATION_TYPES.map((type) => (
                  <label key={type}>
                    <input
                      type="checkbox"
                      checked={preferences.enabled_types[type] ?? true}
                      onChange={(event) => void handleToggleType(type, event.target.checked)}
                    />
                    {t(`notifications.type.${type}`)}
                  </label>
                ))}
              </fieldset>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
