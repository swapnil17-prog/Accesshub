/**
 * Field-by-field comparison of an audit row's old_value and new_value.
 * Returns [{ key, before, after, change: 'added' | 'removed' | 'changed' | 'same' }],
 * changed fields first, then the rest in key order.
 */
export function diffValues(oldValue, newValue) {
  const before = oldValue ?? {};
  const after = newValue ?? {};
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].sort();
  const rows = keys.map((key) => {
    const inBefore = Object.prototype.hasOwnProperty.call(before, key);
    const inAfter = Object.prototype.hasOwnProperty.call(after, key);
    let change = 'same';
    if (!inBefore) change = 'added';
    else if (!inAfter) change = 'removed';
    else if (JSON.stringify(before[key]) !== JSON.stringify(after[key])) change = 'changed';
    return { key, before: before[key], after: after[key], change };
  });
  const order = { changed: 0, added: 1, removed: 2, same: 3 };
  return rows.sort((a, b) => order[a.change] - order[b.change] || a.key.localeCompare(b.key));
}

export function formatValue(value) {
  if (value === undefined) return '';
  if (value === null) return 'null';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}
