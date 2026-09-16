import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../store/AuthContext";
import { todayApi } from "../../services/domainApi";
import type { TodayView } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

export function HomeScreen() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [now, setNow] = useState(() => new Date());
  const [today, setToday] = useState<TodayView | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const loadToday = useCallback(async () => {
    setLoadState("loading");
    try { setToday(await todayApi.get()); setLoadState("loaded"); }
    catch { setLoadState("error"); }
  }, []);
  useEffect(() => {
    void loadToday();

    const handleRefresh = () => void loadToday();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") void loadToday();
    };

    window.addEventListener("focus", handleRefresh);
    window.addEventListener("wakeupram:today-changed", handleRefresh);
    window.addEventListener("wakeupram:goals-changed", handleRefresh);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.removeEventListener("focus", handleRefresh);
      window.removeEventListener("wakeupram:today-changed", handleRefresh);
      window.removeEventListener("wakeupram:goals-changed", handleRefresh);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [loadToday]);

  const displayName = user?.profile?.display_name || "Ram";
  const hour = now.getHours();
  const greeting = hour < 12 ? t("home.goodMorning") : hour < 18 ? t("home.goodAfternoon") : t("home.goodEvening");
  const completion = useMemo(() => {
    if (!today) return 0;
    const total = today.habits_due_today.length;
    return total ? Math.round((today.habits_due_today.filter(h => h.completed_today).length / total) * 100) : 0;
  }, [today]);

  return (
    <main className="home-screen">
      <section className="hero-panel">
        <div className="hero-panel__top"><span>{greeting}</span><span className="mono">{now.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short" }).toUpperCase()}</span></div>
        <h1>{displayName}<span>.</span></h1>
        <div className="hero-panel__clock">{now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</div>
        <p>Build the man. <strong>One day at a time.</strong></p>
      </section>

      <section className="mission-command" aria-label={t("home.todaysMission")}>
        <div className="section-label"><span>01 / TODAY</span><span className="status-dot">LIVE</span></div>
        {loadState === "loading" && <div className="skeleton-line" />}
        {loadState === "error" && <div className="state-row">{t("common.somethingWentWrong")} <button type="button" onClick={() => void loadToday()}>{t("common.retry")}</button></div>}
        {loadState === "loaded" && today?.mission ? (
          <button className="mission-command__body" type="button" onClick={() => navigate("/today")}>
            <span className="mission-command__index">MISSION</span>
            <strong>{today.mission.title}</strong>
            {today.mission.description && <span>{today.mission.description}</span>}
            <i>→</i>
          </button>
        ) : loadState === "loaded" ? (
          <div className="state-row state-row--action">
            <span>{t("home.noMissionYet")}</span>
            <button type="button" onClick={() => navigate("/today")}>
              {t("today.setMission")} →
            </button>
          </div>
        ) : null}
      </section>

      <section className="dashboard-grid">
        <Link className="data-card data-card--large" to="/habits">
          <div className="section-label"><span>02 / HABITS</span><span>{completion}%</span></div>
          <div className="metric">{today?.habits_due_today.length ?? 0}</div>
          <p>{t("home.habitsToday")}</p>
          <div className="progress-track"><span style={{ width: `${completion}%` }} /></div>
        </Link>
        <Link className="data-card" to="/goals">
          <span className="card-index">03</span><strong>{today?.active_goals_count ?? 0}</strong><p>{t("home.activeGoals")}</p>
        </Link>
        <Link className="data-card" to="/countdowns">
          <span className="card-index">04</span><strong>{today?.active_countdown ? "01" : "00"}</strong><p>{t("home.countdown")}</p>
        </Link>
      </section>

      <section className="talk-panel">
        <div><span className="section-label">RAM CORE / READY</span><h2>{t("home.talkToRam")}</h2><p>{t("home.talkDescription")}</p></div>
        <button type="button" onClick={() => navigate("/call")} aria-label={t("home.talkToRam")}><span>→</span></button>
      </section>

      <section className="module-index">
        <div className="section-label"><span>05 / CONTROL ROOM</span><span>OPEN</span></div>
        <div className="module-links">
          <Link to="/health"><span>H</span>Health</Link><Link to="/money"><span>M</span>Money</Link><Link to="/smoking"><span>S</span>Triggers</Link><Link to="/notifications"><span>N</span>Signals</Link><Link to="/insights"><span>I</span>Insights</Link><Link to="/talk"><span>T</span>Chat</Link>
        </div>
      </section>
    </main>
  );
}
