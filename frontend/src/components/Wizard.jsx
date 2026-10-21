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
  const [consent, setConsent] = useState(false);
  const form = useRef(null);
  const step = draft.step || 0;
  const product = products.find((p) => p.id === draft.productId);
  const update = (values) => {
    const next = { ...draft, ...values };
    setDraft(next);
    onSave(next);
  };
  const input = (key, options = {}) => (
    <input
      {...options}
      value={draft[key] ?? ''}
      onChange={(e) =>
        update({
          [key]:
            options.type === 'number'
              ? e.target.value === ''
                ? ''
                : Number(e.target.value)
              : e.target.value,
        })
      }
    />
  );
  const nextStep = (e) => {
    e.preventDefault();
    if (step < 5) update({ step: step + 1 });
    else onSubmit(transition(draft, 'submitted', 'Заявка отправлена на проверку', 'Клиент'));
  };
  return (
    <>
      <button className="text-button back-link" onClick={onBack}>
        <ArrowLeft size={16} />К заявкам
      </button>
      <div className="page-heading">
        <div>
          <div className="eyebrow">№ {draft.number} · ЧЕРНОВИК</div>
          <h1>Финансирование вашего бизнеса</h1>
          <p>Несколько шагов — и мы подберём решение.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => {
            onSave(draft);
            notify('Черновик сохранён в этом браузере');
          }}
        >
          <Save size={17} />
          Сохранить и продолжить позже
        </button>
      </div>
      <div className="wizard-steps">
        {steps.map((s, i) => (
          <div key={s} className={i === step ? 'current' : i < step ? 'done' : ''}>
            <span>{i < step ? <Check size={15} /> : i + 1}</span>
            <strong>{s}</strong>
          </div>
        ))}
      </div>
      <div className="wizard-layout">
        <form className="card wizard-form" ref={form} onSubmit={nextStep}>
          <div className="eyebrow">ШАГ {step + 1} ИЗ 6</div>
          <h2>
            {
              [
                'Для чего нужны деньги?',
                'Выберите комфортные условия',
                'Расскажите о компании',
                'Финансовые показатели',
                'Кто будет на связи?',
                'Проверьте вашу заявку',
              ][step]
            }
          </h2>
          <p className="muted">
            {
              [
                'Подберём финансирование под вашу задачу.',
                'Платёж предварительный. Итоговые условия будут в предложении.',
                'Данные уже заполнены из вашего профиля.',
                'Укажите средние показатели за последние три месяца.',
                'Все изменения статуса появятся прямо в кабинете.',
                'После отправки заявку увидит сотрудник банка.',
              ][step]
            }
          </p>
          {step === 0 && (
            <>
              <Field label="Кредитный продукт">
                <select
                  value={draft.productId}
                  onChange={(e) =>
                    update({
                      productId: e.target.value,
                      amount: Math.min(
                        Math.max(
                          Number(draft.amount),
                          products.find((p) => p.id === e.target.value).min,
                        ),
                        products.find((p) => p.id === e.target.value).max,
                      ),
                      months: Math.min(
                        draft.months,
                        products.find((p) => p.id === e.target.value).months,
                      ),
                    })
                  }
                >
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Цель финансирования">
                <select value={draft.purpose} onChange={(e) => update({ purpose: e.target.value })}>
                  {[
                    'Пополнение оборотных средств',
                    'Покупка оборудования',
                    'Открытие новой точки',
                    'Покрытие кассового разрыва',
                  ].map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </Field>
              <div className="info-box">
                Без залога для демо-сценария. Все условия в прототипе приведены для примера.
              </div>
            </>
          )}
          {step === 1 && (
            <>
              <Field
                label="Сумма кредита, ₽"
                hint={`От ${money(product.min)} до ${money(product.max)}`}
              >
                {input('amount', {
                  type: 'number',
                  min: product.min,
                  max: product.max,
                  required: true,
                  step: 1000,
                })}
              </Field>
              <input
                className="amount-range"
                aria-label="Сумма кредита"
                type="range"
                min={product.min}
                max={product.max}
                step={10000}
                value={draft.amount}
                onChange={(e) => update({ amount: Number(e.target.value) })}
              />
              <Field label="Срок, месяцев" hint={`От 3 до ${product.months} месяцев`}>
                {input('months', { type: 'number', min: 3, max: product.months, required: true })}
              </Field>
            </>
          )}
          {step === 2 && (
            <div className="form-grid">
              <Field label="Название компании">
                {input('name', { required: true, maxLength: 150 })}
              </Field>
              <Field label="ИНН">
                {input('inn', {
                  required: true,
                  pattern: '[0-9]{10}|[0-9]{12}',
                  title: '10 или 12 цифр',
                  inputMode: 'numeric',
                })}
              </Field>
              <Field label="ОГРН / ОГРНИП">
                {input('ogrn', {
                  required: true,
                  pattern: '[0-9]{13}|[0-9]{15}',
                  title: '13 или 15 цифр',
                  inputMode: 'numeric',
                })}
              </Field>
              <Field label="ОКВЭД">
                {input('okved', {
                  required: true,
                  pattern: '[0-9]{2}(\\.[0-9]{1,2}){0,2}',
                  title: 'Например, 47.91',
                })}
              </Field>
              <Field label="Юридический адрес">
                {input('address', { required: true, maxLength: 300 })}
              </Field>
            </div>
          )}
          {step === 3 && (
            <>
              <div className="form-grid">
                <Field label="Среднемесячная выручка, ₽">
                  {input('revenue', { type: 'number', required: true, min: 1, max: 10000000000 })}
                </Field>
                <Field label="Ежемесячные платежи по кредитам, ₽">
                  {input('debt', { type: 'number', required: true, min: 0, max: 10000000000 })}
                </Field>
              </div>
              <h3>Документы компании</h3>
              <p className="muted">
                Можно добавить сейчас или по запросу банка. Для демо документы необязательны.
              </p>
              <DocumentUpload
                documents={draft.documents}
                onChange={(documents) => update({ documents })}
              />
            </>
          )}
          {step === 4 && (
            <>
              <Field label="ФИО контактного лица">
                {input('contact', { required: true, minLength: 3, maxLength: 150 })}
              </Field>
              <Field label="Электронная почта">
                {input('email', { type: 'email', required: true, maxLength: 150 })}
              </Field>
              <Field label="Ваша роль">
                <select value={draft.role} onChange={(e) => update({ role: e.target.value })}>
                  {[
                    'Собственник бизнеса',
                    'Генеральный директор',
                    'Финансовый директор',
                    'Бухгалтер',
                    'Уполномоченный сотрудник',
                  ].map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </Field>
              <div className="info-box">
                Email нужен только для профиля. Подписание и уведомления доступны внутри кабинета.
              </div>
            </>
          )}
          {step === 5 && (
            <>
              <dl className="review-list">
                {[
                  ['Продукт', product.name],
                  ['Цель', draft.purpose],
                  ['Компания', draft.name],
                  ['ИНН', draft.inn],
                  ['Сумма', money(draft.amount)],
                  ['Срок', `${draft.months} месяцев`],
                  ['Выручка / месяц', money(draft.revenue)],
                  ['Платежи по кредитам / месяц', money(draft.debt)],
                  ['Контакт', `${draft.contact} · ${draft.email}`],
                  ['Документы', `${draft.documents.length} шт.`],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  required
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                <span>
                  Подтверждаю корректность синтетических данных и согласен с демонстрационной
                  обработкой заявки.
                </span>
              </label>
            </>
          )}
          <div className="form-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => (step > 0 ? update({ step: step - 1 }) : onBack())}
            >
              <ArrowLeft size={17} />
              Назад
            </button>
            <button className="button primary" type="submit">
              {step === 5 ? 'Отправить заявку' : 'Продолжить'}
              <ArrowRight size={17} />
            </button>
          </div>
        </form>
        <aside className="card calculator">
          <span className="product-icon wallet">₽</span>
          <h3>{product.name}</h3>
          <div className="calc-item">
            <span>Сумма финансирования</span>
            <strong>{money(draft.amount)}</strong>
          </div>
          <div className="calc-item">
            <span>Предварительный платёж</span>
            <strong>
              {money(
                monthlyPayment(Number(draft.amount) || 0, Number(draft.months) || 1, product.rate),
              )}
              <small> / мес.</small>
            </strong>
          </div>
          <div className="calc-pair">
            <span>
              Срок<strong>{draft.months || '—'} мес.</strong>
            </span>
            <span>
              Демо-ставка<strong>{product.rate}%</strong>
            </span>
          </div>
          <div className="divider" />
          <p>
            <CheckCircle2 size={16} />
            Черновик сохраняется автоматически
          </p>
          <p>
            <CheckCircle2 size={16} />
            Результат — в вашем кабинете
          </p>
          <small className="muted">
            Расчёт иллюстративный. Это прототип, реальные кредиты не оформляются.
          </small>
        </aside>
      </div>
    </>
  );
}
