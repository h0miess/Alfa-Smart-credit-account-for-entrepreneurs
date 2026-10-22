import { createId } from './id.js';
export const money = (value) =>
  new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(Number(value) || 0);
export const dateTime = (value) =>
  new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
export const products = [
  {
    id: 'working',
    name: 'Кредит на оборотные средства',
    short: 'На оборотные средства',
    description: 'Закупайте товары, рассчитывайтесь с поставщиками и растите без пауз.',
    max: 10000000,
    min: 100000,
    months: 36,
    rate: 24,
    icon: 'wallet',
    tag: 'Выбор предпринимателей',
  },
  {
    id: 'invest',
    name: 'Кредит на развитие бизнеса',
    short: 'На развитие бизнеса',
    description: 'Оборудование, новые точки и большие планы для вашего дела.',
    max: 100000000,
    min: 1000000,
    minMonths: 12,
    months: 84,
    rate: 22,
    icon: 'growth',
    tag: 'Для больших планов',
  },
  {
    id: 'overdraft',
    name: 'Овердрафт',
    short: 'Овердрафт',
    description: 'Поддержка на случай кассового разрыва. Деньги всегда под рукой.',
    max: 15000000,
    min: 50000,
    minMonths: 12,
    months: 12,
    rate: 26,
    icon: 'bolt',
    tag: 'На каждый день',
  },
];
export const statusLabels = {
  draft: 'Черновик',
  submitted: 'Заявка на рассмотрении',
  checking: 'Заявка на рассмотрении',
  external: 'Заявка на рассмотрении',
  scoring: 'Заявка на рассмотрении',
  review: 'Заявку проверяет специалист',
  info: 'Нужны документы',
  offer: 'Готово предложение',
  accepted: 'Условия приняты',
  signed: 'Договор подписан',
  funded: 'Деньги на счёте',
  rejected: 'Отказ',
  declined: 'Оферта отклонена',
};
const transitions = {
  draft: ['submitted'],
  submitted: ['checking'],
  checking: ['external'],
  external: ['scoring'],
  scoring: ['review', 'info', 'offer', 'rejected'],
  review: ['info', 'offer', 'rejected'],
  info: ['checking'],
  offer: ['accepted', 'signed', 'declined'],
  accepted: ['signed'],
  signed: ['funded'],
  funded: [],
  rejected: [],
  declined: [],
};
export function transition(application, status, note, actor = 'Система') {
  if (!transitions[application.status]?.includes(status))
    throw new Error(`Недопустимый переход: ${application.status} → ${status}`);
  if (
    status === 'accepted' &&
    application.offer_expires_at &&
    Date.parse(application.offer_expires_at) <= Date.now()
  )
    throw new Error('Срок предложения истёк');
  return {
    ...application,
    ...(status === 'offer'
      ? { offer_expires_at: new Date(Date.now() + 14 * 86400000).toISOString() }
      : {}),
    status,
    history: [
      ...application.history,
      { from_status: application.status, status, note, actor, at: new Date().toISOString() },
    ],
  };
}
export function monthlyPayment(amount, months, rate) {
  const r = rate / 1200;
  return r ? (amount * r) / (1 - (1 + r) ** -months) : amount / months;
}
export function scoreApplication(application) {
  const ratio = Number(application.amount) / Math.max(Number(application.revenue), 1);
  const debtRatio = Number(application.debt) / Math.max(Number(application.revenue), 1);
  return Math.max(100, Math.min(950, Math.round(870 - ratio * 25 - debtRatio * 130)));
}
export function runChecks(application) {
  let next = transition(application, 'checking', 'Поля и комплектность данных проверены');
  next = transition(next, 'external', 'ЕГРЮЛ, ФНС, БКИ: синтетические ответы получены');
  next = transition(next, 'scoring', 'Рассчитаны долговая нагрузка и скоринговый балл');
  const score = scoreApplication(next);
  const scenario = next.scenario || 'auto';
  const decision =
    scenario === 'reject' || (scenario === 'auto' && score < 450)
      ? 'rejected'
      : scenario === 'info'
        ? 'info'
        : scenario === 'review' || (scenario === 'auto' && score < 650)
          ? 'review'
          : 'offer';
  next = {
    ...next,
    score,
    reasons: [
      {
        label:
          decision === 'rejected'
            ? 'Доходов недостаточно для обслуживания запрошенной суммы'
            : scenario === 'changed'
              ? 'Сумма снижена, чтобы платёж соответствовал оборотам компании'
              : decision === 'review'
                ? 'Необходима дополнительная оценка специалистом'
                : decision === 'info'
                  ? 'Нужны подтверждающие документы'
                  : 'Заявка соответствует условиям продукта',
      },
    ],
    risk_factors: decision === 'rejected' ? [{ label: 'Высокая долговая нагрузка' }] : [],
    positive_factors: decision === 'offer' ? [{ label: 'Регулярные поступления на счёт' }] : [],
    requested_documents:
      decision === 'info'
        ? [
            'Финансовая отчётность за последний квартал',
            'Выписка по счетам в других банках за 12 месяцев',
          ]
        : [],
    checkedAt: new Date().toISOString(),
    checks: ['ЕГРЮЛ / ЕГРИП', 'ФНС «Прозрачный бизнес»', 'Кредитная история (БКИ)'],
    approvedAmount: scenario === 'changed' ? Math.round(next.amount * 0.8) : Number(next.amount),
  };
  return transition(
    next,
    decision,
    decision === 'info'
      ? 'Загрузите финансовую отчётность за последний квартал.'
      : decision === 'rejected'
        ? 'Высокая долговая нагрузка в демонстрационной модели.'
        : decision === 'review'
          ? 'Необходимо решение кредитного менеджера.'
          : scenario === 'changed'
            ? 'Одобрено 80% запрошенной суммы. Проверьте новые условия.'
            : 'Предложение сформировано. Ознакомьтесь с условиями.',
  );
}
export const defaultCompany = {
  name: 'ООО «Мастерская»',
  inn: '7701234560',
  ogrn: '1207700001234',
  address: 'Москва, ул. Лесная, д. 7',
  okved: '47.91',
  contact: 'Александр Смирнов',
  email: 'alex@example.com',
  role: 'Собственник бизнеса',
};
export function newDraft(company, productId = 'working') {
  const product = products.find((p) => p.id === productId) || products[0];
  return {
    id: createId(),
    number: `АК-${Date.now().toString().slice(-6)}`,
    productId: product.id,
    purpose: 'Пополнение оборотных средств',
    amount: 1500000,
    months: Math.min(24, product.months),
    revenue: 1200000,
    debt: 80000,
    ...company,
    status: 'draft',
    scenario: 'auto',
    step: 0,
    collateral_value: 0,
    documents: [],
    history: [
      { status: 'draft', at: new Date().toISOString(), actor: 'Клиент', note: 'Заявка создана' },
    ],
  };
}
export function initialState() {
  const draft = newDraft(defaultCompany);
  const application = runChecks(transition(draft, 'submitted', 'Заявка отправлена', 'Клиент'));
  return {
    company: defaultCompany,
    applications: [application],
    notifications: [
      {
        id: createId(),
        text: 'Заявка одобрена. Предложение уже ждёт вас в кабинете.',
        at: new Date().toISOString(),
      },
    ],
  };
}
export const STORAGE_KEY = 'alfa-credit-demo-v1';
export function readState() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (
      value &&
      typeof value.company?.name === 'string' &&
      Array.isArray(value.applications) &&
      Array.isArray(value.notifications)
    )
      return {
        ...value,
        applications: value.applications.map((a) => ({
          ...a,
          productId: a.productId === 'line' ? 'working' : a.productId,
        })),
      };
  } catch {
    /* Start with synthetic data if storage is unavailable or invalid. */
  }
  return initialState();
}

