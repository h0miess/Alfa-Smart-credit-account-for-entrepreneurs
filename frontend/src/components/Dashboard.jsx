nimport {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  FileText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { money, products, monthlyPayment } from '../lib/credit';
import { SectionTitle, Status, productIcons } from './UI';
export function ProductCard({ product, onSelect, compact = false }) {
  const Icon = productIcons[product.icon];
  return (
    <article className={`product-card ${compact ? 'compact' : ''}`}>
      <div className="product-top">
        <span className={`product-icon ${product.icon}`}>
          <Icon size={23} />
        </span>
        <ArrowUpRight size={20} />
      </div>
      <h3>{product.short}</h3>
      {!compact && <p>{product.description}</p>}
      <div className="product-terms">
        <span>
          до <strong>{money(product.max)}</strong>
        </span>
        <span>
          от {product.rate}% · до {product.months} мес.
        </span>
      </div>
      <button className="button secondary" onClick={() => onSelect(product.id)}>
        Выбрать продукт
        <ArrowRight size={16} />
      </button>
    </article>
  );
}
export default function Dashboard({ state, onNavigate, onNew, onOpen, onReport }) {
  const active = state.applications.filter(
    (a) => !['rejected', 'declined', 'funded'].includes(a.status),
  );
  const approved = active.find((a) => a.status === 'offer');
  const latest = active[0];
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ВАШ БИЗНЕС. ВАШИ ВОЗМОЖНОСТИ.</div>
          <h1>
            Больше возможностей
            <br className="desktop-break" /> для вашего дела<span className="red">.</span>
          </h1>
          <p>Финансирование, которое помогает двигаться вперёд.</p>
        </div>
        <button className="button primary" onClick={() => onNew()}>
          Новая заявка
          <ArrowUpRight size={18} />
        </button>
      </div>
      <div className="overview-grid">
        <article className="card rating-card">
          <div className="card-label">
            <span>Кредитное здоровье бизнеса</span>
            <ShieldCheck size={20} />
          </div>
          <div className="rating-body">
            <div className="score-ring">
              <svg viewBox="0 0 120 120" aria-hidden="true">
                <circle className="ring-track" cx="60" cy="60" r="51" />
                <circle className="ring-value" cx="60" cy="60" r="51" />
              </svg>
              <div>
                <strong>812</strong>
                <small>из 950</small>
              </div>
            </div>
            <div>
              <span className="status status-offer">Высокий рейтинг</span>
              <p>
                Ваш бизнес готов
                <br />к новым возможностям
              </p>
              <span className="positive">
                <TrendingUp size={14} /> +24 балла за месяц
              </span>
            </div>
          </div>
          <button className="card-link" onClick={onReport}>
            Кредитный отчёт
            <ChevronRight size={17} />
          </button>
        </article>
        <article className="card summary-card">
          <div className="card-label">
            Ваши обязательства
            <span className="soft-icon">
              <FileText size={19} />
            </span>
          </div>
          <div className="summary-amount">{money(2480000)}</div>
          <p className="muted">Остаток по действующим кредитам · демо</p>
          <div className="summary-bottom">
            <div>
              <span>Ближайший платёж</span>
              <strong>
                {money(86400)} <small>· 5 ноября</small>
              </strong>
            </div>
            <span className="good-dot">
              <Check size={14} />
              Без просрочек
            </span>
          </div>
        </article>
        <article className="next-card">
          <div className="card-label">
            <span>Следующий шаг</span>
            <Sparkles size={20} />
          </div>
          <h3>
            {approved
              ? 'Всё готово для роста'
              : latest
                ? 'Вы на шаг ближе'
                : 'Планы становятся делом'}
          </h3>
          <p>
            {approved
              ? 'Ваша заявка одобрена. Ознакомьтесь с предложением и получите финансирование.'
              : latest
                ? 'Откройте заявку, чтобы продолжить оформление и посмотреть её статус.'
                : 'Выберите финансирование под задачи вашего бизнеса.'}
          </p>
          <button
            onClick={() =>
              approved ? onOpen(approved.id) : latest ? onOpen(latest.id) : onNavigate('products')
            }
          >
            {approved ? 'Посмотреть предложение' : latest ? 'Перейти к заявке' : 'Выбрать продукт'}
            <ArrowRight size={18} />
          </button>
        </article>
      </div>
      <section>
        <SectionTitle
          title="Ваши заявки"
          action="Все заявки"
          onAction={() => onNavigate('applications')}
        />
        <div className="card applications-table">
          <div className="table-head">
            <span>Продукт / номер заявки</span>
            <span>Сумма и срок</span>
            <span>Статус</span>
            <span />
          </div>
          {active.slice(0, 3).map((a) => (
            <button className="application-row" key={a.id} onClick={() => onOpen(a.id)}>
              <div className="application-name">
                <span className="table-icon">
                  <FileText size={20} />
                </span>
                <div>
                  <strong>{products.find((p) => p.id === a.productId)?.short}</strong>
                  <small>№ {a.number}</small>
                </div>
              </div>
              <div>
                <strong>{money(a.amount)}</strong>
                <small>
                  {a.months} мес. · от{' '}
                  {money(
                    monthlyPayment(
                      a.amount,
                      a.months,
                      products.find((p) => p.id === a.productId).rate,
                    ),
                  )}
                  /мес.
                </small>
              </div>
              <Status status={a.status} />
              <ChevronRight size={18} />
            </button>
          ))}
          {!active.length && (
            <div className="inline-empty">
              Активных заявок пока нет. Самое время начать что-то новое.
            </div>
          )}
        </div>
      </section>
      <section>
        <SectionTitle
          title="Финансирование под ваши задачи"
          action="Все продукты"
          onAction={() => onNavigate('products')}
        />
        <div className="products-grid">
          {products.slice(0, 3).map((p) => (
            <ProductCard key={p.id} product={p} onSelect={onNew} compact />
          ))}
        </div>
      </section>
      <section className="news-section">
        <SectionTitle title="Полезно для вашего бизнеса" />
        <div className="news-grid">
          <article className="news-card">
            <div className="news-art art-red">
              <div className="abstract-stack">
                <span />
                <span />
                <span />
              </div>
              <span className="art-label">БИЗНЕС В ДВИЖЕНИИ ↗</span>
            </div>
            <div className="news-copy">
              <span className="eyebrow">{approved ? 'ВАША ЗАЯВКА' : 'ФИНАНСИРОВАНИЕ'}</span>
              <h3>
                {approved
                  ? 'Финансирование одобрено. Что дальше?'
                  : 'Как подготовить бизнес к получению кредита'}
              </h3>
              <p>
                {approved
                  ? 'Проверьте сумму, срок и график платежей в вашем предложении.'
                  : 'Соберите данные о выручке и обязательствах — это поможет подобрать условия.'}
              </p>
              <button
                className="text-button"
                onClick={() => (approved ? onOpen(approved.id) : onNavigate('products'))}
              >
                {approved ? 'Открыть предложение' : 'Подобрать продукт'}
                <ArrowRight size={15} />
              </button>
            </div>
          </article>
          <article className="news-card">
            <div className="news-art art-mint">
              <div className="abstract-chart">
                <i />
                <i />
                <i />
                <i />
              </div>
              <span className="art-label">С ПРИЦЕЛОМ НА РОСТ ↗</span>
            </div>
            <div className="news-copy">
              <span className="eyebrow">КРЕДИТНОЕ ЗДОРОВЬЕ</span>
              <h3>Сильный рейтинг — больше возможностей</h3>
              <p>Что влияет на кредитный профиль и как поддерживать его в хорошей форме.</p>
              <button className="text-button" onClick={onReport}>
                Посмотреть факторы
                <ArrowRight size={15} />
              </button>
            </div>
          </article>
        </div>
      </section>
    </>
  );
}
