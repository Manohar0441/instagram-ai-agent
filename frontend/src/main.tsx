import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { ApiError } from "./api/client";
import { AuthProvider } from "./auth/AuthContext";
import { router } from "./router";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/grid.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // A 4xx is the server's considered answer, not a blip. Retrying a
        // 401 is especially pointless — there is no refresh token, so the
        // second attempt fails exactly like the first.
        if (error instanceof ApiError && error.status < 500) return false;
        return failureCount < 2;
      },
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
