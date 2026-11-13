import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { Skeleton } from "./components/ui";
import "./index.css";
import { ApiError } from "./lib/api";
import { Home } from "./pages/Home";

// The tool pages pull in MapLibre and Recharts; load them on demand so the
// landing page stays light.
const CityPage = lazy(() => import("./pages/CityPage"));
const EvPage = lazy(() => import("./pages/EvPage"));
const AreaPage = lazy(() => import("./pages/AreaPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A score for a given location doesn't change within a visit.
      staleTime: Infinity,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      // 4xx means "bad address" etc. — retrying won't help.
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 1,
    },
  },
});

function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-bold text-ink">Page not found</h1>
      <Link to="/" className="mt-3 inline-block font-medium text-accent">
        Back to all tools
      </Link>
    </div>
  );
}

const pageFallback = <Skeleton className="h-96" />;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="city" element={<Suspense fallback={pageFallback}><CityPage /></Suspense>} />
            <Route path="ev" element={<Suspense fallback={pageFallback}><EvPage /></Suspense>} />
            <Route path="area" element={<Suspense fallback={pageFallback}><AreaPage /></Suspense>} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
