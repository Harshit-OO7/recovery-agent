export function formatRupees(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount).replace('?', 'Rs. ');
}

export function formatCompactRupees(amount: number): string {
  if (amount >= 100000) {
    return `Rs. ${(amount / 100000).toFixed(2)}L`;
  }
  if (amount >= 1000) {
    return `Rs. ${(amount / 1000).toFixed(1)}k`;
  }
  return `Rs. ${amount.toFixed(0)}`;
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}
