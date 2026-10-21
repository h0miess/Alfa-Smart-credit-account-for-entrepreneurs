import test from 'node:test';
import assert from 'node:assert/strict';
import {
  defaultCompany,
  initialState,
  monthlyPayment,
  newDraft,
  runChecks,
  scoreApplication,
  transition,
} from './credit.js';
import { createId } from './id.js';
import { webcrypto } from 'node:crypto';
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const submitted = (scenario = 'auto') =>
  transition({ ...newDraft(defaultCompany), scenario }, 'submitted', 'Отправлена');
test('disallows signing a draft and changing a funded application', () => {
  assert.throws(() => transition(newDraft(defaultCompany), 'signed'));
  const approved = runChecks(submitted());
  const funded = transition(transition(approved, 'signed'), 'funded');
  assert.throws(() => transition(funded, 'offer'));
});
test('records checks, score and approval independently', () => {
  const a = runChecks(submitted());
  assert.equal(a.status, 'offer');
  assert.equal(a.score, scoreApplication(a));
  assert.equal(a.checks.length, 3);
  assert.deepEqual(
    a.history.slice(1).map((h) => h.status),
    ['submitted', 'checking', 'external', 'scoring', 'offer'],
  );
});
test('supports modified terms, document request, review and refusal', () => {
  const changed = runChecks(submitted('changed'));
  assert.equal(changed.approvedAmount, changed.amount * 0.8);
  assert.equal(changed.status, 'offer');
  assert.equal(runChecks(submitted('info')).status, 'info');
  assert.equal(runChecks(submitted('review')).status, 'review');
  assert.equal(runChecks(submitted('reject')).status, 'rejected');
});
test('high debt leads to refusal in automatic mode', () => {
  const a = submitted();
  assert.equal(runChecks({ ...a, revenue: 10000, debt: 100000 }).status, 'rejected');
});
test('calculates an annuity payment, including zero interest', () => {
  assert.equal(monthlyPayment(120000, 12, 0), 10000);
  assert.ok(Math.abs(monthlyPayment(1500000, 24, 24) - 79306.65) < 1);
});

test('initializes the dashboard and generates UUIDs over HTTP without randomUUID', () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) },
  });
  try {
    const state = initialState();
    assert.equal(state.applications[0].status, 'offer');
    const ids = [state.applications[0].id, state.notifications[0].id];
    for (let i = 0; i < 100; i++) ids.push(createId());
    for (const id of ids) {
      assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    }
    assert.equal(new Set(ids).size, ids.length);
  } finally {
    Object.defineProperty(globalThis, 'crypto', original);
  }
});
