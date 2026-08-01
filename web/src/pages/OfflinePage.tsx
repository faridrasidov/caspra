import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Settings2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import {
  apiRequest,
  type OfflineReviewItemOut,
  type Schemas,
} from "../api/client";
import {
  Button,
  CommandForm,
  Drawer,
  EmptyState,
  ErrorState,
  FormField,
  IconButton,
  LoadingState,
  PageHeader,
  StatusMark,
  formatMoney,
  formatTime,
} from "../components/ui";

export function OfflinePage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<OfflineReviewItemOut | null>(null);
  const [decision, setDecision] = useState<"accept" | "reject">("reject");
  const [reason, setReason] = useState("");
  const [policyOpen, setPolicyOpen] = useState(false);
  const review = useQuery({
    queryKey: ["offline-review"],
    queryFn: () =>
      apiRequest<OfflineReviewItemOut[]>("/admin/api/v1/offline/review"),
  });
  const policy = useQuery({
    queryKey: ["offline-policy"],
    queryFn: () =>
      apiRequest<Schemas["OfflinePolicyOut"] | null>(
        "/admin/api/v1/offline/policy",
      ),
  });
  const decide = useMutation({
    mutationFn: () =>
      apiRequest(`/admin/api/v1/offline/review/${selected?.id}`, {
        method: "POST",
        body: JSON.stringify({ decision, reason }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["offline-review"] });
      setSelected(null);
    },
  });
  const updatePolicy = useMutation({
    mutationFn: (body: Schemas["OfflinePolicyUpdate"]) =>
      apiRequest("/admin/api/v1/offline/policy", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["offline-policy"] });
      setPolicyOpen(false);
    },
  });

  return (
    <div>
      <PageHeader
        title="Offline reconciliation"
        description="Bounded-risk operations that need server or operator disposition."
        actions={
          <Button
            icon={Settings2}
            variant="secondary"
            onClick={() => setPolicyOpen(true)}
          >
            Risk policy
          </Button>
        }
      />
      <section className="policy-strip">
        <span>
          <strong>Offline spending</strong>
          <StatusMark value={policy.data?.enabled ? "enabled" : "disabled"} />
        </span>
        <span>
          Per transaction{" "}
          <strong>{formatMoney(policy.data?.max_transaction_minor ?? 0)}</strong>
        </span>
        <span>
          Queue age{" "}
          <strong>{policy.data?.max_queue_age_seconds ?? 0} seconds</strong>
        </span>
      </section>
      <section className="table-panel">
        {review.isLoading ? (
          <LoadingState />
        ) : review.error ? (
          <ErrorState message={review.error.message} retry={() => review.refetch()} />
        ) : review.data?.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Occurred</th>
                  <th>Device</th>
                  <th>Sequence</th>
                  <th>Card</th>
                  <th className="number-cell">Amount</th>
                  <th>Reason</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {review.data.map((item) => (
                  <tr key={item.id}>
                    <td>{formatTime(item.occurred_at)}</td>
                    <td className="mono">{item.device_id.slice(0, 8)}</td>
                    <td>{item.sequence_number}</td>
                    <td>{item.card_uid}</td>
                    <td className="number-cell">{formatMoney(item.amount_minor)}</td>
                    <td>{item.error}</td>
                    <td className="action-cell action-pair">
                      <IconButton
                        label="Accept operation"
                        icon={Check}
                        onClick={() => {
                          setDecision("accept");
                          setSelected(item);
                        }}
                      />
                      <IconButton
                        label="Reject operation"
                        icon={X}
                        onClick={() => {
                          setDecision("reject");
                          setSelected(item);
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message="No offline operations are waiting for review." />
        )}
      </section>

      <Drawer
        title={`${decision === "accept" ? "Accept" : "Reject"} offline operation`}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
      >
        <CommandForm
          submitLabel={`Confirm ${decision}`}
          submitting={decide.isPending}
          onSubmit={(event) => {
            event.preventDefault();
            decide.mutate();
          }}
          onCancel={() => setSelected(null)}
        >
          <FormField label="Reason required">
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              required
            />
          </FormField>
        </CommandForm>
      </Drawer>
      <PolicyDrawer
        open={policyOpen}
        current={policy.data ?? null}
        saving={updatePolicy.isPending}
        onClose={() => setPolicyOpen(false)}
        onSave={(body) => updatePolicy.mutate(body)}
      />
    </div>
  );
}

function PolicyDrawer({
  open,
  current,
  saving,
  onClose,
  onSave,
}: {
  open: boolean;
  current: Schemas["OfflinePolicyOut"] | null;
  saving: boolean;
  onClose: () => void;
  onSave: (body: Schemas["OfflinePolicyUpdate"]) => void;
}) {
  const [enabled, setEnabled] = useState(current?.enabled ?? false);
  const [riskAccepted, setRiskAccepted] = useState(
    current?.uid_risk_accepted ?? false,
  );
  useEffect(() => {
    setEnabled(current?.enabled ?? false);
    setRiskAccepted(current?.uid_risk_accepted ?? false);
  }, [current]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const minor = (name: string) => Math.round(Number(data.get(name)) * 100);
    onSave({
      enabled,
      uid_risk_accepted: riskAccepted,
      max_transaction_minor: minor("max_transaction"),
      max_card_total_minor: minor("max_card"),
      max_device_total_minor: minor("max_device"),
      max_outage_total_minor: minor("max_outage"),
      max_queue_age_seconds: Number(data.get("queue_age")),
      max_queue_size: Number(data.get("queue_size")),
      sync_interval_seconds: 60,
    });
  }
  return (
    <Drawer title="Offline risk policy" open={open} onClose={onClose}>
      <CommandForm
        submitLabel="Save policy"
        submitting={saving}
        onSubmit={submit}
        onCancel={onClose}
      >
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          <span>Enable offline spending</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={riskAccepted}
            onChange={(event) => setRiskAccepted(event.target.checked)}
          />
          <span>Accept UID-only card cloning risk</span>
        </label>
        <div className="form-grid">
          <FormField label="Per transaction">
            <input
              name="max_transaction"
              type="number"
              min="0"
              step="0.01"
              defaultValue={(current?.max_transaction_minor ?? 0) / 100}
              required
            />
          </FormField>
          <FormField label="Per card">
            <input
              name="max_card"
              type="number"
              min="0"
              step="0.01"
              defaultValue={(current?.max_card_total_minor ?? 0) / 100}
              required
            />
          </FormField>
          <FormField label="Per device">
            <input
              name="max_device"
              type="number"
              min="0"
              step="0.01"
              defaultValue={(current?.max_device_total_minor ?? 0) / 100}
              required
            />
          </FormField>
          <FormField label="Outage total">
            <input
              name="max_outage"
              type="number"
              min="0"
              step="0.01"
              defaultValue={(current?.max_outage_total_minor ?? 0) / 100}
              required
            />
          </FormField>
          <FormField label="Queue age (seconds)">
            <input
              name="queue_age"
              type="number"
              min="60"
              defaultValue={current?.max_queue_age_seconds ?? 3600}
              required
            />
          </FormField>
          <FormField label="Queue size">
            <input
              name="queue_size"
              type="number"
              min="1"
              max="500"
              defaultValue={current?.max_queue_size ?? 100}
              required
            />
          </FormField>
        </div>
      </CommandForm>
    </Drawer>
  );
}
