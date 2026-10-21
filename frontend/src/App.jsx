import { createId } from './lib/id.js';
import { useEffect, useState } from 'react';
import {
  ArrowLeftRight,
  ArrowUpRight,
  Bell,
  Building2,
  Check,
  ChevronDown,
  ChevronRight,
  FileText,
  LayoutDashboard,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Wallet,
  X,
} from 'lucide-react';
import Dashboard, { ProductCard } from './components/Dashboard';
import Wizard from './components/Wizard';
import ApplicationDetails from './components/ApplicationDetails';
import { Empty, Field, Modal, Status } from './components/UI';
import {
  dateTime,
  money,
  newDraft,
  products,
  readState,
  statusLabels,
  STORAGE_KEY,
} from './lib/credit';
const navigation = [
  { id: 'dashboard', label: 'Обзор', icon: LayoutDashboard },
  { id: 'products', label: 'Кредитные продукты', icon: Wallet },
  { id: 'applications', label: 'Мои заявки', icon: FileText },
  { id: 'profile', label: 'Компания и профиль', icon: Building2 },
];
function loadPage() {
  const page = window.location.hash.slice(1);
  return ['dashboard', 'products', 'applications', 'profile', 'bank'].includes(page)
    ? page
    : 'dashboard';
}
export default function App() {
  const [state, setState] = useState(readState);
  const [page, setPage] = useState(loadPage);
  const [selectedId, setSelectedId] = useState(null);
  const [mode, setMode] = useState(() => (loadPage() === 'bank' ? 'bank' : 'client'));
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState('');
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [storageError, setStorageError] = useState(false);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [state]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const handler = () => {
      setPage(loadPage());
      setSelectedId(null);
    };
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);
  const navigate = (next) => {
    setPage(next);
    setSelectedId(null);
    setSearch('');
    setFilter('all');
    window.history.pushState(null, '', `#${next}`);
    window.scrollTo(0, 0);
  };
  const notify = (message) => setToast(message);
  const saveApplication = (application, announce = false) =>
    setState((previous) => {
      const exists = previous.applications.some((a) => a.id === application.id);
      return {
        ...previous,
        applications: exists
          ? previous.applications.map((a) => (a.id === application.id ? application : a))
          : [application, ...previous.applications],
        notifications: announce
          ? [
              {
                id: createId(),
                text: `Заявка ${application.number}: ${statusLabels[application.status]}`,
                at: new Date().toISOString(),
              },
              ...previous.notifications,
            ].slice(0, 30)
          : previous.notifications,
      };
    });
  const start = (productId = 'working') => {
    const draft = newDraft(state.company, productId);
    saveApplication(draft);
    setSelectedId(draft.id);
    setPage('detail');
    window.scrollTo(0, 0);
  };
  const open = (id) => {
    setSelectedId(id);
    setPage('detail');
    window.scrollTo(0, 0);
  };
  const selected = state.applications.find((a) => a.id === selectedId);
  const switchMode = () => {
    const next = mode === 'client' ? 'bank' : 'client';
    setMode(next);
    navigate(next === 'bank' ? 'bank' : 'dashboard');
  };
  const rows = state.applications.filter(
    (a) =>
      (mode !== 'bank' || a.status !== 'draft') &&
      (filter === 'all' || a.status === filter) &&
      `${a.number} ${a.name} ${products.find((p) => p.id === a.productId)?.name}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#dashboard"
          onClick={(e) => {
            e.preventDefault();
            navigate(mode === 'bank' ? 'bank' : 'dashboard');
          }}
        >
          <span className="alfa-mark">
            А<span />
          </span>
          <div>
            Альфа-Бизнес<small>Кредитный кабинет</small>
          </div>
        </a>
        <button className="company-switch" onClick={() => navigate('profile')}>
          <span className="company-avatar">М</span>
          <div>
            <strong>{state.company.name}</strong>
            <small>ИНН {state.company.inn}</small>
          </div>
          <ChevronDown size={15} />
        </button>
        <div className="nav-caption">{mode === 'bank' ? 'РАБОЧЕЕ МЕСТО БАНКА' : 'ВАШ КАБИНЕТ'}</div>
        <nav aria-label="Основное меню">
          {(mode === 'bank'
            ? [
                { id: 'bank', label: 'Очередь заявок', icon: FileText },
                { id: 'profile', label: 'Демо-компания', icon: Building2 },
              ]
            : navigation
          ).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${page === id || (id === 'applications' && page === 'detail' && mode === 'client') ? 'active' : ''}`}
              onClick={() => navigate(id)}
            >
              <Icon size={20} />
              <span>{label}</span>
              {id === 'applications' && <small>{state.applications.length}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card">
            <span className="help-icon">
              <Sparkles size={20} />
            </span>
            <h3>Рядом с вашим бизнесом</h3>
            <p>Ответы на вопросы — прямо в кабинете.</p>
            <button className="text-button" onClick={() => setModal('help')}>
              Как это работает
              <ArrowUpRight size={15} />
            </button>
          </div>
          <button className="nav-item mode-switch" onClick={switchMode}>
            <ArrowLeftRight size={19} />
            <span>{mode === 'bank' ? 'Кабинет клиента' : 'Рабочее место банка'}</span>
          </button>
          <div className="sidebar-note">
            <span className="live-dot" />
            Альфа-Хак · Демо-прототип
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            {mode === 'bank' ? 'Рабочее место банка' : 'Кабинет предпринимателя'}
            <ChevronRight size={14} />
            <strong>
              {page === 'detail'
                ? 'Заявка'
                : {
                    dashboard: 'Обзор',
                    products: 'Продукты',
                    applications: 'Мои заявки',
                    profile: 'Профиль',
                    bank: 'Очередь заявок',
                  }[page]}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="demo-badge">Демо-данные</span>
            <button
              className="icon-button notification-button"
              aria-label="Уведомления"
              onClick={() => setModal('notifications')}
            >
              <Bell size={21} />
              {state.notifications.length > 0 && <i />}
            </button>
            <span className="top-divider" />
            <button className="user-button" onClick={() => navigate('profile')}>
              <span className="user-avatar">{mode === 'bank' ? 'КМ' : 'АС'}</span>
              <span>
                {mode === 'bank' ? 'Кредитный менеджер' : state.company.contact.split(' ')[0]}
                <small>{mode === 'bank' ? 'Демо-доступ' : state.company.role}</small>
              </span>
              <ChevronDown size={14} />
            </button>
          </div>
        </header>
        <main>
          {storageError && (
            <div className="error-banner" role="alert">
              Браузер не позволяет сохранить данные. Изменения доступны только до перезагрузки
              страницы.
            </div>
          )}
          {page === 'dashboard' && (
            <Dashboard
              state={state}
              onNavigate={navigate}
              onNew={start}
              onOpen={open}
              onReport={() => setModal('report')}
            />
          )}
          {page === 'products' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ДЕНЬГИ ДЛЯ НОВЫХ ВОЗМОЖНОСТЕЙ</div>
                  <h1>
                    У каждого плана есть решение<span className="red">.</span>
                  </h1>
                  <p>Выберите финансирование под задачи вашего бизнеса.</p>
                </div>
              </div>
              <div className="catalog-banner">
                <div>
                  <span className="eyebrow">ПОНЯТНЫЕ УСЛОВИЯ</span>
                  <h2>
                    От небольшой закупки
                    <br />
                    до большого шага вперёд
                  </h2>
                  <p>Одна заявка. Прозрачный статус. Всё онлайн.</p>
                </div>
                <div className="banner-symbol" aria-hidden="true">
                  ↗
                </div>
              </div>
              <div className="catalog-grid">
                {products.map((p) => (
                  <ProductCard key={p.id} product={p} onSelect={start} />
                ))}
              </div>
              <p className="footnote">
                Все ставки и суммы синтетические и не являются условиями кредитования Альфа-Банка.
              </p>
            </>
          )}
          {['applications', 'bank'].includes(page) && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    {mode === 'bank' ? 'КРЕДИТНЫЙ КОНВЕЙЕР' : 'ОТ ПЛАНОВ К ДЕЛУ'}
                  </div>
                  <h1>
                    {mode === 'bank' ? 'Очередь заявок' : 'Ваши заявки'}
                    <span className="red">.</span>
                  </h1>
                  <p>
                    {mode === 'bank'
                      ? 'Проверки, решения и история действий в одном месте.'
                      : 'Продолжите оформление или посмотрите, что происходит с заявкой.'}
                  </p>
                </div>
                {mode === 'client' && (
                  <button className="button primary" onClick={() => start()}>
                    Новая заявка
                    <ArrowUpRight size={18} />
                  </button>
                )}
              </div>
              <div className="list-toolbar">
                <label className="search-field">
                  <Search size={19} />
                  <input
                    aria-label="Поиск заявок"
                    placeholder="Номер заявки, продукт или компания"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                <label className="filter-field">
                  <SlidersHorizontal size={17} />
                  <select
                    aria-label="Фильтр по статусу"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    <option value="all">Все статусы</option>
                    {Object.entries(statusLabels).map(([k, l]) => (
                      <option key={k} value={k}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="card applications-table">
                <div className="table-head">
                  <span>Продукт / компания</span>
                  <span>Сумма и срок</span>
                  <span>Статус</span>
                  <span />
                </div>
                {rows.map((a) => (
                  <button className="application-row" key={a.id} onClick={() => open(a.id)}>
                    <div className="application-name">
                      <span className="table-icon">
                        <FileText size={20} />
                      </span>
                      <div>
                        <strong>{products.find((p) => p.id === a.productId)?.short}</strong>
                        <small>
                          {mode === 'bank' ? a.name + ' · ' : ''}№ {a.number}
                        </small>
                      </div>
                    </div>
                    <div>
                      <strong>{money(a.amount)}</strong>
                      <small>{a.months} месяцев</small>
                    </div>
                    <Status status={a.status} />
                    <ChevronRight size={18} />
                  </button>
                ))}
                {!rows.length && (
                  <Empty
                    title="Заявок не найдено"
                    text="Попробуйте изменить фильтр или создайте новую заявку."
                  />
                )}
              </div>
            </>
          )}
          {page === 'detail' &&
            selected &&
            (selected.status === 'draft' ? (
              <Wizard
                key={selected.id}
                application={selected}
                onSave={saveApplication}
                onSubmit={(a) => {
                  saveApplication(a, true);
                  notify('Заявка отправлена. Запустите демо-проверки.');
                }}
                onBack={() => navigate('applications')}
                notify={notify}
              />
            ) : (
              <ApplicationDetails
                key={selected.id}
                application={selected}
                mode={mode}
                onUpdate={(a, announce = true) => saveApplication(a, announce)}
                onBack={() => navigate(mode === 'bank' ? 'bank' : 'applications')}
                notify={notify}
              />
            ))}
          {page === 'profile' && (
            <Profile
              company={state.company}
              onSave={(company) => {
                setState((s) => ({ ...s, company }));
                notify('Профиль компании сохранён');
              }}
            />
          )}
          <footer>
            <span>© 2026 Альфа-Хак · Умный кредитный кабинет</span>
            <span>
              <ShieldCheck size={14} />
              Синтетические данные · Учебный прототип
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={19} />
          {toast}
          <button
            className="icon-button"
            aria-label="Скрыть уведомление"
            onClick={() => setToast('')}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {modal === 'notifications' && (
        <Modal title="Уведомления" onClose={() => setModal(null)}>
          <div className="notifications">
            {state.notifications.length ? (
              state.notifications.map((n) => (
                <article key={n.id}>
                  <span className="notification-icon">
                    <Bell size={18} />
                  </span>
                  <div>
                    <p>{n.text}</p>
                    <small>{dateTime(n.at)}</small>
                  </div>
                </article>
              ))
            ) : (
              <p>Новых уведомлений нет.</p>
            )}
          </div>
          {state.notifications.length > 0 && (
            <button
              className="button secondary wide"
              onClick={() => setState((s) => ({ ...s, notifications: [] }))}
            >
              Очистить уведомления
            </button>
          )}
        </Modal>
      )}
      {modal === 'report' && (
        <Modal title="Кредитное здоровье бизнеса" onClose={() => setModal(null)}>
          <div className="report-score">
            <ShieldCheck size={40} />
            <strong>
              812 <small>/ 950</small>
            </strong>
          </div>
          <p>Высокий рейтинг · иллюстративный отчёт на синтетических данных.</p>
          <dl className="review-list">
            <div>
              <dt>Просроченные платежи</dt>
              <dd className="positive">Отсутствуют</dd>
            </div>
            <div>
              <dt>Платёжная дисциплина</dt>
              <dd>Стабильная</dd>
            </div>
            <div>
              <dt>Действующие обязательства</dt>
              <dd>{money(2480000)}</dd>
            </div>
            <div>
              <dt>Последний платёж · 5 октября</dt>
              <dd>{money(86400)}</dd>
            </div>
          </dl>
          <div className="info-box">
            Этот индекс показан для примера. Скоринг каждой новой заявки рассчитывается отдельно по
            её финансовым данным.
          </div>
        </Modal>
      )}
      {modal === 'help' && (
        <Modal title="Как устроен кабинет" onClose={() => setModal(null)}>
          <div className="help-steps">
            <p>
              <strong>01. Выберите продукт</strong>Откройте каталог и укажите задачу бизнеса.
            </p>
            <p>
              <strong>02. Заполните заявку</strong>Данные автоматически сохраняются в этом браузере.
            </p>
            <p>
              <strong>03. Получите решение</strong>Запустите демо-проверку. Для ручного решения
              перейдите в рабочее место банка.
            </p>
            <p>
              <strong>04. Подпишите предложение</strong>Демо-код 1234 заменяет подпись. Затем
              доступна имитация выдачи.
            </p>
          </div>
          <div className="info-box">
            Авторизация, проверки и выдача в этом прототипе не подключены к реальным системам. Не
            вводите персональные или конфиденциальные данные.
          </div>
        </Modal>
      )}
    </div>
  );
}
function Profile({ company, onSave }) {
  const [form, setForm] = useState(company);
  const field = (key, label, options = {}) => (
    <Field label={label}>
      <input
        required
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        {...options}
      />
    </Field>
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ВАШ БИЗНЕС</div>
          <h1>
            Компания и профиль<span className="red">.</span>
          </h1>
          <p>Эти данные подставятся в новые заявки.</p>
        </div>
      </div>
      <form
        className="card profile-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSave(form);
        }}
      >
        <div className="profile-heading">
          <span className="company-avatar large">
            <Building2 size={28} />
          </span>
          <div>
            <h2>{company.name}</h2>
            <p className="muted">Демонстрационный профиль предпринимателя</p>
          </div>
        </div>
        <h3>О компании</h3>
        <div className="form-grid">
          {field('name', 'Название компании', { maxLength: 150 })}
          {field('inn', 'ИНН', { pattern: '[0-9]{10}|[0-9]{12}', title: '10 или 12 цифр' })}
          {field('ogrn', 'ОГРН / ОГРНИП', {
            pattern: '[0-9]{13}|[0-9]{15}',
            title: '13 или 15 цифр',
          })}
          {field('okved', 'ОКВЭД')}
          {field('address', 'Юридический адрес', { maxLength: 300 })}
        </div>
        <h3>Представитель компании</h3>
        <div className="form-grid">
          {field('contact', 'ФИО', { minLength: 3, maxLength: 150 })}
          {field('email', 'Электронная почта', { type: 'email' })}
          <Field label="Ваша роль">
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
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
        </div>
        <div className="form-actions">
          <span className="muted">Используйте только синтетические данные</span>
          <button className="button primary" type="submit">
            Сохранить изменения
            <Check size={17} />
          </button>
        </div>
      </form>
    </>
  );
}
