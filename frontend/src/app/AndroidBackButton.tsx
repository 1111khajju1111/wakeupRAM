import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { App as CapacitorApp } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

/**
 * Capacitor Android's default behavior for the hardware/gesture back
 * button is to close the app outright — there's no built-in bridge to the
 * SPA's own router history. Without this, a back press from any screen
 * other than the root would exit Wake Up Ram entirely instead of
 * navigating back within it, which isn't how any other Android app
 * behaves. No-ops on web (Capacitor.isNativePlatform() === false), same
 * pattern as services/nativeNotifications.ts, so this is safe to mount
 * unconditionally in App.tsx.
 *
 * At the router root ("/"), back exits the app instead of calling
 * navigate(-1): there's nowhere further back to go within the SPA, and a
 * Capacitor WebView has no browser history before the app's own root, so
 * falling through to router history there would leave the WebView on a
 * blank page rather than actually closing — the behavior Android users
 * expect from a back press at an app's home screen.
 */
export function AndroidBackButton() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    const listenerHandle = CapacitorApp.addListener("backButton", () => {
      if (location.pathname === "/") {
        void CapacitorApp.exitApp();
      } else {
        navigate(-1);
      }
    });

    return () => {
      void listenerHandle.then((listener) => listener.remove());
    };
  }, [navigate, location.pathname]);

  return null;
}