export const statusGuidance = {
  draft: ['Заполните параметры и отправьте заявку', 'В удобное для вас время'],
  submitted: ['Дополнительных действий не требуется', 'Обычно несколько минут'],
  checking: ['Проверяем сведения о компании', 'Обычно несколько минут'],
  external: ['Получаем сведения из источников', 'Обычно несколько минут'],
  scoring: ['Готовим решение', 'Обычно несколько минут'],
  review: ['Ожидайте решения специалиста', 'Ориентир — 1 рабочий день'],
  info: ['Загрузите весь список документов в эту заявку', 'Ответьте в течение 30 дней'],
  offer: ['Изучите условия и примите или отклоните предложение', 'Предложение действует 14 дней'],
  accepted: ['Подпишите договор кодом в кабинете', 'Обычно несколько минут'],
  signed: ['Ожидайте зачисления на расчётный счёт', 'В демо — сразу после подтверждения выдачи'],
  funded: ['Зачисление на расчётный счёт подтверждено (демо)', 'Оформление завершено'],
  rejected: ['Изучите причины и измените параметры новой заявки', 'Рассмотрение завершено'],
  declined: ['При необходимости создайте новую заявку', 'Заявка закрыта'],
};
export function offerTerms(a) {
  const product = products.find((p) => p.id === a.productId);
  return (
    (a.offer ? { ...a.offer, annual_rate_pct: a.offer.annual_rate_pct ?? a.offer.rate } : null) || {
      amount: a.approvedAmount || a.amount,
      term_months: a.months,
      annual_rate_pct: product.rate,
      monthly_payment: monthlyPayment(a.approvedAmount || a.amount, a.months, product.rate),
    }
  );
}
