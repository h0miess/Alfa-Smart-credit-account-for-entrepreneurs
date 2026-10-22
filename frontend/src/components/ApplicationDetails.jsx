import { useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, FileCheck2, ShieldCheck } from 'lucide-react';
import {
  offerTerms,
  statusGuidance,
  dateTime,
  money,
  monthlyPayment,
  products,
  transition,
  runChecks,
  statusLabels,
} from '../lib/credit';
import { Field, Status, Modal } from './UI';
import { DocumentUpload } from './Wizard';
export default function ApplicationDetails({
  application: a,
  onUpdate,
  onBack,
  mode,
  notify,
  canSign,
}) {
  const [signing, setSigning] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [comment, setComment] = useState('');
  const product = products.find((p) => p.id === a.productId);
  const terms = offerTerms(a);
  const amount = terms.amount;
  const payment = terms.monthly_payment;
  const [changedAmount, setChangedAmount] = useState(amount);
  const [changedMonths, setChangedMonths] = useState(terms.term_months);
  const [changedRate, setChangedRate] = useState(terms.annual_rate_pct);
  const [requested, setRequested] = useState('Финансовая отчётность за последний квартал');
  const documents = a.requested_documents?.length
    ? a.requested_documents
    : ['Финансовая отчётность за последний квартал'];
  const completeDocuments = documents.every((label) =>
    a.documents.some((d) => d.request === label),
  );

  const offerExpired = a.offer_expires_at && Date.parse(a.offer_expires_at) <= Date.now();
  const terminal = ['rejected', 'declined'].includes(a.status);
  const stages = [
    'submitted',
    'checking',
    'external',
    'scoring',
    'review',
    'offer',
    'accepted',
    'signed',
    'funded',
  ];
  const position = a.status === 'info' ? 4 : stages.indexOf(a.status);
  const advance = (status, note) =>
    onUpdate(
      transition(
        mode === 'bank' ? { ...a, reasons: [{ label: note }] } : a,
        status,
        note,
        mode === 'bank' ? 'Андеррайтер' : 'Клиент',
      ),
    );
  return (
    <>
      <button className="text-button back-link" onClick={onBack}>
        <ArrowLeft size={16} />
        Все заявки
      </button>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ЗАЯВКА № {a.number}</div>
          <h1>{product.short}</h1>
          <p>
            {a.name} · {money(a.amount)} · {a.months} мес.
          </p>
        </div>
        <Status status={a.status} />
      </div>
      <div className="info-box status-banner">
        <strong>{statusLabels[a.status]}</strong>
        <p>{statusGuidance[a.status]?.[0]}</p>
        <span>{statusGuidance[a.status]?.[1]}</span>
      </div>
      <div className="detail-layout">
        <div>
          <section className="card detail-card">
            <h2>
              {a.status === 'funded'
                ? 'Средства предоставлены'
                : a.status === 'offer'
                  ? 'Хорошие новости. Вам одобрено!'
                  : 'Всё о вашей заявке'}
            </h2>
            <p className="muted">{a.history.at(-1)?.note}</p>
            {a.status === 'submitted' && (
              <div className="info-box">
                <p>
                  В демо проверки запускаются кнопкой. Результаты и источники появятся в истории
                  заявки.
                </p>
                <Field label="Демонстрационный сценарий">
                  <select
                    value={a.scenario}
                    onChange={(e) => onUpdate({ ...a, scenario: e.target.value }, false)}
                  >
                    {[
                      ['auto', 'Автоматически по финансовым данным'],
                      ['changed', 'Одобрение с изменением суммы'],
                      ['info', 'Запрос дополнительных документов'],
                      ['review', 'Ручное рассмотрение'],
                      ['reject', 'Отказ'],
                    ].map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </Field>
                <button className="button primary" onClick={() => onUpdate(runChecks(a))}>
                  <ShieldCheck size={17} />
                  Запустить демо-проверки
                </button>
              </div>
            )}
            {['offer', 'accepted', 'signed', 'funded'].includes(a.status) && (
              <>
                <p>
                  {a.offer_expires_at
                    ? `Предложение действительно до ${dateTime(a.offer_expires_at)}`
                    : 'Демо-предложение: срок действия уточняется'}
                  {offerExpired && a.status === 'offer'
                    ? ' · Срок истёк, требуется новое предложение'
                    : ''}
                </p>
                <div className="offer-summary">
                  <div>
                    <span>Одобренная сумма</span>
                    <strong>{money(amount)}</strong>
                  </div>
                  <div>
                    <span>Ежемесячный платёж</span>
                    <strong>{money(payment)}</strong>
                  </div>
                  <div>
                    <span>Ставка / срок</span>
                    <strong>
                      {terms.annual_rate_pct}% / {terms.term_months} мес.
                    </strong>
                  </div>
                </div>
                {(amount !== Number(a.amount) ||
                  terms.term_months !== a.months ||
                  terms.annual_rate_pct !== product.rate) && (
                  <div className="info-box">
                    Встречное предложение: сумма {money(a.amount)} → {money(amount)}; срок{' '}
                    {a.months} → {terms.term_months} мес.; ставка предварительного расчёта{' '}
                    {product.rate}% → {terms.annual_rate_pct}%. Причины изменений указаны ниже.
                  </div>
                )}
                <details className="payment-schedule">
                  <summary>Предварительный график платежей</summary>
                  <table>
                    <thead>
                      <tr>
                        <th>Платёж</th>
                        <th>Сумма</th>
                        <th>Основной долг</th>
                        <th>Проценты</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Array.from({ length: terms.term_months }, (_, i) => {
                        const r = terms.annual_rate_pct / 1200;
                        const balance = r
                          ? amount * (1 + r) ** i - (payment * ((1 + r) ** i - 1)) / r
                          : amount - payment * i;
                        const interest = balance * r;
                        return (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            <td>{money(payment)}</td>
                            <td>{money(payment - interest)}</td>
                            <td>{money(interest)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </details>
                <p>
                  Демо-условия: комиссии — 0 ₽. Заявленный залог: {money(a.collateral_value || 0)}.
                  Первый платёж через месяц после выдачи. Расчёт иллюстративный.
                </p>
              </>
            )}
            {a.status === 'offer' && mode === 'client' && (
              <div className="form-actions">
                <button
                  className="button secondary"
                  onClick={() => advance('declined', 'Клиент отклонил предложение')}
                >
                  Отклонить
                </button>
                <button
                  className="button primary"
                  disabled={offerExpired}
                  onClick={() =>
                    onUpdate(
                      transition(
                        { ...a, offer: terms },
                        'accepted',
                        'Клиент принял условия предложения без изменений',
                        'Клиент',
                      ),
                    )
                  }
                >
                  Принять условия
                  <ArrowRight size={17} />
                </button>
              </div>
            )}
            {a.status === 'accepted' && mode === 'client' && (
              <div className="info-box">
                <p>
                  Договор сформирован на принятых условиях: {money(amount)}, {terms.term_months}{' '}
                  мес., {terms.annual_rate_pct}%.
                </p>
                {canSign ? (
                  <button className="button primary" onClick={() => setSigning(true)}>
                    Подписать договор
                  </button>
                ) : (
                  <p>
                    Подписание доступно руководителю. В демо: смените роль представителя на
                    «Генеральный директор» в профиле и вернитесь в эту заявку.
                  </p>
                )}
              </div>
            )}
            {a.status === 'signed' && mode === 'client' && (
              <button
                className="button primary"
                onClick={() =>
                  advance(
                    'funded',
                    'Демо-выдача завершена. Реального перевода средств не происходит.',
                  )
                }
              >
                Смоделировать выдачу
                <ArrowRight size={17} />
              </button>
            )}
            {a.status === 'funded' && (
              <div className="success-box">
                <CheckCircle2 size={22} />
                Готово! Демонстрационный кредит оформлен. Реальные деньги не переводились.
              </div>
            )}
            {a.status === 'info' && (
              <>
                <h3>Полный список запрошенных документов</h3>
                {documents.map((label) => (
                  <div key={label}>
                    <h3>{label}</h3>
                    <DocumentUpload
                      documents={a.documents.filter((d) => d.request === label)}
                      onChange={(files) =>
                        onUpdate(
                          {
                            ...a,
                            documents: [
                              ...a.documents.filter((d) => d.request !== label),
                              ...files.map((d) => ({ ...d, request: label })),
                            ],
                          },
                          false,
                        )
                      }
                    />
                  </div>
                ))}
                {mode === 'client' && (
                  <button
                    className="button primary"
                    disabled={!completeDocuments}
                    onClick={() => {
                      const next = transition(
                        a,
                        'checking',
                        'Клиент предоставил запрошенные документы',
                        'Клиент',
                      );
                      const external = transition(
                        next,
                        'external',
                        'Документы приняты; повторные mock-проверки завершены',
                      );
                      const scored = transition(external, 'scoring', 'Оценка обновлена');
                      onUpdate(
                        transition(
                          scored,
                          'review',
                          'Документы доступны менеджеру. Ожидается решение.',
                        ),
                      );
                    }}
                  >
                    Передать документы банку
                    <ArrowRight size={17} />
                  </button>
                )}
              </>
            )}
            {a.status === 'review' && mode === 'client' && (
              <div className="info-box">
                Заявку рассматривает кредитный менеджер. Для демонстрации переключитесь в рабочее
                место банка внизу боковой панели.
              </div>
            )}
            {mode === 'bank' && a.status === 'review' && (
              <div className="bank-actions">
                <Field label="Комментарий к решению">
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Обоснование решения или запрос данных"
                    required
                  />
                </Field>
                <Field label="Полный список документов (по одному на строку)">
                  <textarea value={requested} onChange={(e) => setRequested(e.target.value)} />
                </Field>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const offer = {
                      amount: Number(changedAmount),
                      term_months: Number(changedMonths),
                      annual_rate_pct: Number(changedRate),
                      monthly_payment: monthlyPayment(
                        Number(changedAmount),
                        Number(changedMonths),
                        Number(changedRate),
                      ),
                    };
                    onUpdate(
                      transition(
                        { ...a, offer, reasons: [{ label: comment }] },
                        'offer',
                        comment,
                        'Андеррайтер',
                      ),
                    );
                  }}
                >
                  <div className="form-grid">
                    <Field label="Предлагаемая сумма">
                      <input
                        type="number"
                        required
                        min={product.min}
                        max={product.max}
                        value={changedAmount}
                        onChange={(e) => setChangedAmount(e.target.value)}
                      />
                    </Field>
                    <Field label="Срок">
                      <input
                        type="number"
                        required
                        min={product.minMonths || 3}
                        max={product.months}
                        value={changedMonths}
                        onChange={(e) => setChangedMonths(e.target.value)}
                      />
                    </Field>
                    <Field label="Ставка, %">
                      <input
                        type="number"
                        required
                        min="0"
                        max="100"
                        step="0.01"
                        value={changedRate}
                        onChange={(e) => setChangedRate(e.target.value)}
                      />
                    </Field>
                  </div>
                  <button className="button secondary" disabled={!comment.trim()}>
                    Предложить изменённые условия
                  </button>
                </form>
                <div className="button-row">
                  <button
                    className="button primary"
                    disabled={!comment.trim()}
                    onClick={() => advance('offer', comment)}
                  >
                    Одобрить
                  </button>
                  <button
                    className="button secondary"
                    disabled={!comment.trim() || !requested.trim()}
                    onClick={() =>
                      onUpdate(
                        transition(
                          {
                            ...a,
                            requested_documents: requested
                              .split('\n')
                              .map((x) => x.trim())
                              .filter(Boolean),
                          },
                          'info',
                          comment,
                          'Андеррайтер',
                        ),
                      )
                    }
                  >
                    Запросить сведения
                  </button>
                  <button
                    className="button danger"
                    disabled={!comment.trim()}
                    onClick={() => advance('rejected', comment)}
                  >
                    Отказать
                  </button>
                </div>
              </div>
            )}
            {(a.reasons || a.risk_factors || a.positive_factors) && (
              <section>
                <h3>Почему принято такое решение</h3>
                {[
                  ['Причины', a.reasons],
                  ['Что требует внимания', a.risk_factors],
                  ['Сильные стороны', a.positive_factors],
                ].map(([title, items]) =>
                  items?.length ? (
                    <div key={title}>
                      <h3>{title}</h3>
                      <ul>
                        {items.map((item, i) => (
                          <li key={i}>{item.label || item.text || String(item)}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null,
                )}
              </section>
            )}
            {a.status === 'rejected' && (
              <div className="info-box">
                Что можно изменить: уменьшите сумму или увеличьте срок новой заявки, проверьте
                актуальность данных об оборотах и погасите задолженности. Это не гарантирует
                одобрение.
              </div>
            )}
            {terminal && (
              <div className="info-box">
                {a.status === 'rejected'
                  ? 'Решение демонстрационной модели. Можно создать новую заявку с другими параметрами.'
                  : 'Вы отклонили предложение. При необходимости создайте новую заявку.'}
              </div>
            )}
          </section>
          <section className="card detail-card">
            <h2>История заявки</h2>
            <ol className="timeline">
              {[...a.history].reverse().map((h, i) => (
                <li key={`${h.at}-${i}`}>
                  <span className="timeline-dot" />
                  <div>
                    <strong>{statusLabels[h.status]}</strong>
                    <p>{h.note}</p>
                    <small>
                      {dateTime(h.at)} · {h.actor}
                    </small>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
        <aside>
          <section className="card detail-card">
            <h3>Этапы оформления</h3>
            <ol className="stage-list">
              {stages.map((s, i) => (
                <li key={s} className={i <= position && !terminal ? 'complete' : ''}>
                  <span>{i < position && !terminal ? <CheckCircle2 size={17} /> : i + 1}</span>
                  {statusLabels[s]}
                </li>
              ))}
            </ol>
          </section>
          {mode === 'bank' && (
            <section className="card detail-card">
              <h3>Результаты проверок</h3>
              {a.checkedAt ? (
                <>
                  <p>
                    PD: {a.pd == null ? 'не получена от модели' : `${(a.pd * 100).toFixed(2)}%`} ·
                    Грейд: {a.grade || 'не получен'}
                  </p>
                  <div className="score-inline">
                    <ShieldCheck size={26} />
                    <strong>
                      {a.score}
                      <small> / 950</small>
                    </strong>
                  </div>
                  <p className="muted">
                    Скоринговая оценка. Итоговое решение учитывает сценарий и действия менеджера.
                  </p>
                  {a.checks.map((c) => (
                    <p className="check-line" key={c}>
                      <FileCheck2 size={17} />
                      {c}
                      <span>Mock</span>
                    </p>
                  ))}
                  <small className="muted">
                    Проверено {dateTime(a.checkedAt)}. Источники смоделированы, реальных запросов
                    нет.
                  </small>
                </>
              ) : (
                <p className="muted">Результаты появятся после запуска проверок.</p>
              )}
            </section>
          )}
          <section className="card detail-card">
            <h3>Данные клиента</h3>
            <dl className="review-list">
              <div>
                <dt>ИНН</dt>
                <dd>{a.inn}</dd>
              </div>
              <div>
                <dt>Выручка / мес.</dt>
                <dd>{money(a.revenue)}</dd>
              </div>
              <div>
                <dt>Платежи / мес.</dt>
                <dd>{money(a.debt)}</dd>
              </div>
              <div>
                <dt>Контакт</dt>
                <dd>{a.contact}</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
      {signing && (
        <Modal title="Подписание предложения" onClose={() => setSigning(false)}>
          <p className="muted">
            Это имитация подписи без SMS. Для подтверждения введите демо-код <strong>1234</strong>.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!canSign) {
                setError('Подписание доступно руководителю');
                return;
              }
              if (code !== '1234') {
                setError('Введите демо-код 1234');
                return;
              }
              advance('signed', 'Оферта принята и подписана демо-кодом');
              setSigning(false);
              notify('Документы подписаны. Можно перейти к демо-выдаче.');
            }}
          >
            <Field label="Код подтверждения">
              <input
                autoFocus
                inputMode="numeric"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                maxLength={4}
                autoComplete="off"
              />
            </Field>
            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}
            <button className="button primary wide" type="submit">
              Подписать
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
