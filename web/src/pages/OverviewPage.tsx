import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUpFromLine,
  CheckCircle2,
  RefreshCw,
  WalletCards,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  apiRequest,
  type Schemas,
  type TransactionOut,
} from "../api/client";
import { RefundDrawer } from "../components/RefundDrawer";
import { TransactionTable } from "../components/TransactionTable";
import {
  ErrorState,
  IconButton,
  LoadingState,
  StatusMark,
  formatMoney,
  formatTime,
} from "../components/ui";

type OverviewData = {
  transactions: Schemas["PaginatedTransactionOut"];
  wallets: Schemas["PaginatedWalletOut"];
  devices: Schemas["PaginatedDeviceOut"];
  daily: Schemas["DailyReportOut"];
  reconciliation: Schemas["ReconciliationReportOut"];
  offline: Schemas["OfflineReviewItemOut"][];
  deliveries: Schemas["PaginatedWebhookDeliveryOut"];
};

async function loadOverview(): Promise<OverviewData> {
  const [
    transactions,
    wallets,
    devices,
    daily,
    reconciliation,
    offline,
    deliveries,
  ] = await Promise.all([
    apiRequest<Schemas["PaginatedTransactionOut"]>(
      "/admin/api/v1/transactions?page=1&limit=10",
    ),
    apiRequest<Schemas["PaginatedWalletOut"]>("/admin/api/v1/wallets?page=1&limit=100"),
    apiRequest<Schemas["PaginatedDeviceOut"]>("/admin/api/v1/devices?page=1&limit=8"),
    apiRequest<Schemas["DailyReportOut"]>("/admin/api/v1/reports/daily"),
    apiRequest<Schemas["ReconciliationReportOut"]>(
      "/admin/api/v1/ledger/reconciliation",
    ),
    apiRequest<Schemas["OfflineReviewItemOut"][]>("/admin/api/v1/offline/review"),
    apiRequest<Schemas["PaginatedWebhookDeliveryOut"]>(
      "/admin/api/v1/webhooks/deliveries?page=1&limit=5",
    ),
  ]);
  return {
    transactions,
    wallets,
    devices,
    daily,
    reconciliation,
    offline,
    deliveries,
  };
}

