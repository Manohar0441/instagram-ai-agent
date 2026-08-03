import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { LoadingPage } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import {
  RedirectIfAuthenticated,
  RedirectIfOnboarded,
  RequireAuth,
  RequireOnboarding,
} from "./routes/guards";

/**
 * Retries a failed dynamic import once via a full reload.
 *
 * The most common cause of a lazy route failing to load is a stale chunk
 * hash left over from before a redeploy - the page's already-loaded HTML
 * still points at a JS file the server no longer serves, which otherwise
 * shows up to the user as "this bit of the app is just broken" until they
 * think to reload manually. A hard reload fetches the current asset
 * manifest and silently fixes it; a second failure for the same chunk
 * (already retried this session) is a real error and is left to propagate
 * to the ErrorBoundary instead of reload-looping forever.
 */
function retryImport<T>(load: () => Promise<T>, key: string): Promise<T> {
  return load().catch((error: unknown) => {
    const flagKey = `instalysis.chunk-retry.${key}`;
    if (!window.sessionStorage.getItem(flagKey)) {
      window.sessionStorage.setItem(flagKey, "1");
      window.location.reload();
      // The reload navigates away before a real value would ever be
      // needed - this just keeps the promise pending in the meantime.
      return new Promise<T>(() => {});
    }
    throw error;
  });
}

/* Auth and onboarding load eagerly - they are the first thing a signed-out
 * visitor sees, and splitting them would add a spinner to the critical path.
 *
 * Everything behind the app shell is lazy. The charting library alone is
 * most of the bundle, and a user reading the chat never needs it. */
const OverviewPage = lazy(() =>
  retryImport(
    () => import("./pages/dashboard/OverviewPage").then((m) => ({ default: m.OverviewPage })),
    "OverviewPage",
  ),
);
const TrendsPage = lazy(() =>
  retryImport(
    () => import("./pages/dashboard/TrendsPage").then((m) => ({ default: m.TrendsPage })),
    "TrendsPage",
  ),
);
const MediaPage = lazy(() =>
  retryImport(
    () => import("./pages/dashboard/MediaPage").then((m) => ({ default: m.MediaPage })),
    "MediaPage",
  ),
);
const TopContentPage = lazy(() =>
  retryImport(
    () =>
      import("./pages/dashboard/TopContentPage").then((m) => ({ default: m.TopContentPage })),
    "TopContentPage",
  ),
);
const ChatPage = lazy(() =>
  retryImport(
    () => import("./pages/ai/ChatPage").then((m) => ({ default: m.ChatPage })),
    "ChatPage",
  ),
);
const InsightsPage = lazy(() =>
  retryImport(
    () => import("./pages/ai/InsightsPage").then((m) => ({ default: m.InsightsPage })),
    "InsightsPage",
  ),
);
const RecommendationsPage = lazy(() =>
  retryImport(
    () =>
      import("./pages/ai/RecommendationsPage").then((m) => ({
        default: m.RecommendationsPage,
      })),
    "RecommendationsPage",
  ),
);
const ReportsPage = lazy(() =>
  retryImport(
    () => import("./pages/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })),
    "ReportsPage",
  ),
);
const FullReportPage = lazy(() =>
  retryImport(
    () =>
      import("./pages/reports/FullReportPage").then((m) => ({ default: m.FullReportPage })),
    "FullReportPage",
  ),
);
const SettingsPage = lazy(() =>
  retryImport(
    () => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
    "SettingsPage",
  ),
);
const DealsPage = lazy(() =>
  retryImport(
    () => import("./pages/deals/DealsPage").then((m) => ({ default: m.DealsPage })),
    "DealsPage",
  ),
);
const DealFormPage = lazy(() =>
  retryImport(
    () => import("./pages/deals/DealFormPage").then((m) => ({ default: m.DealFormPage })),
    "DealFormPage",
  ),
);
const GeminiKeyPage = lazy(() =>
  retryImport(
    () =>
      import("./pages/onboarding/GeminiKeyPage").then((m) => ({ default: m.GeminiKeyPage })),
    "GeminiKeyPage",
  ),
);
const ConnectInstagramPage = lazy(() =>
  retryImport(
    () =>
      import("./pages/onboarding/ConnectInstagramPage").then((m) => ({
        default: m.ConnectInstagramPage,
      })),
    "ConnectInstagramPage",
  ),
);

function lazyRoute(element: ReactNode) {
  return <Suspense fallback={<LoadingPage />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    element: <RedirectIfAuthenticated />,
    children: [{ path: "/login", element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <RedirectIfOnboarded />,
        children: [
          { path: "/onboarding/gemini", element: lazyRoute(<GeminiKeyPage />) },
          { path: "/onboarding/instagram", element: lazyRoute(<ConnectInstagramPage />) },
        ],
      },
      {
        // Settings sits outside RequireOnboarding on purpose: it is how a
        // user fixes a rejected key or a broken Instagram connection, and
        // gating it would trap them in a redirect loop.
        element: <AppShell />,
        children: [{ path: "/settings", element: lazyRoute(<SettingsPage />) }],
      },
      {
        element: <RequireOnboarding />,
        children: [
          {
            element: <AppShell />,
            children: [
              { path: "/dashboard", element: lazyRoute(<OverviewPage />) },
              { path: "/trends", element: lazyRoute(<TrendsPage />) },
              { path: "/media", element: lazyRoute(<MediaPage />) },
              { path: "/top-content", element: lazyRoute(<TopContentPage />) },
              { path: "/chat", element: lazyRoute(<ChatPage />) },
              { path: "/insights", element: lazyRoute(<InsightsPage />) },
              { path: "/recommendations", element: lazyRoute(<RecommendationsPage />) },
              { path: "/reports", element: lazyRoute(<ReportsPage />) },
              { path: "/reports/full", element: lazyRoute(<FullReportPage />) },
              { path: "/deals", element: lazyRoute(<DealsPage />) },
              { path: "/deals/new", element: lazyRoute(<DealFormPage />) },
              { path: "/deals/:id/edit", element: lazyRoute(<DealFormPage />) },
            ],
          },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "*", element: <NotFoundPage /> },
]);
