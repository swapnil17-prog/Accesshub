import { render, screen, within } from '@testing-library/react';

import { diffValues } from './diff';
import JsonDiff from './JsonDiff';

describe('audit JSON diff', () => {
  it('classifies fields, changed first', () => {
    expect(diffValues({ status: 'PENDING', step: 1, gone: true }, { status: 'APPROVED', step: 1, comment: 'ok' })).toEqual([
      { key: 'status', before: 'PENDING', after: 'APPROVED', change: 'changed' },
      { key: 'comment', before: undefined, after: 'ok', change: 'added' },
      { key: 'gone', before: true, after: undefined, change: 'removed' },
      { key: 'step', before: 1, after: 1, change: 'same' },
    ]);
  });

  it('compares nested values by content', () => {
    const [row] = diffValues({ steps: [{ a: 1 }] }, { steps: [{ a: 1 }] });
    expect(row.change).toBe('same');
  });

  it('renders before and after per field', () => {
    render(<JsonDiff oldValue={{ approver_id: 3 }} newValue={{ approver_id: 1, reason: 'On leave' }} />);
    const approverRow = screen.getByRole('rowheader', { name: /approver_id/ }).closest('tr');
    expect(within(approverRow).getByText('3')).toBeInTheDocument();
    expect(within(approverRow).getByText('1')).toBeInTheDocument();
    expect(within(approverRow).getByText('Changed')).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: /reason/ })).toHaveTextContent('Added');
  });

  it('handles events without values', () => {
    render(<JsonDiff oldValue={null} newValue={null} />);
    expect(screen.getByText(/no values were recorded/i)).toBeInTheDocument();
  });
});
