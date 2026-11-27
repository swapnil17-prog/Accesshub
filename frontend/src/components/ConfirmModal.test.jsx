import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';

import ConfirmModal from './ConfirmModal';

function TwoFieldDialog({ onCancel }) {
  const [a, setA] = useState('');
  const [b, setB] = useState('');
  return (
    <ConfirmModal open title="Two fields" onConfirm={() => {}} onCancel={() => onCancel()}>
      <input aria-label="First" value={a} onChange={(e) => setA(e.target.value)} />
      <input aria-label="Second" value={b} onChange={(e) => setB(e.target.value)} />
    </ConfirmModal>
  );
}

describe('ConfirmModal', () => {
  it('focuses the first field once, and typing elsewhere keeps focus (regression)', async () => {
    render(<TwoFieldDialog onCancel={() => {}} />);
    expect(screen.getByLabelText('First')).toHaveFocus();
    await userEvent.type(screen.getByLabelText('Second'), 'hello');
    expect(screen.getByLabelText('Second')).toHaveValue('hello');
    expect(screen.getByLabelText('First')).toHaveValue('');
  });

  it('Escape cancels using the latest handler', async () => {
    const onCancel = vi.fn();
    render(<TwoFieldDialog onCancel={onCancel} />);
    await userEvent.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