export function OverviewPage() {
  const overview = useQuery({ queryKey: ["overview"], queryFn: loadOverview });
  const [refundTransaction, setRefundTransaction] =
    useState<TransactionOut | null>(null);

  const derived = useMemo(() => {
    if (!overview.data) return null;
    const currency =
      overview.data.wallets.items[0]?.currency ??
      overview.data.daily.currency ??
      "USD";
    const liability = overview.data.wallets.items.reduce(
      (total, wallet) => total + wallet.balance_minor,
      0,
    );
    const latestDay = overview.data.daily.rows.at(-1);
    const chart = overview.data.daily.rows.slice(-14).map((row) => ({
      day: new Date(`${row.day}T00:00:00`).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      }),
      load: row.total_credit_minor / 100,
      spend: row.total_debit_minor / 100,
    }));
    const reconciliationCount = overview.data.reconciliation.issues.length;
    return { currency, liability, latestDay, chart, reconciliationCount };
  }, [overview.data]);

  if (overview.isLoading) return <LoadingState label="Loading operations overview" />;
  if (overview.error || !overview.data || !derived) {
    return (
      <ErrorState
        message={overview.error?.message ?? "Overview is unavailable"}
        retry={() => overview.refetch()}
      />
    );
  }

  const failedDeliveries = overview.data.deliveries.items.filter(
    (delivery) => !["success", "pending"].includes(delivery.status),
  );

  return (
    <div className="overview-page">
      <section className="metric-band" aria-label="Financial status">
        <Metric
          label="Wallet liability"
          value={formatMoney(derived.liability, derived.currency)}
          detail={`${overview.data.wallets.total} active wallet records`}
          icon={WalletCards}
          tone="neutral"
        />
        <Metric
          label="Today's load"
          value={formatMoney(
            derived.latestDay?.total_credit_minor ?? 0,
            derived.currency,
          )}
          detail={`${derived.latestDay?.transaction_count ?? 0} transactions`}
          icon={ArrowDownToLine}
          tone="positive"
        />
        <Metric
          label="Today's spend"
          value={formatMoney(
            derived.latestDay?.total_debit_minor ?? 0,
            derived.currency,
          )}
          detail="Posted debit volume"
          icon={ArrowUpFromLine}
          tone="positive"
        />
        <Metric
          label="Reconciliation"
          value={derived.reconciliationCount ? "Review required" : "Balanced"}
          detail={`${derived.reconciliationCount} differences`}
          icon={derived.reconciliationCount ? AlertCircle : CheckCircle2}
          tone={derived.reconciliationCount ? "warning" : "positive"}
        />
      </section>

      <div className="overview-grid">
        <section className="panel chart-panel">
          <header className="panel-header">
            <div>
              <h2>Transaction volume</h2>
              <p>Daily posted value</p>
            </div>
            <div className="chart-legend">
              <span className="legend-load">Load</span>
              <span className="legend-spend">Spend</span>
            </div>
          </header>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={derived.chart}>
                <CartesianGrid stroke="#e6e8eb" strokeDasharray="3 3" />
                <XAxis dataKey="day" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} width={48} />
                <Tooltip
                  formatter={(value) =>
                    new Intl.NumberFormat(undefined, {
                      style: "currency",
                      currency: derived.currency,
                    }).format(Number(value))
                  }
                />
                <Line
                  type="monotone"
                  dataKey="load"
                  stroke="#2457d6"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="spend"
                  stroke="#16833b"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="panel exceptions-panel">
          <header className="panel-header">
            <div>
              <h2>Operational exceptions</h2>
              <p>Queues that need attention</p>
            </div>
            <IconButton
              label="Refresh exceptions"
              icon={RefreshCw}
              onClick={() => overview.refetch()}
            />
          </header>
          <ExceptionGroup
            title="Offline review"
            count={overview.data.offline.length}
            rows={overview.data.offline.slice(0, 3).map((item) => ({
              primary: `Sequence ${item.sequence_number}`,
              secondary: `${formatMoney(item.amount_minor)} / ${item.card_uid}`,
              status: item.status,
            }))}
          />
          <ExceptionGroup
            title="Failed webhooks"
            count={failedDeliveries.length}
            rows={failedDeliveries.slice(0, 3).map((delivery) => ({
              primary: delivery.event_type,
              secondary: `${delivery.attempts} attempts / ${formatTime(
                delivery.next_retry_at,
              )}`,
              status: delivery.status,
            }))}
          />
        </section>

        <section className="panel recent-panel">
          <header className="panel-header">
            <div>
              <h2>Recent transactions</h2>
              <p>Newest posted activity</p>
            </div>
          </header>
          <TransactionTable
            transactions={overview.data.transactions.items}
            onRefund={setRefundTransaction}
          />
        </section>

        <section className="panel device-panel">
          <header className="panel-header">
            <div>
              <h2>Device health</h2>
              <p>Latest registered state</p>
            </div>
          </header>
          <div className="compact-list">
            {overview.data.devices.items.map((device) => (
              <div key={device.id}>
                <span>
                  <strong>{device.name}</strong>
                  <small>{device.type}</small>
                </span>
                <StatusMark value={device.status} />
              </div>
            ))}
          </div>
        </section>
      </div>
      <RefundDrawer
        transaction={refundTransaction}
        onClose={() => setRefundTransaction(null)}
      />
    </div>
  );
}

function Metric({
  label,
  value,
  detail,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof WalletCards;
  tone: "neutral" | "positive" | "warning";
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
        <em>{detail}</em>
      </span>
      <Icon aria-hidden="true" size={23} />
    </div>
  );
}

function ExceptionGroup({
  title,
  count,
  rows,
}: {
  title: string;
  count: number;
  rows: { primary: string; secondary: string; status: string }[];
}) {
  return (
    <div className="exception-group">
      <h3>
        {title} <span>{count}</span>
      </h3>
      {rows.length ? (
        rows.map((row, index) => (
          <div className="exception-row" key={`${row.primary}-${index}`}>
            <span>
              <strong>{row.primary}</strong>
              <small>{row.secondary}</small>
            </span>
            <StatusMark value={row.status} />
          </div>
        ))
      ) : (
        <p className="clear-queue">No items waiting.</p>
      )}
    </div>
  );
}
