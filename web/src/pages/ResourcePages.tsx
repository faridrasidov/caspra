import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CreditCard,
  KeyRound,
  Plus,
  RotateCcw,
  WalletCards,
} from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import { apiRequest, type Schemas } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
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
  SearchField,
  StatusMark,
  formatMoney,
  formatTime,
} from "../components/ui";

type ResourceRecord = Record<string, unknown> & { id: string };
type PaginatedResult = {
  items: ResourceRecord[];
  total: number;
  page: number;
  limit: number;
};
type Column = {
  key: string;
  label: string;
  render?: (row: ResourceRecord) => ReactNode;
  numeric?: boolean;
};

function ResourcePage({
  title,
  description,
  endpoint,
  columns,
  action,
  rowAction,
}: {
  title: string;
  description: string;
  endpoint: string;
  columns: Column[];
  action?: ReactNode;
  rowAction?: (row: ResourceRecord) => ReactNode;
}) {
  const [search, setSearch] = useState("");
  const resource = useQuery({
    queryKey: ["resource", endpoint],
    queryFn: () =>
      apiRequest<PaginatedResult>(`${endpoint}?page=1&limit=100`),
  });
  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return resource.data?.items ?? [];
    return (resource.data?.items ?? []).filter((row) =>
      JSON.stringify(row).toLowerCase().includes(normalized),
    );
  }, [resource.data, search]);

  return (
    <div className="resource-page">
      <PageHeader title={title} description={description} actions={action} />
      <section className="table-panel">
        <div className="table-toolbar">
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder={`Search ${title.toLowerCase()}`}
          />
          <span>{resource.data?.total ?? 0} records</span>
        </div>
        {resource.isLoading ? (
          <LoadingState />
        ) : resource.error ? (
          <ErrorState
            message={resource.error.message}
            retry={() => resource.refetch()}
          />
        ) : rows.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th
                      key={column.key}
                      className={column.numeric ? "number-cell" : undefined}
                    >
                      {column.label}
                    </th>
                  ))}
                  {rowAction ? <th aria-label="Actions" /> : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        className={column.numeric ? "number-cell" : undefined}
                      >
                        {column.render
                          ? column.render(row)
                          : renderValue(row[column.key])}
                      </td>
                    ))}
                    {rowAction ? (
                      <td className="action-cell">{rowAction(row)}</td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message={`No ${title.toLowerCase()} found.`} />
        )}
      </section>
    </div>
  );
}

function renderValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return formatTime(value);
  }
  if (typeof value === "string" && value.length > 30) {
    return <span className="mono">{value.slice(0, 12).toUpperCase()}</span>;
  }
  return String(value).replaceAll("_", " ");
}

function useCreateResource(endpoint: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: unknown) =>
      apiRequest(endpoint, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["resource", endpoint] }),
  });
}

export function CustomersPage() {
  const [open, setOpen] = useState(false);
  const create = useCreateResource("/admin/api/v1/customers");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [externalId, setExternalId] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate(
      {
        full_name: fullName || null,
        email: email || null,
        external_id: externalId || null,
      },
      { onSuccess: () => setOpen(false) },
    );
  }
  return (
    <>
      <ResourcePage
        title="Customers"
        description="Customer identities and stored-value relationships."
        endpoint="/admin/api/v1/customers"
        action={
          <Button icon={Plus} onClick={() => setOpen(true)}>
            Add customer
          </Button>
        }
        columns={[
          { key: "full_name", label: "Name" },
          { key: "email", label: "Email" },
          { key: "phone", label: "Phone" },
          { key: "external_id", label: "External ID" },
          {
            key: "status",
            label: "Status",
            render: (row) => <StatusMark value={String(row.status)} />,
          },
          { key: "created_at", label: "Created" },
        ]}
      />
      <Drawer title="Add customer" open={open} onClose={() => setOpen(false)}>
        <CommandForm
          submitLabel="Create customer"
          submitting={create.isPending}
          onSubmit={submit}
          onCancel={() => setOpen(false)}
        >
          <FormField label="Full name">
            <input
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
            />
          </FormField>
          <FormField label="Email">
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </FormField>
          <FormField label="External ID">
            <input
              value={externalId}
              onChange={(event) => setExternalId(event.target.value)}
            />
          </FormField>
          {create.error ? <p className="form-error">{create.error.message}</p> : null}
        </CommandForm>
      </Drawer>
    </>
  );
}

