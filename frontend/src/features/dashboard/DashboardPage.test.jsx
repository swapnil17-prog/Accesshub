import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as approvalsApi from '../../api/approvals';
import * as auditApi from '../../api/audit';
import * as requestsApi from '../../api/requests';
import { authState, renderWithProviders, users } from '../../test/utils';
import DashboardPage from './DashboardPage';
// Compile the lazily loaded Recharts chunk during collection, not inside the timed test.
import './SummaryCharts';

vi.mock('../../api/approvals');
vi.mock('../../api/audit');
vi.mock('../../api/requests');

const SUMMARY = {
  total_requests: 41,
  by_status: { PENDING: 9, APPROVED: 15, REJECTED: 8, CANCELLED: 5, EXPIRED: 4 },
  by_application: [
    {
      application_id: 4,
      name: 'AWS Console',
      total: 14,
      by_status: { PENDING: 3, APPROVED: 5, REJECTED: 3, CANCELLED: 2, EXPIRED: 1 },
    },
  ],
  avg_approval_hours: 39.8,
  escalations_last_30_days: 8,
  overdue_approvals: 2,
};

beforeEach(() => {
  requestsApi.listRequests.mockResolvedValue({ items: [], page: 1, per_page: 1, total: 2 });
  approvalsApi.fetchInbox.mockResolvedValue({
    items: [{ id: 1, is_overdue: true }, { id: 2, is_overdue: false }, { id: 3, is_overdue: false }],
    page: 1,
    per_page: 100,
    total: 3,
  });
  auditApi.fetchSummary.mockResolvedValue(SUMMARY);
});

const tile = (label) => screen.getByText(label).parentElement;

describe('Dashboard', () => {
  it('shows an employee their own numbers and no organisation report', async () => {
    renderWithProviders(<DashboardPage />, { preloadedState: authState(users.employee) });
    expect(await within(tile('My pending requests')).findByText('2')).toBeInTheDocument();
    expect(within(tile('Waiting for my approval')).getByText('3')).toBeInTheDocument();
    expect(within(tile('Overdue in my inbox')).getByText('1')).toBeInTheDocument();
    expect(requestsApi.listRequests).toHaveBeenCalledWith(
      expect.objectContaining({ filters: { mine: true, status: 'PENDING' } }),
    );
    expect(screen.queryByText('Organisation')).not.toBeInTheDocument();
    expect(auditApi.fetchSummary).not.toHaveBeenCalled();
  });

  it('shows admins the organisation tiles and charts, each with a table view', async () => {
    renderWithProviders(<DashboardPage />, { preloadedState: authState(users.admin) });
    expect(await screen.findByText('39.8 h')).toBeInTheDocument();
    expect(within(tile('Total requests')).getByText('41')).toBeInTheDocument();
    expect(within(tile('Escalations')).getByText('8')).toBeInTheDocument();

    const statusCard = (await screen.findByRole('heading', { name: 'Requests by status' }, { timeout: 8000 })).closest('section');
    await userEvent.click(within(statusCard).getByRole('button', { name: 'Show table' }));
    const statusTable = within(statusCard).getByRole('table', { name: 'Requests by status' });
    expect(within(statusTable).getByRole('row', { name: 'Approved 15' })).toBeInTheDocument();

    const appCard = screen.getByRole('heading', { name: 'Requests by application' }).closest('section');
    expect(within(appCard).getByRole('list', { name: 'Legend' })).toHaveTextContent(/Approved.*Pending.*Cancelled.*Rejected.*Expired/);
    await userEvent.click(within(appCard).getByRole('button', { name: 'Show table' }));
    expect(within(appCard).getByRole('row', { name: 'AWS Console 5 3 2 3 1 14' })).toBeInTheDocument();
  });
});
