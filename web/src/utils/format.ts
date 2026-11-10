export function currencyExponent(currency: string) {
  const exponent = new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions().maximumFractionDigits;
  if (exponent === undefined) throw new Error("Currency precision is unavailable");
  return exponent;
}

export function amountInput(amountMinor: number, currency: string) {
  return (amountMinor / 10 ** currencyExponent(currency)).toFixed(currencyExponent(currency));
}

export function toMinorUnits(value: string, currency: string) {
  const exponent = currencyExponent(currency);
  if (!/^\d+(\.\d+)?$/.test(value.trim())) throw new Error("Enter a valid amount");
  const [whole = "0", fraction = ""] = value.trim().split(".");
  if (fraction.length > exponent) throw new Error(`Use at most ${exponent} decimal places`);
  const minor = BigInt(whole) * 10n ** BigInt(exponent) + BigInt(fraction.padEnd(exponent, "0") || "0");
  if (minor > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("Amount is too large");
  return Number(minor);
}

export function formatMoney(amountMinor: number, currency = "USD") {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  }).format(amountMinor / 10 ** currencyExponent(currency));
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
