import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { ChatPage } from "./pages/ai/ChatPage";
import { InsightsPage } from "./pages/ai/InsightsPage";
import { RecommendationsPage } from "./pages/ai/RecommendationsPage";
import { MediaPage } from "./pages/dashboard/MediaPage";
import { OverviewPage } from "./pages/dashboard/OverviewPage";
import { TopContentPage } from "./pages/dashboard/TopContentPage";
import { TrendsPage } from "./pages/dashboard/TrendsPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ConnectInstagramPage } from "./pages/onboarding/ConnectInstagramPage";
import { GeminiKeyPage } from "./pages/onboarding/GeminiKeyPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ReportsPage } from "./pages/reports/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import {
  RedirectIfAuthenticated,
  RedirectIfOnboarded,
  RequireAuth,
  RequireOnboarding,
} from "./routes/guards";

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
          { path: "/onboarding/gemini", element: <GeminiKeyPage /> },
          { path: "/onboarding/instagram", element: <ConnectInstagramPage /> },
        ],
      },
      {
        // Settings sits outside RequireOnboarding on purpose: it is how a
        // user fixes a rejected key or a broken Instagram connection, and
        // gating it would trap them in a redirect loop.
        element: <AppShell />,
        children: [{ path: "/settings", element: <SettingsPage /> }],
      },
      {
        element: <RequireOnboarding />,
        children: [
          {
            element: <AppShell />,
            children: [
              { path: "/dashboard", element: <OverviewPage /> },
              { path: "/trends", element: <TrendsPage /> },
              { path: "/media", element: <MediaPage /> },
              { path: "/top-content", element: <TopContentPage /> },
              { path: "/chat", element: <ChatPage /> },
              { path: "/insights", element: <InsightsPage /> },
              { path: "/recommendations", element: <RecommendationsPage /> },
              { path: "/reports", element: <ReportsPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "*", element: <NotFoundPage /> },
]);
