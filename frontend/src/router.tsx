import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { LoadingPage } from "./components/ui";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RegisterPage } from "./pages/RegisterPage";
import {
  RedirectIfAuthenticated,
  RedirectIfOnboarded,
  RequireAuth,
  RequireOnboarding,
} from "./routes/guards";

/* Auth and onboarding load eagerly - they are the first thing a signed-out
 * visitor sees, and splitting them would add a spinner to the critical path.
 *
 * Everything behind the app shell is lazy. The charting library alone is
 * most of the bundle, and a user reading the chat never needs it. */
const OverviewPage = lazy(() =>
  import("./pages/dashboard/OverviewPage").then((m) => ({ default: m.OverviewPage })),
);
const TrendsPage = lazy(() =>
  import("./pages/dashboard/TrendsPage").then((m) => ({ default: m.TrendsPage })),
);
const MediaPage = lazy(() =>
  import("./pages/dashboard/MediaPage").then((m) => ({ default: m.MediaPage })),
);
const TopContentPage = lazy(() =>
  import("./pages/dashboard/TopContentPage").then((m) => ({ default: m.TopContentPage })),
);
const ChatPage = lazy(() =>
  import("./pages/ai/ChatPage").then((m) => ({ default: m.ChatPage })),
);
const InsightsPage = lazy(() =>
  import("./pages/ai/InsightsPage").then((m) => ({ default: m.InsightsPage })),
);
const RecommendationsPage = lazy(() =>
  import("./pages/ai/RecommendationsPage").then((m) => ({
    default: m.RecommendationsPage,
  })),
);
const ReportsPage = lazy(() =>
  import("./pages/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
const GeminiKeyPage = lazy(() =>
  import("./pages/onboarding/GeminiKeyPage").then((m) => ({ default: m.GeminiKeyPage })),
);
const ConnectInstagramPage = lazy(() =>
  import("./pages/onboarding/ConnectInstagramPage").then((m) => ({
    default: m.ConnectInstagramPage,
  })),
);

function lazyRoute(element: ReactNode) {
  return <Suspense fallback={<LoadingPage />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    element: <RedirectIfAuthenticated />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
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
            ],
          },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "*", element: <NotFoundPage /> },
]);
