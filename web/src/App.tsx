import { LoaderCircle } from "lucide-react";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthProvider";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";

const OverviewPage = lazy(() =>
  import("./pages/OverviewPage").then((module) => ({
    default: module.OverviewPage,
  })),
);
const TransactionsPage = lazy(() =>
  import("./pages/TransactionsPage").then((module) => ({
    default: module.TransactionsPage,
  })),
);
const OfflinePage = lazy(() =>
  import("./pages/OfflinePage").then((module) => ({
    default: module.OfflinePage,
  })),
);
const WebhooksPage = lazy(() =>
  import("./pages/WebhooksPage").then((module) => ({
    default: module.WebhooksPage,
  })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({
    default: module.SettingsPage,
  })),
);
const CustomersPage = lazy(() =>
  import("./pages/ResourcePages").then((module) => ({
    default: module.CustomersPage,
  })),
);
const CardsPage = lazy(() =>
  import("./pages/ResourcePages").then((module) => ({
    default: module.CardsPage,
  })),
);
const WalletsPage = lazy(() =>
  import("./pages/ResourcePages").then((module) => ({
    default: module.WalletsPage,
  })),
);
const DevicesPage = lazy(() =>
  import("./pages/ResourcePages").then((module) => ({
    default: module.DevicesPage,
  })),
);
const ApiKeysPage = lazy(() =>
  import("./pages/ResourcePages").then((module) => ({
    default: module.ApiKeysPage,
  })),
);
const AuditPage = lazy(() =>
  import("./pages/ResourcePages").then((module) => ({
    default: module.AuditPage,
  })),
);

export function App() {
  const { loading, user } = useAuth();
  if (loading) {
    return (
      <div className="app-loading" role="status">
        <LoaderCircle className="spin" aria-hidden="true" />
        <span>Opening Caspra</span>
      </div>
    );
  }
  if (!user) return <LoginPage />;

  return (
    <Suspense
      fallback={
        <div className="state-box">
          <LoaderCircle className="spin" aria-hidden="true" />
          <span>Loading workspace</span>
        </div>
      }
    >
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="cards" element={<CardsPage />} />
          <Route path="wallets" element={<WalletsPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="offline" element={<OfflinePage />} />
          <Route path="webhooks" element={<WebhooksPage />} />
          <Route path="api-keys" element={<ApiKeysPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
