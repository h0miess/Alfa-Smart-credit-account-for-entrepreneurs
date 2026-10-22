import { createId } from '../lib/id.js';
import { useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Save, UploadCloud } from 'lucide-react';
import { money, monthlyPayment, products, transition } from '../lib/credit';
import { Field } from './UI';
const steps = ['Цель', 'Условия', 'Компания', 'Финансы', 'Контакты', 'Проверка'];
export function DocumentUpload({ documents, onChange }) {
  const [error, setError] = useState('');
  return (
    <div>
      <label className="upload-zone">
        <UploadCloud size={28} />
        <strong>Добавьте документы</strong>
        <span>PDF, JPG, PNG · до 10 МБ · сохраняем только название</span>
        <input
          aria-label="Загрузить документы"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          multiple
          onChange={(e) => {
            const files = Array.from(e.target.files);
            if (
              files.some((f) => f.size > 10 * 1024 * 1024 || !/\.(pdf|jpe?g|png)$/i.test(f.name))
            ) {
              setError('Выберите PDF, JPG или PNG размером до 10 МБ.');
              e.target.value = '';
              return;
            }
            onChange([
              ...documents,
              ...files.map((f) => ({ id: createId(), name: f.name, size: f.size })),
            ]);
            setError('');
            e.target.value = '';
          }}
        />
      </label>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <div className="document-list">
        {documents.map((d) => (
          <div key={d.id}>
            <CheckCircle2 size={17} />
            <span>
              {d.name}
              <small>Демо-загрузка · содержимое не передаётся</small>
            </span>
            <button
              className="text-button"
              type="button"
              aria-label={`Удалить ${d.name}`}
              onClick={() => onChange(documents.filter((x) => x.id !== d.id))}
            >
              Удалить
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
export default function Wizard({ application, onSave, onSubmit, onBack, notify }) {
  const [draft, setDraft] = useState(application);
  const [confirmed, setConfirmed] = useState(false);
  const product = products.find((p) => p.id === draft.productId);
  const update = (patch) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    onSave(next);
  };
  const goals = [
    ['working', 'Пополнить оборотку'],
    ['invest', 'Купить оборудование'],
    ['overdraft', 'Запас на счёте'],
  ];
  return (
    <>
      <button className="text-button back-link" onClick={onBack}>
        ← Все заявки
      </button>
      <div className="page-heading">
        <div>
          <h1>Деньги для вашего дела</h1>
          <p>Компания и финансовые данные уже заполнены из профиля банка.</p>
        </div>
      </div>
      <div className="wizard-layout">
        <form
          className="card wizard-form"
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit(
              transition(
                { ...draft, consent_at: new Date().toISOString() },
                'submitted',
                'Согласия на обработку данных и запрос БКИ получены',
                'Клиент',
              ),
            );
          }}
        >
          <h2>Какая у вас задача?</h2>
          <Field label="Цель финансирования">
            <select
              value={draft.productId}
              onChange={(e) => {
                const p = products.find((p) => p.id === e.target.value);
                update({
                  productId: p.id,
                  purpose: goals.find((g) => g[0] === p.id)[1],
                  amount: Math.min(Math.max(draft.amount, p.min), p.max),
                  months: Math.max(p.minMonths || 3, Math.min(draft.months, p.months)),
                });
              }}
            >
              {goals.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <div className="form-grid">
            <Field label="Сумма, ₽" hint={`От ${money(product.min)} до ${money(product.max)}`}>
              <input
                type="number"
                required
                min={product.min}
                max={product.max}
                value={draft.amount}
                onChange={(e) => update({ amount: e.target.value })}
              />
            </Field>
            <Field label="Срок, месяцев">
              <input
                type="number"
                required
                min={product.minMonths || 3}
                max={product.months}
                value={draft.months}
                onChange={(e) => update({ months: Number(e.target.value) })}
              />
            </Field>
          </div>
          <Field label="Заявленная стоимость залога, ₽" hint="Укажите 0, если залога нет">
            <input
              type="number"
              required
              min="0"
              value={draft.collateral_value ?? 0}
              onChange={(e) => update({ collateral_value: Number(e.target.value) })}
            />
          </Field>
          <h3>Данные из профиля</h3>
          <dl className="review-list">
            <div>
              <dt>Компания / ИНН</dt>
              <dd>
                {draft.name} / {draft.inn}
              </dd>
            </div>
            <div>
              <dt>Представитель</dt>
              <dd>
                {draft.contact} · {draft.role}
              </dd>
            </div>
            <div>
              <dt>Средняя выручка в месяц</dt>
              <dd>{money(draft.revenue)}</dd>
            </div>
          </dl>
          <p className="muted">
            Если сведения изменились, обновите профиль до создания новой заявки. Финансовые данные в
            прототипе синтетические.
          </p>
          <label className="checkbox-label">
            <input
              required
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            <span>
              Подтверждаю данные и даю согласие на обработку данных и запрос кредитной истории в БКИ
              (демонстрация).
            </span>
          </label>
          <div className="form-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                onSave(draft);
                notify('Черновик сохранён');
                onBack();
              }}
            >
              Сохранить черновик
            </button>
            <button className="button primary">Отправить заявку</button>
          </div>
        </form>
        <aside className="card calculator">
          <h3>{product.name}</h3>
          <div className="calc-item">
            <span>Примерный платёж</span>
            <strong>
              {money(monthlyPayment(Number(draft.amount), Number(draft.months) || 1, product.rate))}{' '}
              / мес.
            </strong>
          </div>
          <p>Ставка для расчёта: {product.rate}% годовых</p>
          <p>Окончательные условия и объяснение решения появятся в предложении.</p>
        </aside>
      </div>
    </>
  );
}
