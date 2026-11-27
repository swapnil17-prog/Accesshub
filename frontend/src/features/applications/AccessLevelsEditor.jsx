import { useState } from 'react';
import { useDispatch } from 'react-redux';

import Button from '../../components/Button';
import ConfirmModal from '../../components/ConfirmModal';
import { TextInput } from '../../components/form';
import { useToast } from '../../components/toastContext';
import { addAccessLevel, deleteAccessLevel, renameAccessLevel } from './applicationsSlice';

/** Add, rename and delete an application's access levels. */
export default function AccessLevelsEditor({ application, readOnly = false }) {
  const dispatch = useDispatch();
  const toast = useToast();
  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState(null); // { id, name }
  const [deleting, setDeleting] = useState(null); // level
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(thunk, arg, success) {
    setBusy(true);
    setError(null);
    const result = await dispatch(thunk(arg));
    setBusy(false);
    if (thunk.fulfilled.match(result)) {
      if (success) toast.success(success);
      return true;
    }
    setError(result.payload?.message ?? 'That did not work.');
    return false;
  }

  async function add(event) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    if (await run(addAccessLevel, { appId: application.id, name }, `Added “${name}”.`)) setNewName('');
  }

  async function saveRename(event) {
    event.preventDefault();
    const name = editing.name.trim();
    if (!name) return;
    if (await run(renameAccessLevel, { appId: application.id, levelId: editing.id, name })) setEditing(null);
  }

  async function confirmDelete() {
    const level = deleting;
    setDeleting(null);
    await run(deleteAccessLevel, { appId: application.id, levelId: level.id }, `Deleted “${level.name}”.`);
  }

  return (
    <div>
      {error ? (
        <p role="alert" className="mb-3 text-sm text-rose-600">
          {error}
        </p>
      ) : null}
      <ul className="divide-y divide-slate-100 rounded-md ring-1 ring-slate-200" aria-label="Access levels">
        {application.access_levels.length === 0 ? (
          <li className="px-3 py-3 text-sm text-slate-500">No access levels yet.</li>
        ) : null}
        {application.access_levels.map((level) => (
          <li key={level.id} className="flex items-center gap-2 px-3 py-2">
            {editing?.id === level.id ? (
              <form onSubmit={saveRename} className="flex flex-1 items-center gap-2">
                <TextInput
                  aria-label={`New name for ${level.name}`}
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  autoFocus
                />
                <Button type="submit" size="sm" loading={busy}>
                  Save
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                  Cancel
                </Button>
              </form>
            ) : (
              <>
                <span className="flex-1 text-sm text-slate-900">{level.name}</span>
                {readOnly ? null : (
                  <>
                    <Button size="sm" variant="ghost" onClick={() => setEditing({ id: level.id, name: level.name })}>
                      Rename
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-rose-600 hover:text-rose-700"
                      onClick={() => setDeleting(level)}
                      aria-label={`Delete ${level.name}`}
                    >
                      Delete
                    </Button>
                  </>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
      {readOnly ? null : (
        <form onSubmit={add} className="mt-3 flex gap-2">
          <TextInput
            aria-label="New access level name"
            placeholder="e.g. Read only"
            value={newName}
            maxLength={120}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Button
            type="submit"
            variant="secondary"
            className="shrink-0 whitespace-nowrap"
            disabled={!newName.trim()}
            loading={busy && !editing}
          >
            Add level
          </Button>
        </form>
      )}
      <ConfirmModal
        open={deleting !== null}
        title={`Delete “${deleting?.name}”?`}
        message="Levels that have ever been requested can't be deleted, so the history stays intact."
        confirmLabel="Delete"
        tone="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
