import { GridIcon, HomeIcon, InboxIcon, ListIcon, PlusIcon, ShieldIcon, UsersIcon } from './components/icons';

/**
 * Sidebar entries. ``roles`` (any-of) hides an item from users without them; items without
 * ``roles`` are shown to everyone. The routes in routes.jsx enforce the same roles.
 */
export const NAV_SECTIONS = [
  {
    label: null,
    items: [{ to: '/', label: 'Dashboard', icon: HomeIcon, end: true }],
  },
  {
    label: 'Access',
    items: [
      { to: '/requests/new', label: 'New request', icon: PlusIcon, roles: ['employee'] },
      { to: '/requests', label: 'My requests', icon: ListIcon, roles: ['employee'], end: true },
      // Anyone can be assigned an approval (e.g. a SPECIFIC_USER step), so no role filter.
      { to: '/approvals', label: 'Approval inbox', icon: InboxIcon, badge: 'inbox' },
    ],
  },
  {
    label: 'Administration',
    items: [
      { to: '/admin/applications', label: 'Applications', icon: GridIcon, roles: ['admin', 'app_owner'] },
      { to: '/admin/users', label: 'Users', icon: UsersIcon, roles: ['admin'] },
      { to: '/audit', label: 'Audit log', icon: ShieldIcon, roles: ['auditor', 'admin'] },
    ],
  },
];

export const ALL_ROLES = ['employee', 'manager', 'app_owner', 'admin', 'auditor'];

export const ROLE_LABELS = {
  employee: 'Employee',
  manager: 'Manager',
  app_owner: 'App owner',
  admin: 'Admin',
  auditor: 'Auditor',
};

export function visibleSections(hasRole) {
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.roles || hasRole(...item.roles)),
  })).filter((section) => section.items.length > 0);
}
