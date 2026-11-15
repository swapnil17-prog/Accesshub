import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import * as requestsApi from '../../api/requests';
import { authState, renderWithProviders, users } from '../../test/utils';
import RequestDetailPage from './RequestDetailPage';

vi.mock('../../api/requests');

const now = new Date().toISOString();
const person = (id, name) => ({ id, name, email: `${id}@example.com` });

function request(overrides = {}) {
  return {
    id: 42,
    requester: person(users.employee.id, users.employee.name),
    application: { id: 1, name: 'AWS Console' },
    access_level: { id: 3, name: 'PowerUser' },
    status: 'REJECTED',
    current_step: 2,
    total_steps: 3,
    duration_days: 30,
    expires_at: null,
    created_at: now,
    updated_at: now,
    justification: 'Investigating production incidents.',
    steps: [
      { step_order: 1, approver_type: 'MANAGER', sla_hours: 24 },
      { step_order: 2, approver_type: 'APP_OWNER', sla_hours: 24 },
      { step_order: 3, approver_type: 'SPECIFIC_USER', sla_hours: 8 },
    ],
    approvals: [
      {
        id: 1,
        step_order: 1,
        approver: person(3, 'Morgan Manager'),
        decision: 'APPROVED',
        comment: 'Fine by me',
        due_at: now,
        decided_at: now,
        escalated: false,
        escalated_from: null,
        is_overdue: false,
        created_at: now,
      },
      {
        id: 2,
        step_order: 2,
        approver: person(4, 'Owen Owner'),
        decision: 'REJECTED',
        comment: 'Use ReadOnly instead',
        due_at: now,
        decided_at: now,
        escalated: true,
        escalated_from: person(8, 'Old Owner'),
        is_overdue: false,
        created_at: now,
      },
    ],
    ...overrides,
  };
}

function renderDetail(data, user = users.employee) {
  requestsApi.getRequest.mockResolvedValue(data);
  return renderWithProviders(
    <Routes>
      <Route path="/requests/:requestId" element={<RequestDetailPage />} />
    </Routes>,
    { preloadedState: authState(user), route: `/requests/${data.id}` },
  );
}

describe('Request detail', () => {
  it('shows a vertical timeline of every step', async () => {
    renderDetail(request());
    await screen.findByRole('heading', { name: /AWS Console · PowerUser/ });

    const step1 = screen.getByTestId('timeline-step-1');
    expect(within(step1).getByText(/Morgan Manager/)).toBeInTheDocument();
    expect(within(step1).getByText('Approved')).toBeInTheDocument();
    expect(within(step1).getByText(/Fine by me/)).toBeInTheDocument();

    const step2 = screen.getByTestId('timeline-step-2');
    expect(within(step2).getByText('Rejected')).toBeInTheDocument();
    expect(within(step2).getByText('Escalated')).toBeInTheDocument();
    expect(within(step2).getByText(/escalated from Old Owner/)).toBeInTheDocument();

    const step3 = screen.getByTestId('timeline-step-3');
    expect(within(step3).getByText(/not needed/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel request' })).not.toBeInTheDocument();
  });

  it('lets the requester cancel a pending request', async () => {
    const pending = request({
      status: 'PENDING',
      current_step: 1,
      approvals: [{ ...request().approvals[0], decision: 'PENDING', comment: null, decided_at: null }],
    });
    requestsApi.cancelRequest.mockResolvedValue({
      ...pending,
      status: 'CANCELLED',
      approvals: [{ ...pending.approvals[0], decision: 'SKIPPED' }],
    });
    renderDetail(pending);

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel request' }));
    const dialog = screen.getByRole('dialog', { name: 'Cancel this request?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel request' }));

    expect(requestsApi.cancelRequest).toHaveBeenCalledWith(42);
    expect(await screen.findByText('Your request was cancelled.')).toBeInTheDocument();
    expect(screen.getAllByText('Cancelled').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Cancel request' })).not.toBeInTheDocument();
  });

  it('says so when the request does not exist or is not visible', async () => {
    requestsApi.getRequest.mockRejectedValue({
      response: { status: 404, data: { error: { code: 'NOT_FOUND', message: 'Access request not found' } } },
    });
    renderWithProviders(
      <Routes>
        <Route path="/requests/:requestId" element={<RequestDetailPage />} />
      </Routes>,
      { preloadedState: authState(users.employee), route: '/requests/999' },
    );
    expect(await screen.findByText('Request not found')).toBeInTheDocument();
  });
});
