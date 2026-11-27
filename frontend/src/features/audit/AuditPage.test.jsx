import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import * as auditApi from '../../api/audit';
import { authState, renderWithProviders, users } from '../../test/utils';
import { saveBlob } from '../../utils/download';
import AuditPage from './AuditPage';

vi.mock('../../api/audit');
vi.mock('../../utils/download');

const ROW = {
  id: 7,
  created_at: '2026-11-20T10:00:00Z',
  actor: { id: 2, name: 'Avery Auditor', email: 'auditor@accesshub.dev' },
  action: 'WORKFLOW_UPDATED',
  entity_type: 'application',
  entity_id: 4,
  old_value: { steps: 1 },
  new_value: { steps: 2 },
  ip_address: '10.0.0.1',
  user_agent: 'pytest',
};

beforeEach(() => {
  auditApi.listAuditLogs.mockResolvedValue({ items: [ROW], page: 1, per_page: 25, total: 1 });
});

describe('Audit log export', () => {
  it('downloads the CSV for the current filters', async () => {
    const blob = new Blob(['id,action\n7,WORKFLOW_UPDATED\n'], { type: 'text/csv' });
    auditApi.exportAuditCsv.mockResolvedValue({ blob, filename: 'audit-20261120-100000.csv' });
    renderWithProviders(<AuditPage />, { preloadedState: authState(users.auditor) });
    await screen.findByText('WORKFLOW_UPDATED');

    await userEvent.selectOptions(screen.getByLabelText('Action'), 'WORKFLOW_UPDATED');
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));

    expect(auditApi.exportAuditCsv).toHaveBeenCalledWith(expect.objectContaining({ action: 'WORKFLOW_UPDATED' }));
    expect(saveBlob).toHaveBeenCalledWith(blob, 'audit-20261120-100000.csv');
    expect(await screen.findByText('Downloaded audit-20261120-100000.csv.')).toBeInTheDocument();
  });

  it('reports a failed export', async () => {
    auditApi.exportAuditCsv.mockRejectedValue({
      response: { status: 403, data: { error: { code: 'FORBIDDEN', message: 'You do not have permission' } } },
    });
    renderWithProviders(<AuditPage />, { preloadedState: authState(users.auditor) });
    await screen.findByText('WORKFLOW_UPDATED');
    await userEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('You do not have permission');
    expect(saveBlob).not.toHaveBeenCalled();
  });

  it('expands a row to show the field diff', async () => {
    renderWithProviders(<AuditPage />, { preloadedState: authState(users.auditor) });
    await userEvent.click(await screen.findByRole('button', { name: 'Show changes for event 7' }));
    expect(screen.getByRole('table', { name: 'Changes recorded in this event' })).toHaveTextContent(/steps.*1.*2/);
  });
});
