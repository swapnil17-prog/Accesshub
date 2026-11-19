import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import Button from '../../components/Button';
import DataTable from '../../components/DataTable';
import EmptyState from '../../components/EmptyState';
import { ErrorAlert, Select, TextInput } from '../../components/form';
import { SearchIcon, UsersIcon } from '../../components/icons';
import PageHeader from '../../components/PageHeader';
import StatusBadge from '../../components/StatusBadge';
import { useDebounce } from '../../hooks/useDebounce';
import { ALL_ROLES, ROLE_LABELS } from '../../navigation';
import EditUserModal from './EditUserModal';
import { fetchUsers, selectUsers } from './usersSlice';

function RoleChips({ roles }) {
  return (
    <div className="flex flex-wrap gap-1">
      {roles.map((role) => (
        <span key={role} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">
          {ROLE_LABELS[role] ?? role}
        </span>
      ))}
    </div>
  );
}

export default function UsersAdminPage() {
  const dispatch = useDispatch();
  const list = useSelector(selectUsers);
  const [query, setQuery] = useState('');
  const [role, setRole] = useState('');
  const [active, setActive] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const q = useDebounce(query.trim(), 300);

  useEffect(() => {
    dispatch(fetchUsers({ page, filters: { q, role, is_active: active } }));
  }, [dispatch, page, q, role, active]);

  function filterChange(setter) {
    return (event) => {
      setter(event.target.value);
      setPage(1);
    };
  }

  const columns = [
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (u) => (
        <div>
          <p className="font-medium text-slate-900">{u.name}</p>
          <p className="text-xs text-slate-500">{u.email}</p>
        </div>
      ),
    },
    { key: 'department', header: 'Department', sortable: true, render: (u) => u.department || '—' },
    { key: 'manager', header: 'Manager', sortable: true, sortValue: (u) => u.manager?.name, render: (u) => u.manager?.name ?? '—' },
    { key: 'roles', header: 'Roles', render: (u) => <RoleChips roles={u.roles} /> },
    {
      key: 'is_active',
      header: 'Status',
      sortable: true,
      sortValue: (u) => (u.is_active ? 0 : 1),
      render: (u) => <StatusBadge status={u.is_active ? 'ACTIVE' : 'INACTIVE'} />,
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      render: (u) => (
        <Button size="sm" variant="secondary" onClick={() => setEditing(u)} aria-label={`Edit ${u.name}`}>
          Edit
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Users" description="Departments, reporting lines, roles and access to AccessHub." />
      <div className="mb-4 grid gap-3 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200 sm:grid-cols-3">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <TextInput
            type="search"
            aria-label="Search users"
            placeholder="Search name or email"
            value={query}
            onChange={filterChange(setQuery)}
            className="pl-9"
          />
        </div>
        <Select aria-label="Role" value={role} onChange={filterChange(setRole)}>
          <option value="">All roles</option>
          {ALL_ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </Select>
        <Select aria-label="Status" value={active} onChange={filterChange(setActive)}>
          <option value="">Active and inactive</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </Select>
      </div>
      {list.error ? (
        <div className="mb-4">
          <ErrorAlert title="Couldn't load users">{list.error.message}</ErrorAlert>
        </div>
      ) : null}
      <DataTable
        caption="Users"
        columns={columns}
        rows={list.items}
        loading={list.status === 'loading'}
        pagination={{ page: list.page, perPage: list.perPage, total: list.total, onPageChange: setPage }}
        empty={<EmptyState icon={UsersIcon} title="No users match" description="Try a different search or filter." />}
      />
      {editing ? (
        <EditUserModal
          user={editing}
          onClose={(saved) => {
            setEditing(null);
            if (saved) dispatch(fetchUsers({ page, filters: { q, role, is_active: active } }));
          }}
        />
      ) : null}
    </>
  );
}
