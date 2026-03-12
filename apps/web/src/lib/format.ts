export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDate(date: Date | string | null | undefined): string {
  if (!date) return "N/A";
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d.getTime())) return "N/A";
  return new Intl.DateTimeFormat("en-US").format(d);
}
