import {
  Bell,
  Building2,
  ChevronDown,
  CircleGauge,
  CreditCard,
  FileKey2,
  History,
  Menu,
  RadioTower,
  ScrollText,
  Settings,
  Users,
  WalletCards,
  Webhook,
  WifiOff,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { IconButton } from "./ui";

const navigation = [
  { to: "/", label: "Overview", icon: CircleGauge },
  {
    to: "/customers",
    label: "Customers",
    icon: Users,
    permission: "customers:read",
  },
  { to: "/cards", label: "Cards", icon: CreditCard, permission: "cards:read" },
  {
    to: "/wallets",
    label: "Wallets",
    icon: WalletCards,
    permission: "wallets:read",
  },
  {
    to: "/transactions",
    label: "Transactions",
    icon: History,
    permission: "transactions:read",
  },
  {
    to: "/devices",
    label: "Devices",
    icon: RadioTower,
    permission: "devices:read",
  },
  {
    to: "/offline",
    label: "Offline review",
    icon: WifiOff,
    permission: "transactions:read",
  },
  {
    to: "/webhooks",
    label: "Webhooks",
    icon: Webhook,
    permission: "integrations:manage",
  },
  {
    to: "/api-keys",
    label: "API keys",
    icon: FileKey2,
    permission: "integrations:manage",
  },
  {
    to: "/audit",
    label: "Audit log",
    icon: ScrollText,
    permission: "audit:read",
  },
  {
    to: "/settings",
    label: "Settings",
    icon: Settings,
    permission: "settings:manage",
  },
];

export function AppShell() {
  const { user, permissions, logout } = useAuth();
  const [mobileNav, setMobileNav] = useState(false);
  const location = useLocation();
  const current =
    navigation.find((item) =>
      item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to),
    ) ?? navigation[0];
  const visibleNavigation = navigation.filter(
    (item) => !item.permission || permissions.has(item.permission),
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <span className="brand-mark" aria-hidden="true">
            C
          </span>
          <span>CASPRA</span>
          <IconButton
            label="Close navigation"
            icon={X}
            className="mobile-close"
            onClick={() => setMobileNav(false)}
          />
        </div>
        <nav aria-label="Primary navigation">
          {visibleNavigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={() => setMobileNav(false)}
            >
              <Icon aria-hidden="true" size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="system-status">
          <span aria-hidden="true" />
          All systems operational
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <IconButton
              label="Open navigation"
              icon={Menu}
              className="mobile-menu"
              onClick={() => setMobileNav(true)}
            />
            <h2>{current.label}</h2>
          </div>
          <div className="topbar-actions">
            <button className="venue-selector" title="Current organization">
              <Building2 aria-hidden="true" size={16} />
              <span>Primary venue</span>
              <ChevronDown aria-hidden="true" size={15} />
            </button>
            <IconButton label="Notifications" icon={Bell} />
            <button className="operator-menu" onClick={logout}>
              <span className="operator-avatar">
                {user?.email.slice(0, 1).toUpperCase()}
              </span>
              <span>
                <strong>{user?.full_name || "Operator"}</strong>
                <small>{user?.email}</small>
              </span>
              <ChevronDown aria-hidden="true" size={15} />
            </button>
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
