import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import * as applicationsApi from '../../api/applications';
import * as requestsApi from '../../api/requests';
import { authState, renderWithProviders, users } from '../../test/utils';
import NewRequestPage from './NewRequestPage';

vi.mock('../../api/applications');
vi.mock('../../api/requests');

const APPS = [
  {
    id: 1,
    name: 'GitHub',
    description: 'Source code hosting',
    owner: { id: 4, name: 'Owen Owner', email: 'owner@accesshub.dev' },
    is_active: true,
    access_levels: [
      { id: 11, name: 'Read' },
      { id: 12, name: 'Write' },
    ],
    workflow_steps: [
      { step_order: 1, approver_type: 'MANAGER', approver_user: null, sla_hours: 24 },
      { step_order: 2, approver_type: 'APP_OWNER', approver_user: null, sla_hours: 48 },
    ],
  },
  {
    id: 2,
    name: 'Workday',
    description: 'HR and payroll',
    owner: { id: 4, name: 'Owen Owner', email: 'owner@accesshub.dev' },
    is_active: true,
    access_levels: [{ id: 21, name: 'Employee Self-Service' }],
    workflow_steps: [{ step_order: 1, approver_type: 'SPECIFIC_USER', approver_user: { id: 9, name: 'Hana HR' }, sla_hours: 8 }],
  },
];

const JUSTIFICATION = 'I maintain the release pipeline this quarter.';

function renderPage() {
  applicationsApi.listApplications.mockResolvedValue({ items: APPS, page: 1, per_page: 100, total: 2 });
  return renderWithProviders(
    <Routes>
      <Route path="/requests/new" element={<NewRequestPage />} />
      <Route path="/requests/:id" element={<p>Detail page</p>} />
    </Routes>,
    { preloadedState: authState(users.employee), route: '/requests/new' },
  );
}

async function fillForm({ app = 'GitHub', level = 'Write', justification = JUSTIFICATION } = {}) {
  await userEvent.click(await screen.findByRole('radio', { name: new RegExp(app) }));
  await userEvent.selectOptions(screen.getByLabelText('Access level'), level);
  await userEvent.type(screen.getByLabelText('Business justification'), justification);
}

const submit = () => userEvent.click(screen.getByRole('button', { name: 'Submit request' }));

describe('New request', () => {
  it('searches applications and previews the approval chain', async () => {
    renderPage();
    await userEvent.type(await screen.findByRole('searchbox', { name: 'Search applications' }), 'payroll');
    expect(screen.queryByRole('radio', { name: /GitHub/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: /Workday/ }));

    const chain = screen.getByRole('list', { name: 'Approval chain' });
    expect(within(chain).getByText('Hana HR')).toBeInTheDocument();
    expect(within(chain).getByText(/responds within 8h/)).toBeInTheDocument();
  });

  it('validates on the client before calling the API', async () => {
    renderPage();
    await screen.findByRole('radio', { name: /GitHub/ });
    await submit();
    expect(screen.getByText('Choose an application.')).toBeInTheDocument();
    expect(screen.getByText('Choose an access level.')).toBeInTheDocument();
    expect(screen.getByText('Please explain in at least 20 characters.')).toBeInTheDocument();
    expect(requestsApi.createRequest).not.toHaveBeenCalled();
  });

  it('submits and opens the new request', async () => {
    requestsApi.createRequest.mockResolvedValue({ id: 77, approvals: [{ approver: { name: 'Morgan Manager' } }] });
    renderPage();
    await fillForm();
    await userEvent.selectOptions(screen.getByLabelText(/duration/i), '90');
    await submit();

    expect(requestsApi.createRequest).toHaveBeenCalledWith({
      application_id: 1,
      access_level_id: 12,
      justification: JUSTIFICATION,
      duration_days: 90,
    });
    expect(await screen.findByText('Detail page')).toBeInTheDocument();
  });

  it('shows API validation errors inline next to the field', async () => {
    requestsApi.createRequest.mockRejectedValue({
      response: {
        status: 422,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Invalid input',
            details: { justification: ['Must be at least 20 characters.'], duration_days: ['Must be <= 365.'] },
          },
        },
      },
    });
    renderPage();
    await fillForm();
    await submit();

    expect(await screen.findByText('Must be at least 20 characters.')).toBeInTheDocument();
    expect(screen.getByLabelText('Business justification')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('Must be <= 365.')).toBeInTheDocument();
  });

  it('explains a duplicate pending request', async () => {
    requestsApi.createRequest.mockRejectedValue({
      response: {
        status: 409,
        data: {
          error: {
            code: 'DUPLICATE_REQUEST',
            message: 'You already have a pending request for this application and access level',
          },
        },
      },
    });
    renderPage();
    await fillForm();
    await submit();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Already requested');
    expect(within(alert).getByRole('link', { name: /pending requests/i })).toHaveAttribute('href', '/requests?status=PENDING');
  });

  it('validates a custom duration', async () => {
    renderPage();
    await fillForm();
    await userEvent.selectOptions(screen.getByLabelText(/duration/i), 'custom');
    await userEvent.type(screen.getByLabelText('Number of days'), '500');
    await submit();
    expect(screen.getByText('Enter a whole number from 1 to 365.')).toBeInTheDocument();
    expect(requestsApi.createRequest).not.toHaveBeenCalled();
  });
});
