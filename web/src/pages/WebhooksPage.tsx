import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { useState } from "react";

import { apiRequest, type Schemas } from "../api/client";
import {
  EmptyState,
  ErrorState,
  IconButton,
  LoadingState,
  PageHeader,
  StatusMark,
  formatTime,
} from "../components/ui";

export function WebhooksPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<"subscriptions" | "deliveries">("deliveries");
  const subscriptions = useQuery({
    queryKey: ["webhooks"],
    queryFn: () =>
      apiRequest<Schemas["PaginatedWebhookOut"]>(
        "/admin/api/v1/webhooks?page=1&limit=100",
      ),
  });
  const deliveries = useQuery({
    queryKey: ["webhook-deliveries"],
    queryFn: () =>
      apiRequest<Schemas["PaginatedWebhookDeliveryOut"]>(
        "/admin/api/v1/webhooks/deliveries?page=1&limit=100",
      ),
  });
  const replay = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/admin/api/v1/webhooks/deliveries/${id}/replay`, {
        method: "POST",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["webhook-deliveries"] }),
  });
  const active = view === "deliveries" ? deliveries : subscriptions;

  return (
    <div>
      <PageHeader
        title="Webhooks"
        description="Signed event subscriptions, retries, and dead-letter recovery."
      />
      <div className="segmented-control">
        <button
          className={view === "deliveries" ? "active" : ""}
          onClick={() => setView("deliveries")}
        >
          Deliveries
        </button>
        <button
          className={view === "subscriptions" ? "active" : ""}
          onClick={() => setView("subscriptions")}
        >
          Subscriptions
        </button>
      </div>
      <section className="table-panel">
        {active.isLoading ? (
          <LoadingState />
        ) : active.error ? (
          <ErrorState message={active.error.message} retry={() => active.refetch()} />
        ) : view === "deliveries" ? (
          deliveries.data?.items.length ? (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Created</th>
                    <th>Event</th>
                    <th>Status</th>
                    <th>Attempts</th>
                    <th>Response</th>
                    <th>Next retry</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {deliveries.data.items.map((delivery) => (
                    <tr key={delivery.id}>
                      <td>{formatTime(delivery.created_at)}</td>
                      <td>{delivery.event_type}</td>
                      <td>
                        <StatusMark value={delivery.status} />
                      </td>
                      <td>{delivery.attempts}</td>
                      <td>{delivery.response_code ?? delivery.error ?? "-"}</td>
                      <td>{formatTime(delivery.next_retry_at)}</td>
                      <td className="action-cell">
                        <IconButton
                          label="Replay delivery"
                          icon={RefreshCcw}
                          onClick={() => replay.mutate(delivery.id)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message="No webhook deliveries have been queued." />
          )
        ) : subscriptions.data?.items.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Destination</th>
                  <th>Events</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {subscriptions.data.items.map((webhook) => (
                  <tr key={webhook.id}>
                    <td>{webhook.url}</td>
                    <td>{(webhook.events ?? []).join(", ")}</td>
                    <td>
                      <StatusMark value={webhook.active ? "active" : "inactive"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message="No webhook subscriptions are configured." />
        )}
      </section>
    </div>
  );
}