export function CardsPage() {
  const [open, setOpen] = useState(false);
  const [uid, setUid] = useState("");
  const [customerId, setCustomerId] = useState("");
  const create = useCreateResource("/admin/api/v1/cards");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate(
      { uid, type: "rfid", customer_id: customerId || null },
      { onSuccess: () => setOpen(false) },
    );
  }
  return (
    <>
      <ResourcePage
        title="Cards"
        description="RFID and NFC credentials assigned to customers."
        endpoint="/admin/api/v1/cards"
        action={
          <Button icon={CreditCard} onClick={() => setOpen(true)}>
            Register card
          </Button>
        }
        columns={[
          { key: "uid", label: "UID" },
          { key: "type", label: "Type" },
          { key: "customer_id", label: "Customer" },
          {
            key: "status",
            label: "Status",
            render: (row) => <StatusMark value={String(row.status)} />,
          },
          { key: "created_at", label: "Registered" },
        ]}
      />
      <Drawer title="Register card" open={open} onClose={() => setOpen(false)}>
        <CommandForm
          submitLabel="Register card"
          submitting={create.isPending}
          onSubmit={submit}
          onCancel={() => setOpen(false)}
        >
          <FormField label="Card UID">
            <input value={uid} onChange={(event) => setUid(event.target.value)} required />
          </FormField>
          <FormField label="Customer ID" hint="Optional; the card can be assigned later.">
            <input
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
            />
          </FormField>
        </CommandForm>
      </Drawer>
    </>
  );
}

export function WalletsPage() {
  const queryClient = useQueryClient();
  const [wallet, setWallet] = useState<ResourceRecord | null>(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const topup = useMutation({
    mutationFn: () =>
      apiRequest(`/admin/api/v1/wallets/${wallet?.id}/topup`, {
        method: "POST",
        body: JSON.stringify({
          idempotency_key: crypto.randomUUID(),
          amount_minor: Math.round(Number(amount) * 100),
          currency: wallet?.currency,
          description: reason,
        }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["resource", "/admin/api/v1/wallets"],
      });
      setWallet(null);
    },
  });
  return (
    <>
      <ResourcePage
        title="Wallets"
        description="Cached balances backed by immutable ledger entries."
        endpoint="/admin/api/v1/wallets"
        columns={[
          { key: "id", label: "Wallet" },
          { key: "customer_id", label: "Customer" },
          { key: "type", label: "Type" },
          { key: "currency", label: "Currency" },
          {
            key: "balance_minor",
            label: "Balance",
            numeric: true,
            render: (row) =>
              formatMoney(Number(row.balance_minor), String(row.currency)),
          },
          {
            key: "status",
            label: "Status",
            render: (row) => <StatusMark value={String(row.status)} />,
          },
        ]}
        rowAction={(row) => (
          <IconButton
            label="Top up wallet"
            icon={WalletCards}
            onClick={() => setWallet(row)}
          />
        )}
      />
      <Drawer title="Top up wallet" open={Boolean(wallet)} onClose={() => setWallet(null)}>
        <CommandForm
          submitLabel="Confirm top-up"
          submitting={topup.isPending}
          onSubmit={(event) => {
            event.preventDefault();
            topup.mutate();
          }}
          onCancel={() => setWallet(null)}
        >
          <FormField label="Amount">
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              required
            />
          </FormField>
          <FormField label="Reason required">
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
            />
          </FormField>
        </CommandForm>
      </Drawer>
    </>
  );
}

export function DevicesPage() {
  const queryClient = useQueryClient();
  const { permissions } = useAuth();
  const [device, setDevice] = useState<ResourceRecord | null>(null);
  const [reason, setReason] = useState("");
  const reset = useMutation({
    mutationFn: () =>
      apiRequest(`/admin/api/v1/devices/${device?.id}/reset`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["resource", "/admin/api/v1/devices"],
      });
      setDevice(null);
      setReason("");
    },
  });
  return (
    <>
      <ResourcePage
        title="Devices"
        description="Reader, kiosk, and gateway fleet status."
        endpoint="/admin/api/v1/devices"
        columns={[
          { key: "name", label: "Device" },
          { key: "serial", label: "Serial" },
          { key: "type", label: "Type" },
          { key: "location_id", label: "Location" },
          {
            key: "status",
            label: "Status",
            render: (row) => <StatusMark value={String(row.status)} />,
          },
        ]}
        rowAction={
          permissions.has("devices:manage")
            ? (row) => (
                <IconButton
                  label="Queue device reset"
                  icon={RotateCcw}
                  onClick={() => setDevice(row)}
                />
              )
            : undefined
        }
      />
      <Drawer
        title="Queue device reset"
        open={Boolean(device)}
        onClose={() => setDevice(null)}
      >
        <CommandForm
          submitLabel="Queue reset"
          submitting={reset.isPending}
          onSubmit={(event) => {
            event.preventDefault();
            reset.mutate();
          }}
          onCancel={() => setDevice(null)}
        >
          <FormField label="Reason required">
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </FormField>
          {reset.error ? <p className="form-error">{reset.error.message}</p> : null}
        </CommandForm>
      </Drawer>
    </>
  );
}

