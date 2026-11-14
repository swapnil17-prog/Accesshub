/** "PENDING" -> "Pending" */
export function statusLabel(status) {
  if (!status) return '';
  return status.charAt(0) + status.slice(1).toLowerCase();
}
