import type { CapacitorConfig } from "@capacitor/cli";

// appId/appName are the two values Capacitor bakes into the generated
// native project at `npx cap add android` time — change them here BEFORE
// running that command for the first time; changing them after requires
// regenerating the native project, not just editing this file.
const config: CapacitorConfig = {
  appId: "com.wakeupram.app",
  appName: "Wake Up Ram",
  webDir: "dist",
  // Points the native shell at a locally-built web bundle (`npm run build`
  // -> dist/) rather than a remote URL — the app works fully offline for
  // anything not requiring the backend API, consistent with section 14's
  // PWA/offline-friendly requirement. Switch to a `server.url` pointing at
  // a deployed frontend only if you specifically want the native shell to
  // load a remote bundle instead of the one built into the APK.
  android: {
    allowMixedContent: false,
  },
  plugins: {
    // Local notifications need an explicit channel on Android 8+; this one
    // is deliberately generic ("default") since Notification.notification_type
    // (deadline/habit_intervention/behavioral/etc., see backend
    // app/models/notification.py) already carries the finer distinction —
    // no need for a matching proliferation of Android channels.
    LocalNotifications: {
      smallIcon: "ic_stat_wake_up_ram",
      iconColor: "#0A0A0A",
    },
  },
};

export default config;
