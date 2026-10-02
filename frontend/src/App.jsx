import { useEffect, useState } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client.js";
import AiPage from "./pages/admin/AiPage.jsx";
import ContentPage from "./pages/admin/ContentPage.jsx";
import LeaderboardPage from "./pages/admin/LeaderboardPage.jsx";
import LessonPreview from "./pages/admin/LessonPreview.jsx";
import SettingsPage from "./pages/admin/SettingsPage.jsx";
import CertificateSettingsPage from "./pages/admin/CertificateSettingsPage.jsx";
import UsersPage from "./pages/admin/UsersPage.jsx";
import GamesPage from "./pages/games/GamesPage.jsx";
import PlayPage from "./pages/games/PlayPage.jsx";
import CertificatesPage, {
  CertificateDetailPage,
} from "./pages/learn/CertificatesPage.jsx";
import LessonPage from "./pages/learn/LessonPage.jsx";
import ProjectsPage from "./pages/learn/ProjectsPage.jsx";
import TrackPage from "./pages/learn/TrackPage.jsx";
import PlaygroundPage from "./pages/playground/PlaygroundPage.jsx";
import LoginPage from "./pages/auth/LoginPage.jsx";
import SignupPage from "./pages/auth/SignupPage.jsx";
import DemoLessonPage from "./pages/demo/DemoLessonPage.jsx";
import DemoPage from "./pages/demo/DemoPage.jsx";
import HomePage from "./pages/Home.jsx";
import NotificationsPage from "./pages/settings/NotificationsPage.jsx";
import PreferencesPage from "./pages/settings/PreferencesPage.jsx";
import ProfilePage from "./pages/settings/ProfilePage.jsx";
import ProgressPage from "./pages/settings/ProgressPage.jsx";
import SetupPage from "./pages/setup/SetupPage.jsx";
import AppNav from "./components/layout/AppNav.jsx";
import SettingsLayout from "./components/layout/SettingsLayout.jsx";
import InstallPrompt from "./components/pwa/InstallPrompt.jsx";
import OfflineNotice from "./components/pwa/OfflineNotice.jsx";
import { clearPracticeSession } from "./practiceSession.js";
import { applyStoredPrefs } from "./prefs.js";
import { isStaff, isSuperAdmin } from "./roles.js";
import { applyTheme, readTheme } from "./theme/theme.js";

const GUEST_ONLY = new Set(["/login", "/signup"]);

function isOpenPath(pathname) {
  return (
    pathname === "/" ||
    GUEST_ONLY.has(pathname) ||
    pathname === "/demo" ||
    pathname.startsWith("/demo/")
  );
}

function Shell() {
  const [theme, setTheme] = useState(readTheme);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [setupRequired, setSetupRequired] = useState(false);
  const [user, setUser] = useState(null);
  const [signingOut, setSigningOut] = useState(false);
  const location = useLocation();

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    applyStoredPrefs();
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const status = await api("/api/setup/status");
        let current = null;
        try {
          current = await api("/api/me");
        } catch (err) {
          if (err.status !== 401) {
            throw err;
          }
        }
        if (!cancelled) {
          setSetupRequired(status.setup_required);
          setUser(current);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "The API is unreachable");
        }
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function logout() {
    setSigningOut(true);
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      clearPracticeSession();
      setUser(null);
      setSigningOut(false);
    }
  }

  const nextTheme = theme === "dark" ? "light" : "dark";
  let destination = null;
  if (ready && !error) {
    if (setupRequired && location.pathname !== "/setup") {
      destination = "/setup";
    } else if (!setupRequired && location.pathname === "/setup") {
      destination = user ? "/" : "/login";
    } else if (!setupRequired && !user && !isOpenPath(location.pathname)) {
      destination = "/login";
    } else if (user && GUEST_ONLY.has(location.pathname)) {
      destination = "/";
    } else if (
      user &&
      !isStaff(user.role) &&
      (location.pathname.startsWith("/admin") ||
        location.pathname.startsWith("/settings/notifications"))
    ) {
      destination = "/";
    } else if (
      user &&
      !isSuperAdmin(user.role) &&
      (location.pathname.startsWith("/admin/users") ||
        location.pathname.startsWith("/admin/content") ||
        location.pathname.startsWith("/admin/preview") ||
        location.pathname.startsWith("/admin/certificates"))
    ) {
      destination = "/";
    }
  }

  return (
    <main className="min-h-screen overflow-x-clip bg-bg px-4 py-8 text-text sm:px-6 sm:py-16">
      <div className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-6 sm:gap-8">
        <header className="practice-rise flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-2xl font-medium tracking-tight text-accent sm:text-3xl">
              Ghostline
            </p>
            <p className="mt-2 max-w-xl text-muted">
              Learn coding by typing. Keep the muscle memory.
            </p>
          </div>
          <button
            type="button"
            className="theme-pin inline-flex shrink-0 items-center rounded-full border border-muted/25 bg-surface px-3.5 py-2 font-mono text-xs uppercase tracking-[0.16em] text-muted shadow-[var(--shadow)] hover:border-accent/35 hover:text-text"
            onClick={() => setTheme(nextTheme)}
            aria-label={`Switch to ${nextTheme} theme`}
            title={`Switch to ${nextTheme} theme`}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </header>
        {ready && !setupRequired ? (
          <AppNav user={user} onSignOut={logout} signingOut={signingOut} />
        ) : null}
        <InstallPrompt />
        <OfflineNotice />
        {error ? <p className="text-sm text-error">{error}</p> : null}
        {!ready && !error ? <p className="text-sm text-muted">Loading…</p> : null}
        {destination ? <Navigate to={destination} replace /> : null}
        {ready && !error && !destination ? (
          <Outlet context={{ user, setUser, setSetupRequired, theme, setTheme }} />
        ) : null}
      </div>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/demo/lessons/:lessonId" element={<DemoLessonPage />} />
        <Route element={<SettingsLayout />}>
          <Route path="/settings" element={<Navigate to="/settings/profile" replace />} />
          <Route path="/settings/profile" element={<ProfilePage />} />
          <Route path="/settings/preferences" element={<PreferencesPage />} />
          <Route path="/settings/progress" element={<ProgressPage />} />
          <Route path="/settings/notifications" element={<NotificationsPage />} />
          <Route path="/admin/settings" element={<SettingsPage />} />
          <Route path="/admin/certificates" element={<CertificateSettingsPage />} />
          <Route path="/admin/ai" element={<AiPage />} />
        </Route>
        <Route path="/admin/content" element={<ContentPage />} />
        <Route path="/admin/preview/lessons/:lessonId" element={<LessonPreview />} />
        <Route path="/admin/leaderboard" element={<LeaderboardPage />} />
        <Route path="/admin/leadboard" element={<Navigate to="/admin/leaderboard" replace />} />
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/games" element={<GamesPage />} />
        <Route path="/games/:game" element={<PlayPage />} />
        <Route path="/stats" element={<Navigate to="/" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/certificates" element={<CertificatesPage />} />
        <Route path="/certificates/:slug" element={<CertificateDetailPage />} />
        <Route path="/playground" element={<PlaygroundPage />} />
        <Route path="/learn/tracks/:slug" element={<TrackPage />} />
        <Route path="/learn/lessons/:lessonId" element={<LessonPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
