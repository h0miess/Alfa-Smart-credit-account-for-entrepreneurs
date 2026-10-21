import { useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, FileCheck2, ShieldCheck } from 'lucide-react';
import {
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
export default function ApplicationDetails({ application: a, onUpdate, onBack, mode, notify }) {
  const [signing, setSigning] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [comment, setComment] = useState('');
  const product = products.find((p) => p.id === a.productId);
  const amount = a.approvedAmount || a.amount;
  const payment = monthlyPayment(amount, a.months, product.rate);
  const terminal = ['rejected', 'declined'].includes(a.status);
  const stages = [
    'submitted',
    'checking',
    'external',
    'scoring',
    'review',
    'offer',
    'signed',
    'funded',
  ];
  const position = a.status === 'info' ? 4 : stages.indexOf(a.status);
  const advance = (status, note) =>
    onUpdate(transition(a, status, note, mode === 'bank' ? 'Кредитный менеджер' : 'Клиент'));
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
            {['offer', 'signed', 'funded'].includes(a.status) && (
              <>
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
                      {product.rate}% / {a.months} мес.
                    </strong>
                  </div>
                </div>
                {amount !== Number(a.amount) && (
                  <div className="info-box">
                    Сумма изменена: запрошено {money(a.amount)}, одобрено {money(amount)}.
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
                      {Array.from({ length: a.months }, (_, i) => {
                        const r = product.rate / 1200;
                        const balance = amount * (1 + r) ** i - (payment * ((1 + r) ** i - 1)) / r;
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
                <p className="muted">
                  Демо-условия: без залога и комиссий. Первый платёж через месяц после выдачи.
                  Расчёт иллюстративный.
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
                <button className="button primary" onClick={() => setSigning(true)}>
                  Принять и подписать
                  <ArrowRight size={17} />
                </button>
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
                <DocumentUpload
                  documents={a.documents}
                  onChange={(documents) => onUpdate({ ...a, documents }, false)}
                />
                {mode === 'client' && (
                  <button
                    className="button primary"
                    disabled={!a.documents.length}
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
                    disabled={!comment.trim()}
                    onClick={() => advance('info', comment)}
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
          <section className="card detail-card">
            <h3>Результаты проверок</h3>
            {a.checkedAt ? (
              <>
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
                  Проверено {dateTime(a.checkedAt)}. Источники смоделированы, реальных запросов нет.
                </small>
              </>
            ) : (
              <p className="muted">Результаты появятся после запуска проверок.</p>
            )}
          </section>
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
