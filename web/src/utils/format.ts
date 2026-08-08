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

export function renderValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return formatTime(value);
  }
  if (typeof value === "string" && value.length > 30) {
    return value.slice(0, 12).toUpperCase();
  }
  return String(value).replaceAll("_", " ");
}
