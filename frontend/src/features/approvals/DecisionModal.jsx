import { useEffect, useState } from 'react';

import ConfirmModal from '../../components/ConfirmModal';
import { Field, Textarea } from '../../components/form';
import { describedBy } from '../../utils/forms';

/**
 * Approve or reject one or more approvals. Rejecting requires a comment (the requester sees
 * it); approving takes an optional one. ``onConfirm(comment)`` is called with the trimmed text.
 */
export default function DecisionModal({ open, mode, count = 1, subject, loading = false, onConfirm, onCancel }) {
  const [comment, setComment] = useState('');
  const [touched, setTouched] = useState(false);
  const isReject = mode === 'reject';

  useEffect(() => {
    if (open) {
      setComment('');
      setTouched(false);
    }
  }, [open, mode]);

  const missing = isReject && comment.trim() === '';
  const error = touched && missing ? 'A comment is required when rejecting.' : null;

  function confirm() {
    setTouched(true);
    if (missing) return;
    onConfirm(comment.trim());
  }

  const what = count > 1 ? `${count} requests` : 'this request';
  return (
    <ConfirmModal
      open={open}
      title={isReject ? `Reject ${what}?` : `Approve ${what}?`}
      message={subject}
      confirmLabel={isReject ? 'Reject' : count > 1 ? `Approve ${count}` : 'Approve'}
      tone={isReject ? 'danger' : 'primary'}
      loading={loading}
      onConfirm={confirm}
      onCancel={onCancel}
    >
      <Field
        id="decision-comment"
        label={isReject ? 'Reason for rejecting' : 'Comment'}
        optional={!isReject}
        error={error}
        hint={isReject ? 'Shared with the requester.' : undefined}
      >
        <Textarea
          id="decision-comment"
          rows={3}
          maxLength={2000}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          onBlur={() => setTouched(true)}
          error={error}
          placeholder={isReject ? 'e.g. Please use the shared read-only account instead.' : 'Optional note for the record'}
          {...describedBy('decision-comment', error, isReject)}
        />
      </Field>
    </ConfirmModal>
  );
}
