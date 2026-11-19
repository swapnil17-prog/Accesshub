import { useEffect, useId, useState } from 'react';

import * as usersApi from '../api/users';
import { useDebounce } from '../hooks/useDebounce';
import { controlClass } from '../utils/forms';
import { SearchIcon, XIcon } from './icons';
import Spinner from './Spinner';

/**
 * Search-and-pick an active user (via GET /api/users/lookup).
 * ``value``: {id, name, email} | null. ``onChange`` receives the same shape.
 */
export default function UserPicker({ id, value, onChange, error, placeholder = 'Search by name or email', disabled }) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const listId = `${inputId}-options`;
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const debounced = useDebounce(query, 250);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setLoading(true);
    usersApi
      .lookupUsers(debounced.trim())
      .then((items) => {
        if (!cancelled) setResults(items);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced, open]);

  if (value) {
    return (
      <div
        className={`flex items-center justify-between rounded-md px-3 py-2 text-sm ring-1 ring-inset ${error ? 'ring-rose-400' : 'ring-slate-300'} ${disabled ? 'bg-slate-50' : 'bg-white'}`}
      >
        <span className="min-w-0 truncate">
          <span className="font-medium text-slate-900">{value.name}</span>{' '}
          <span className="text-slate-500">{value.email}</span>
        </span>
        {disabled ? null : (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="ml-2 rounded p-0.5 text-slate-400 hover:text-slate-600"
            aria-label={`Clear ${value.name}`}
          >
            <XIcon className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="relative">
      <SearchIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={error ? true : undefined}
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className={`${controlClass(error)} pl-9 pr-3`}
      />
      {open ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-sm shadow-lg ring-1 ring-slate-900/10"
        >
          {loading && results.length === 0 ? (
            <li className="px-3 py-2">
              <Spinner size="sm" label="Searching" />
            </li>
          ) : results.length === 0 ? (
            <li className="px-3 py-2 text-slate-500">No matching users</li>
          ) : (
            results.map((user) => (
              <li key={user.id} role="option" aria-selected={false}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    onChange(user);
                    setQuery('');
                    setOpen(false);
                  }}
                  className="block w-full px-3 py-2 text-left hover:bg-indigo-50"
                >
                  <span className="font-medium text-slate-900">{user.name}</span>
                  <span className="block text-xs text-slate-500">{user.email}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
