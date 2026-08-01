import {
  AlertTriangle,
  Check,
  LoaderCircle,
  Search,
  X,
  type LucideIcon,
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";

export function Button({
  children,
  icon: Icon,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: LucideIcon;
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  return (
    <button className={`button button-${variant}`} {...props}>
      {Icon ? <Icon aria-hidden="true" size={16} /> : null}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  icon: Icon,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  icon: LucideIcon;
}) {
  return (
    <button
      className="icon-button"
      aria-label={label}
      title={label}
      {...props}
    >
      <Icon aria-hidden="true" size={18} />
    </button>
  );
}

export function StatusMark({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone =
    normalized.includes("fail") ||
    normalized.includes("offline") ||
    normalized.includes("dead") ||
    normalized.includes("reversed")
      ? "danger"
      : normalized.includes("pending") ||
          normalized.includes("review") ||
          normalized.includes("retry") ||
          normalized.includes("leased")
        ? "warning"
        : "success";
  return (
    <span className={`status-mark status-${tone}`}>
      <span aria-hidden="true" />
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder = "Search",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="search-field">
      <Search aria-hidden="true" size={16} />
      <span className="sr-only">{placeholder}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

export function LoadingState({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="state-box" role="status">
      <LoaderCircle className="spin" aria-hidden="true" size={22} />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="state-box state-error" role="alert">
      <AlertTriangle aria-hidden="true" size={22} />
      <span>{message}</span>
      {retry ? (
        <Button variant="secondary" onClick={retry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="state-box">
      <Check aria-hidden="true" size={22} />
      <span>{message}</span>
    </div>
  );
}

export function Drawer({
  title,
  open,
  onClose,
  children,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="drawer-layer">
      <button
        className="drawer-backdrop"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <section className="drawer" role="dialog" aria-modal="true">
        <header>
          <h2>{title}</h2>
          <IconButton label="Close" icon={X} onClick={onClose} />
        </header>
        <div className="drawer-body">{children}</div>
      </section>
    </div>
  );
}

export function FormField({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

export function CommandForm({
  children,
  submitLabel,
  submitting,
  onSubmit,
  onCancel,
}: {
  children: ReactNode;
  submitLabel: string;
  submitting: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  return (
    <form className="command-form" onSubmit={onSubmit}>
      <div className="command-fields">{children}</div>
      <footer>
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Working..." : submitLabel}
        </Button>
      </footer>
    </form>
  );
}

export function formatMoney(amountMinor: number, currency = "USD") {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  }).format(amountMinor / 100);
}

export function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
