import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import * as approvalsApi from '../../api/approvals';
import { authState, renderWithProviders, users } from '../../test/utils';
import InboxPage from './InboxPage';

vi.mock('../../api/approvals');

const HOUR = 3600 * 1000;

function item(id, { dueInHours = 10, escalated = false, name = `Requester ${id}` } = {}) {
  const dueAt = new Date(Date.now() + dueInHours * HOUR).toISOString();
  return {
    id,
    step_order: 1,
    assigned_at: new Date().toISOString(),
    due_at: dueAt,
    is_overdue: dueInHours < 0,
    escalated,
    request: {
      id: 100 + id,
      requester: { id: 10 + id, name, email: `r${id}@example.com` },
      application: { id: 1, name: 'Jira' },
      access_level: { id: 2, name: 'Developer' },
      status: 'PENDING',
      current_step: 1,
      total_steps: 2,
      duration_days: null,
      expires_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      justification: 'Needed to work on the migration tickets this quarter.',
    },
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const apiError = (message) => ({ response: { status: 409, data: { error: { code: 'INVALID_STATE', message } } } });

function renderInbox(items) {
  approvalsApi.fetchInbox.mockResolvedValue({ items, page: 1, per_page: 20, total: items.length });
  return renderWithProviders(
    <Routes>
      <Route path="/approvals" element={<InboxPage />} />
    </Routes>,
    { preloadedState: authState(users.admin), route: '/approvals' },
  );
}

const rowFor = (name) => screen.getByText(name).closest('tr');

describe('Approval inbox', () => {
  it('lists pending approvals with requester, app, level, justification and an overdue highlight', async () => {
    renderInbox([item(1, { dueInHours: -2, name: 'Olivia Overdue', escalated: true }), item(2, { name: 'Tom Ontime' })]);

    const overdue = await screen.findByText('Olivia Overdue');
    const overdueRow = overdue.closest('tr');
    expect(within(overdueRow).getByText(/overdue by 2 hours/i)).toBeInTheDocument();
    expect(within(overdueRow).getByText('Overdue')).toBeInTheDocument();
    expect(within(overdueRow).getByText('Escalated')).toBeInTheDocument();
    expect(overdueRow.className).toMatch(/bg-rose-50/);

    const ontimeRow = rowFor('Tom Ontime');
    expect(within(ontimeRow).getByText(/due in 10 hours/i)).toBeInTheDocument();
    expect(ontimeRow.className).not.toMatch(/bg-rose-50/);
    expect(within(ontimeRow).getByText('Jira')).toBeInTheDocument();
    expect(within(ontimeRow).getByText('Developer')).toBeInTheDocument();
    expect(within(ontimeRow).getByText(/migration tickets/)).toBeInTheDocument();
  });

  it('approving removes the row immediately (optimistic) and confirms with a toast', async () => {
    const pending = deferred();
    approvalsApi.approve.mockReturnValue(pending.promise);
    const { store } = renderInbox([item(1, { name: 'Ann Approve' }), item(2, { name: 'Bob Stays' })]);

    await userEvent.click(await screen.findByRole('button', { name: 'Approve request from Ann Approve' }));
    const dialog = screen.getByRole('dialog', { name: 'Approve this request?' });
    await userEvent.type(within(dialog).getByLabelText(/comment/i), 'Looks fine');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve' }));

    // Gone before the API has answered.
    expect(screen.queryByText('Ann Approve')).not.toBeInTheDocument();
    expect(screen.getByText('Bob Stays')).toBeInTheDocument();
    expect(store.getState().approvals.inboxCount).toBe(1);
    expect(approvalsApi.approve).toHaveBeenCalledWith(1, 'Looks fine');

    pending.resolve({ id: 101, status: 'APPROVED' });
    expect(await screen.findByRole('status', { name: '' })).toHaveTextContent('Approved.');
    expect(screen.queryByText('Ann Approve')).not.toBeInTheDocument();
  });

  it('rejecting requires a comment', async () => {
    approvalsApi.reject.mockResolvedValue({ id: 101, status: 'REJECTED' });
    renderInbox([item(1, { name: 'Rita Reject' })]);

    await userEvent.click(await screen.findByRole('button', { name: 'Reject request from Rita Reject' }));
    const dialog = screen.getByRole('dialog', { name: 'Reject this request?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));

    expect(within(dialog).getByText('A comment is required when rejecting.')).toBeInTheDocument();
    expect(approvalsApi.reject).not.toHaveBeenCalled();
    expect(screen.getByText('Rita Reject')).toBeInTheDocument();

    await userEvent.type(within(dialog).getByLabelText(/reason for rejecting/i), '  Use the read-only role  ');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Reject' }));

    expect(approvalsApi.reject).toHaveBeenCalledWith(1, 'Use the read-only role');
    await waitFor(() => expect(screen.queryByText('Rita Reject')).not.toBeInTheDocument());
    expect(await screen.findByText('Rejected.')).toBeInTheDocument();
  });

  it('puts the row back and shows the error when the API refuses', async () => {
    approvalsApi.approve.mockRejectedValue(apiError('This approval has already been decided'));
    const { store } = renderInbox([item(1, { name: 'First' }), item(2, { name: 'Second' })]);

    await userEvent.click(await screen.findByRole('button', { name: 'Approve request from Second' }));
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('This approval has already been decided');
    // restored in its original position, counts restored too
    const names = screen.getAllByText(/^(First|Second)$/).map((el) => el.textContent.split(' ')[0]);
    expect(names).toEqual(['First', 'Second']);
    expect(store.getState().approvals.inbox.total).toBe(2);
  });

  it('bulk-approves the selected rows and reports partial failures', async () => {
    approvalsApi.approve.mockImplementation((id) =>
      id === 2 ? Promise.reject(apiError('Already decided')) : Promise.resolve({ id: 100 + id }),
    );
    renderInbox([item(1, { name: 'One' }), item(2, { name: 'Two' }), item(3, { name: 'Three' })]);

    await screen.findByText('One');
    expect(screen.getByRole('button', { name: /approve selected/i })).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select request from One' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select request from Two' }));
    await userEvent.click(screen.getByRole('button', { name: 'Approve selected (2)' }));

    const dialog = screen.getByRole('dialog', { name: 'Approve 2 requests?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve 2' }));

    expect(approvalsApi.approve).toHaveBeenCalledTimes(2);
    expect(await screen.findByText('Approved 1 of 2 requests.')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Already decided');
    expect(screen.queryByText('One')).not.toBeInTheDocument();
    expect(screen.getByText('Two')).toBeInTheDocument(); // restored
    expect(screen.getByText('Three')).toBeInTheDocument(); // never selected
  });

  it('select-all toggles every visible row', async () => {
    renderInbox([item(1, { name: 'One' }), item(2, { name: 'Two' })]);
    await screen.findByText('One');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select all' }));
    expect(screen.getByRole('button', { name: 'Approve selected (2)' })).toBeEnabled();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Select all' }));
    expect(screen.getByRole('button', { name: /approve selected/i })).toBeDisabled();
  });

  it('moves due time and actions into the row on small screens', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
    try {
      renderInbox([item(1, { name: 'Narrow Nora', dueInHours: -1 })]);
      const row = (await screen.findByText('Narrow Nora')).closest('tr');
      expect(screen.queryByRole('columnheader', { name: /due/i })).not.toBeInTheDocument();
      expect(within(row).getByRole('button', { name: 'Approve request from Narrow Nora' })).toBeInTheDocument();
      expect(within(row).getByText(/overdue by 1 hour/i)).toBeInTheDocument();
    } finally {
      delete window.matchMedia;
    }
  });

  it('shows an empty state when nothing is waiting', async () => {
    renderInbox([]);
    expect(await screen.findByText("You're all caught up")).toBeInTheDocument();
  });
});
