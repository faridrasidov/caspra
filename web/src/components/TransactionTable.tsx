import { MoreVertical, RotateCcw } from "lucide-react";

import type { TransactionOut } from "../api/client";
import {
  EmptyState,
  IconButton,
  StatusMark,
  formatMoney,
  formatTime,
} from "./ui";

export function TransactionTable({
  transactions,
  onRefund,
}: {
  transactions: TransactionOut[];
  onRefund?: (transaction: TransactionOut) => void;
}) {
  if (!transactions.length) {
    return <EmptyState message="No transactions match this view." />;
  }
  return (
    <div className="table-scroll">
      <table className="data-table transaction-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Reference</th>
            <th>Wallet</th>
            <th>Type</th>
            <th className="number-cell">Amount</th>
            <th>Status</th>
            <th>Channel</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => {
            const canRefund =
              ["debit", "capture"].includes(transaction.type) &&
              transaction.status === "posted";
            return (
              <tr key={transaction.id}>
                <td>{formatTime(transaction.created_at)}</td>
                <td className="mono">{transaction.id.slice(0, 8).toUpperCase()}</td>
                <td className="mono">
                  {transaction.wallet_id?.slice(0, 8).toUpperCase() ?? "-"}
                </td>
                <td className="capitalize">{transaction.type}</td>
                <td
                  className={`number-cell ${
                    ["debit", "refund"].includes(transaction.type)
                      ? "amount-out"
                      : ""
                  }`}
                >
                  {formatMoney(transaction.amount_minor, transaction.currency)}
                </td>
                <td>
                  <StatusMark value={transaction.status} />
                </td>
                <td>
                  {transaction.device_id
                    ? `Device ${transaction.device_id.slice(0, 5)}`
                    : "Admin"}
                </td>
                <td className="action-cell">
                  {canRefund && onRefund ? (
                    <IconButton
                      label="Refund transaction"
                      icon={RotateCcw}
                      onClick={() => onRefund(transaction)}
                    />
                  ) : (
                    <IconButton label="Transaction actions" icon={MoreVertical} disabled />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
