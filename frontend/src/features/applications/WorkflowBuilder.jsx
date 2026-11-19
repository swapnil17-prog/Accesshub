import { useEffect, useRef, useState } from 'react';

import Button from '../../components/Button';
import { ErrorAlert, Select, TextInput } from '../../components/form';
import { ChevronDownIcon, ChevronUpIcon, PlusIcon, XIcon } from '../../components/icons';
import UserPicker from '../../components/UserPicker';
import { APPROVER_TYPE_LABELS } from '../../utils/format';
import {
  APPROVER_TYPES,
  errorsFromApi,
  hasErrors,
  MAX_STEPS,
  moveStep,
  newStep,
  sameSteps,
  SLA_MAX,
  SLA_MIN,
  toEditable,
  toPayload,
  validateSteps,
} from './workflowModel';

const NO_ERRORS = { global: null, byIndex: {} };

function DragHandle() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden="true">
      {[5, 10, 15].flatMap((y) => [<circle key={`a${y}`} cx="7" cy={y} r="1.4" />, <circle key={`b${y}`} cx="13" cy={y} r="1.4" />])}
    </svg>
  );
}

/**
 * Edit an application's ordered approval steps: add, remove, reorder (drag or arrows),
 * choose the approver type (and user for SPECIFIC_USER) and the SLA. ``onSave(payload)``
 * must resolve to ``{ ok: true }`` or ``{ ok: false, error }`` (the API error).
 */
