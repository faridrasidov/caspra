import { useQuery } from "@tanstack/react-query";
import { Download, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";

import {
  apiRequest,
  type Schemas,
  type TransactionOut,
} from "../api/client";
import { RefundDrawer } from "../components/RefundDrawer";
import { TransactionTable } from "../components/TransactionTable";
import {
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
  SearchField,
} from "../components/ui";

export function TransactionsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [refundTransaction, setRefundTransaction] =
    useState<TransactionOut | null>(null);
  const transactions = useQuery({
    queryKey: ["transactions"],
    queryFn: () =>
      apiRequest<Schemas["PaginatedTransactionOut"]>(
        "/admin/api/v1/transactions?page=1&limit=100",
      ),
  });
  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (transactions.data?.items ?? []).filter(
      (transaction) =>
        (!statusFilter || transaction.status === statusFilter) &&
        (!term || JSON.stringify(transaction).toLowerCase().includes(term)),
    );
  }, [search, statusFilter, transactions.data]);

  return (
    <div>
      <PageHeader
        title="Transactions"
        description="Posted ledger activity, captures, and compensating refunds."
        actions={
          <Button
            icon={Download}
            variant="secondary"
            onClick={() => window.open("/admin/api/v1/transactions/export", "_blank")}
          >
            Export
          </Button>
        }
      />
      <section className="table-panel">
        <div className="table-toolbar">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="Search transactions"
          />
          <label className="filter-control">
            <SlidersHorizontal aria-hidden="true" size={16} />
            <span className="sr-only">Status filter</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="posted">Posted</option>
              <option value="pending">Pending</option>
              <option value="reversed">Reversed</option>
              <option value="failed">Failed</option>
            </select>
          </label>
        </div>
        {transactions.isLoading ? (
          <LoadingState />
        ) : transactions.error ? (
          <ErrorState
            message={transactions.error.message}
            retry={() => transactions.refetch()}
          />
        ) : (
          <TransactionTable transactions={rows} onRefund={setRefundTransaction} />
        )}
      </section>
      <RefundDrawer
        transaction={refundTransaction}
        onClose={() => setRefundTransaction(null)}
      />
    </div>
  );
}
