import { diffValues, formatValue } from './diff';

const ROW_STYLE = {
  changed: 'bg-amber-50/60',
  added: 'bg-emerald-50/60',
  removed: 'bg-rose-50/60',
  same: '',
};

const CHANGE_LABEL = { changed: 'Changed', added: 'Added', removed: 'Removed', same: '' };

/** Old vs new values of an audit entry, one row per field. */
export default function JsonDiff({ oldValue, newValue }) {
  const rows = diffValues(oldValue, newValue);
  if (rows.length === 0) return <p className="text-sm text-slate-500">No values were recorded for this event.</p>;
  return (
    <div className="overflow-x-auto rounded-md bg-white ring-1 ring-slate-200">
      <table className="min-w-full text-xs">
        <caption className="sr-only">Changes recorded in this event</caption>
        <thead className="bg-slate-50 text-left text-slate-500">
          <tr>
            <th scope="col" className="px-3 py-2 font-semibold">
              Field
            </th>
            <th scope="col" className="px-3 py-2 font-semibold">
              Before
            </th>
            <th scope="col" className="px-3 py-2 font-semibold">
              After
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 font-mono">
          {rows.map((row) => (
            <tr key={row.key} className={ROW_STYLE[row.change]}>
              <th scope="row" className="whitespace-nowrap px-3 py-2 text-left font-semibold text-slate-700">
                {row.key}
                {CHANGE_LABEL[row.change] ? (
                  <span className="ml-2 font-sans text-[10px] font-medium uppercase tracking-wide text-slate-500">
                    {CHANGE_LABEL[row.change]}
                  </span>
                ) : null}
              </th>
              <td className="px-3 py-2 align-top text-slate-600">
                <pre className={`whitespace-pre-wrap break-all ${row.change === 'changed' || row.change === 'removed' ? 'text-rose-700 line-through decoration-rose-300' : ''}`}>
                  {formatValue(row.before)}
                </pre>
              </td>
              <td className="px-3 py-2 align-top text-slate-900">
                <pre className={`whitespace-pre-wrap break-all ${row.change === 'changed' || row.change === 'added' ? 'text-emerald-800' : ''}`}>
                  {formatValue(row.after)}
                </pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