export default function WorkflowBuilder({ steps: savedSteps, onSave, saving = false, readOnly = false }) {
  const [steps, setSteps] = useState(() => toEditable(savedSteps));
  const [errors, setErrors] = useState(NO_ERRORS);
  const dragFrom = useRef(null);
  const [dragOver, setDragOver] = useState(null);

  // Reset when the saved workflow changes (e.g. after a successful save or reload).
  const savedKey = JSON.stringify(savedSteps);
  useEffect(() => {
    setSteps(toEditable(savedSteps));
    setErrors(NO_ERRORS);
    // savedKey stands for savedSteps' content
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedKey]);

  const dirty = !sameSteps(steps, toEditable(savedSteps));

  function update(index, patch) {
    setSteps((current) => current.map((step, i) => (i === index ? { ...step, ...patch } : step)));
    setErrors((current) => {
      const byIndex = { ...current.byIndex };
      delete byIndex[index];
      return { ...current, byIndex };
    });
  }

  function move(from, to) {
    setSteps((current) => moveStep(current, from, to));
    setErrors(NO_ERRORS);
  }

  async function save() {
    const found = validateSteps(steps);
    setErrors(found);
    if (hasErrors(found)) return;
    const result = await onSave(toPayload(steps));
    if (!result.ok) setErrors(errorsFromApi(result.error));
  }

  return (
    <div>
      {errors.global ? (
        <div className="mb-4">
          <ErrorAlert>{errors.global}</ErrorAlert>
        </div>
      ) : null}

      {steps.length === 0 ? (
        <p className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          No approval steps yet. Requests can&apos;t be submitted until there is at least one.
        </p>
      ) : (
        <ol className="space-y-3" aria-label="Workflow steps">
          {steps.map((step, index) => {
            const stepErrors = errors.byIndex[index] ?? {};
            const label = `Step ${index + 1}`;
            return (
              <li
                key={step.key}
                draggable={!readOnly}
                onDragStart={(e) => {
                  dragFrom.current = index;
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(index);
                }}
                onDragLeave={() => setDragOver(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragFrom.current !== null) move(dragFrom.current, index);
                  dragFrom.current = null;
                  setDragOver(null);
                }}
                onDragEnd={() => setDragOver(null)}
                className={`rounded-lg bg-white p-4 ring-1 transition ${dragOver === index ? 'ring-2 ring-indigo-400' : 'ring-slate-200'}`}
                aria-label={label}
              >
                <div className="flex flex-wrap items-start gap-3">
                  <div className="flex items-center gap-2 pt-1.5">
                    {readOnly ? null : (
                      <span className="cursor-grab text-slate-400" title="Drag to reorder">
                        <DragHandle />
                      </span>
                    )}
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700 ring-1 ring-indigo-200">
                      {index + 1}
                    </span>
                  </div>

                  <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-[minmax(0,12rem)_minmax(0,1fr)_7rem]">
                    <div>
                      <label htmlFor={`${step.key}-type`} className="block text-xs font-medium text-slate-600">
                        Approver
                      </label>
                      <Select
                        id={`${step.key}-type`}
                        value={step.approver_type}
                        disabled={readOnly}
                        onChange={(e) => update(index, { approver_type: e.target.value, approver_user: null })}
                        className="mt-1"
                      >
                        {APPROVER_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {APPROVER_TYPE_LABELS[type]}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      {step.approver_type === 'SPECIFIC_USER' ? (
                        <>
                          <label htmlFor={`${step.key}-user`} className="block text-xs font-medium text-slate-600">
                            Person
                          </label>
                          <div className="mt-1">
                            <UserPicker
                              id={`${step.key}-user`}
                              value={step.approver_user}
                              disabled={readOnly}
                              onChange={(user) => update(index, { approver_user: user })}
                              error={stepErrors.approver_user_id}
                            />
                          </div>
                          {stepErrors.approver_user_id ? (
                            <p className="mt-1 text-xs text-rose-600">{stepErrors.approver_user_id}</p>
                          ) : null}
                        </>
                      ) : (
                        <p className="pt-6 text-xs text-slate-500">
                          {step.approver_type === 'MANAGER'
                            ? "The requester's manager (an admin if they have none)."
                            : "This application's owner."}
                        </p>
                      )}
                    </div>
                    <div>
                      <label htmlFor={`${step.key}-sla`} className="block text-xs font-medium text-slate-600">
                        SLA (hours)
                      </label>
                      <TextInput
                        id={`${step.key}-sla`}
                        type="number"
                        min={SLA_MIN}
                        max={SLA_MAX}
                        value={step.sla_hours}
                        disabled={readOnly}
                        onChange={(e) => update(index, { sla_hours: e.target.value })}
                        error={stepErrors.sla_hours}
                        aria-invalid={stepErrors.sla_hours ? true : undefined}
                        className="mt-1"
                      />
                      {stepErrors.sla_hours ? <p className="mt-1 text-xs text-rose-600">{stepErrors.sla_hours}</p> : null}
                    </div>
                  </div>

                  {readOnly ? null : (
                    <div className="flex items-center gap-1 pt-5">
                      <button
                        type="button"
                        onClick={() => move(index, index - 1)}
                        disabled={index === 0}
                        className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30"
                        aria-label={`Move ${label} up`}
                      >
                        <ChevronUpIcon className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => move(index, index + 1)}
                        disabled={index === steps.length - 1}
                        className="rounded p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30"
                        aria-label={`Move ${label} down`}
                      >
                        <ChevronDownIcon className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setSteps((current) => current.filter((_, i) => i !== index));
                          setErrors(NO_ERRORS);
                        }}
                        className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-600"
                        aria-label={`Remove ${label}`}
                      >
                        <XIcon className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {readOnly ? null : (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Button
            variant="secondary"
            onClick={() => setSteps((current) => [...current, newStep()])}
            disabled={steps.length >= MAX_STEPS}
          >
            <PlusIcon className="h-4 w-4" />
            Add step
          </Button>
          <div className="flex items-center gap-2">
            {dirty ? <span className="text-xs text-amber-700">Unsaved changes</span> : null}
            <Button
              variant="ghost"
              onClick={() => {
                setSteps(toEditable(savedSteps));
                setErrors(NO_ERRORS);
              }}
              disabled={!dirty || saving}
            >
              Reset
            </Button>
            <Button onClick={save} loading={saving} disabled={!dirty}>
              Save workflow
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
