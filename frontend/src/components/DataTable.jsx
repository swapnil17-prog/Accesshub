import { useMemo, useState } from 'react';

import EmptyState from './EmptyState';
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon, ChevronUpIcon } from './icons';
import Spinner from './Spinner';

/**
 * Table with sortable columns and pagination.
 *
 * columns: [{ key, header, render?(row), sortable?, sortValue?(row), className?, align? }]
 *
 * Sorting is client-side by default (on the rows given). Pass ``sort`` + ``onSortChange``
 * to control it instead (e.g. to sort on the server).
 * Pagination is shown when ``pagination = { page, perPage, total, onPageChange }`` is given.
 * Expandable rows: pass ``isExpanded(row)`` and ``renderExpanded(row)``; the expanded
 * content renders in a full-width row under its parent.
 */
export default function DataTable({
  columns,
  rows,
  rowKey = 'id',
  loading = false,
  sort: controlledSort,
  onSortChange,
  pagination,
  onRowClick,
  rowClassName,
  empty,
  caption,
  isExpanded,
  renderExpanded,
}) {
  const [internalSort, setInternalSort] = useState(null);
  const sort = onSortChange ? controlledSort : internalSort;

  const sortedRows = useMemo(() => {
    if (onSortChange || !sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column) return rows;
    const valueOf = column.sortValue ?? ((row) => row[column.key]);
    const direction = sort.direction === 'desc' ? -1 : 1;
    return [...rows].sort((a, b) => {
      const va = valueOf(a);
      const vb = valueOf(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * direction;
      return String(va).localeCompare(String(vb), undefined, { numeric: true }) * direction;
    });
  }, [rows, columns, sort, onSortChange]);

  function toggleSort(key) {
    const next =
      sort?.key === key ? { key, direction: sort.direction === 'asc' ? 'desc' : 'asc' } : { key, direction: 'asc' };
    if (onSortChange) onSortChange(next);
    else setInternalSort(next);
  }

  const keyOf = typeof rowKey === 'function' ? rowKey : (row) => row[rowKey];
  const showEmpty = !loading && sortedRows.length === 0;

  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
      <div className="relative overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <thead className="bg-slate-50">
            <tr>
              {columns.map((column) => {
                const active = sort?.key === column.key;
                const ariaSort = active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : undefined;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={column.sortable ? (ariaSort ?? 'none') : undefined}
                    className={`whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 ${column.align === 'right' ? 'text-right' : 'text-left'} ${column.headerClassName ?? ''}`}
                  >
                    {column.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.key)}
                        className="group inline-flex items-center gap-1 uppercase hover:text-slate-900"
                      >
                        {column.header}
                        <span className={active ? 'text-slate-900' : 'text-slate-300 group-hover:text-slate-400'}>
                          {active && sort.direction === 'desc' ? (
                            <ChevronDownIcon className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronUpIcon className="h-3.5 w-3.5" />
                          )}
                        </span>
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sortedRows.map((row) => [
              <tr
                key={keyOf(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === 'Enter') onRowClick(row);
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                className={`${onRowClick ? 'cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none' : ''} ${rowClassName?.(row) ?? ''}`}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-4 py-3 text-slate-700 ${column.align === 'right' ? 'text-right' : ''} ${column.className ?? ''}`}
                  >
                    {column.render ? column.render(row) : row[column.key]}
                  </td>
                ))}
              </tr>,
              isExpanded?.(row) ? (
                <tr key={`${keyOf(row)}-expanded`} className="bg-slate-50/70">
                  <td colSpan={columns.length} className="px-4 py-4">
                    {renderExpanded(row)}
                  </td>
                </tr>
              ) : null,
            ])}
          </tbody>
        </table>
        {loading ? (
          <div className="flex items-center justify-center bg-white/60 py-10" aria-live="polite">
            <Spinner label="Loading" />
          </div>
        ) : null}
        {showEmpty ? (empty ?? <EmptyState title="Nothing to show" description="No records match." />) : null}
      </div>
      {pagination ? <Pagination {...pagination} /> : null}
    </div>
  );
}

export function Pagination({ page, perPage, total, onPageChange }) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  const from = total === 0 ? 0 : (page - 1) * perPage + 1;
  const to = Math.min(total, page * perPage);
  return (
    <nav
      className="flex items-center justify-between gap-4 border-t border-slate-200 bg-white px-4 py-3 text-sm"
      aria-label="Pagination"
    >
      <p className="text-slate-500">
        {total === 0 ? (
          'No results'
        ) : (
          <>
            Showing <span className="font-medium text-slate-900">{from}</span>–
            <span className="font-medium text-slate-900">{to}</span> of{' '}
            <span className="font-medium text-slate-900">{total}</span>
          </>
        )}
      </p>
      <div className="flex items-center gap-2">
        <span className="hidden text-slate-500 sm:inline">
          Page {page} of {pages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="rounded-md p-1.5 text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Previous page"
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          className="rounded-md p-1.5 text-slate-600 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Next page"
        >
          <ChevronRightIcon className="h-4 w-4" />
        </button>
      </div>
    </nav>
  );
}
