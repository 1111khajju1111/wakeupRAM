import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AuthProvider, useAuth } from "./store/AuthContext";
import { ThemeProvider } from "./theme/ThemeProvider";
import { RequireAuth } from "./app/RequireAuth";
import { LoginScreen } from "./features/auth/LoginScreen";
import { RegisterScreen } from "./features/auth/RegisterScreen";
import { HomeScreen } from "./features/dashboard/HomeScreen";
import { TodayScreen } from "./features/today/TodayScreen";
import { GoalsScreen } from "./features/goals/GoalsScreen";
import { HabitsScreen } from "./features/habits/HabitsScreen";
import { HealthScreen } from "./features/health/HealthScreen";
import { SmokingScreen } from "./features/smoking/SmokingScreen";
import { FinanceScreen } from "./features/finance/FinanceScreen";
import { CountdownsScreen } from "./features/countdowns/CountdownsScreen";
import { NotificationsScreen } from "./features/notifications/NotificationsScreen";
import { InsightsScreen } from "./features/insights/InsightsScreen";
import { TalkScreen } from "./features/talk/TalkScreen";
import { CallScreen } from "./features/talk/CallScreen";
import { AndroidBackButton } from "./app/AndroidBackButton";
import { AppShell } from "./app/AppShell";
import "./i18n";
import "./app/global.css";

function ProfileSyncedProviders({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const { i18n } = useTranslation();

  useEffect(() => {
    if (user?.profile?.preferred_language) {
      void i18n.changeLanguage(user.profile.preferred_language);
    }
  }, [user?.profile?.preferred_language, i18n]);

  return (
    <ThemeProvider initialMode={user?.profile?.theme_preference ?? "system"}>{children}</ThemeProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ProfileSyncedProviders>
        <BrowserRouter>
          <AndroidBackButton />
          <Routes>
            <Route path="/login" element={<LoginScreen />} />
            <Route path="/register" element={<RegisterScreen />} />
            <Route
              path="/"
              element={
                <RequireAuth><AppShell><HomeScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/today"
              element={
                <RequireAuth><AppShell><TodayScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/goals"
              element={
                <RequireAuth><AppShell><GoalsScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/habits"
              element={
                <RequireAuth><AppShell><HabitsScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/talk"
              element={
                <RequireAuth><AppShell><TalkScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/call"
              element={
                <RequireAuth><AppShell><CallScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/health"
              element={
                <RequireAuth><AppShell><HealthScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/smoking"
              element={
                <RequireAuth><AppShell><SmokingScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/money"
              element={
                <RequireAuth><AppShell><FinanceScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/countdowns"
              element={
                <RequireAuth><AppShell><CountdownsScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/notifications"
              element={
                <RequireAuth><AppShell><NotificationsScreen /></AppShell></RequireAuth>
              }
            />
            <Route
              path="/insights"
              element={
                <RequireAuth><AppShell><InsightsScreen /></AppShell></RequireAuth>
              }
            />
          </Routes>
        </BrowserRouter>
      </ProfileSyncedProviders>
    </AuthProvider>
  );
}
