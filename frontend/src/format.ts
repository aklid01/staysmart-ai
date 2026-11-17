export function money(value: number | null | undefined, currency: string): string | null {
  return value == null ? null : `${value.toFixed(2)} ${currency}`
}

export function moneyOrText(
  value: number | null | undefined,
  currency: string,
  fallback: string,
): string {
  return money(value, currency) ?? fallback
}
