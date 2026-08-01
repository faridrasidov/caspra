import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { apiRequest, type TransactionOut } from "../api/client";
import {
  CommandForm,
  Drawer,
  FormField,
  formatMoney,
  formatTime,
} from "./ui";

export function RefundDrawer({
  transaction,
  onClose,
}: {
  transaction: TransactionOut | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    setAmount(
      transaction ? (transaction.amount_minor / 100).toFixed(2) : "",
    );
    setReason("");
  }, [transaction]);

  const refund = useMutation({
    mutationFn: async () => {
      if (!transaction) return;
      await apiRequest(
        `/admin/api/v1/transactions/${transaction.id}/refund`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotency_key: crypto.randomUUID(),
            amount_minor: Math.round(Number(amount) * 100),
            reason,
          }),
        },
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["transactions"] });
      onClose();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    refund.mutate();
  }

  return (
    <Drawer title="Refund transaction" open={Boolean(transaction)} onClose={onClose}>
      {transaction ? (
        <CommandForm
          submitLabel="Confirm refund"
          submitting={refund.isPending}
          onSubmit={submit}
          onCancel={onClose}
        >
          <dl className="detail-list">
            <div>
              <dt>Transaction</dt>
              <dd className="mono">{transaction.id.slice(0, 12).toUpperCase()}</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>{formatTime(transaction.created_at)}</dd>
            </div>
            <div>
              <dt>Original amount</dt>
              <dd>{formatMoney(transaction.amount_minor, transaction.currency)}</dd>
            </div>
          </dl>
          <FormField
            label="Refund amount"
            hint={`Maximum ${formatMoney(
              transaction.amount_minor,
              transaction.currency,
            )}`}
          >
            <input
              type="number"
              min="0.01"
              max={(transaction.amount_minor / 100).toFixed(2)}
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              required
            />
          </FormField>
          <FormField label="Reason required">
            <select
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
            >
              <option value="">Select reason</option>
              <option value="Customer request">Customer request</option>
              <option value="Duplicate charge">Duplicate charge</option>
              <option value="Operator correction">Operator correction</option>
              <option value="Service issue">Service issue</option>
            </select>
          </FormField>
          {refund.error ? (
            <p className="form-error" role="alert">
              {refund.error.message}
            </p>
          ) : null}
        </CommandForm>
      ) : null}
    </Drawer>
  );
}