export function ApiKeysPage() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const create = useCreateResource("/admin/api/v1/api-keys");
  return (
    <>
      <ResourcePage
        title="API keys"
        description="Tenant credentials for server-to-server integrations."
        endpoint="/admin/api/v1/api-keys"
        action={
          <Button icon={KeyRound} onClick={() => setOpen(true)}>
            Create key
          </Button>
        }
        columns={[
          { key: "name", label: "Name" },
          { key: "prefix", label: "Prefix" },
          { key: "scopes", label: "Scopes" },
          { key: "last_used_at", label: "Last used" },
          {
            key: "revoked",
            label: "Status",
            render: (row) => (
              <StatusMark value={row.revoked ? "revoked" : "active"} />
            ),
          },
        ]}
      />
      <Drawer title="Create API key" open={open} onClose={() => setOpen(false)}>
        {createdKey ? (
          <div className="one-time-secret">
            <p>This key is shown once.</p>
            <code>{createdKey}</code>
            <Button
              onClick={() => {
                navigator.clipboard.writeText(createdKey);
                setOpen(false);
              }}
            >
              Copy and close
            </Button>
          </div>
        ) : (
          <CommandForm
            submitLabel="Create key"
            submitting={create.isPending}
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate(
                { name, scopes: [] },
                {
                  onSuccess: (result) =>
                    setCreatedKey(
                      (result as Schemas["ApiKeyCreateResult"]).api_key,
                    ),
                },
              );
            }}
            onCancel={() => setOpen(false)}
          >
            <FormField label="Key name">
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </FormField>
          </CommandForm>
        )}
      </Drawer>
    </>
  );
}

export function AuditPage() {
  return (
    <ResourcePage
      title="Audit log"
      description="Immutable operator activity with request correlation."
      endpoint="/admin/api/v1/audit"
      columns={[
        { key: "created_at", label: "Time" },
        { key: "actor_user_id", label: "Actor" },
        { key: "action", label: "Action" },
        { key: "target_type", label: "Target" },
        { key: "target_id", label: "Target ID" },
      ]}
    />
  );
}
