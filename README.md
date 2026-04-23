# Albion Analytics Bot

Discord bot and web dashboard for Albion Online guild operations: events, tickets, analytics, and full economy accounting.

---

## RU

### Что это

`Albion Analytics Bot` — единая система для гильдии:
- Discord-бот для ежедневных действий (ивенты, тикеты, роли, статистика).
- Веб-дашборд для управления, аналитики и экономики.
- Экономический модуль на двойной записи с аудитом и сверкой.

### Основные подсистемы

#### 1) Discord Bot
- Тикеты: создание, распределение, оценка, контроль.
- Ивенты: шаблоны, слоты, join/leave/manage, ручные замены.
- Роли и доступ: member / mentor / founder / economy.
- Статистика игроков и payroll-инструменты.

#### 2) Web Dashboard
- KPI и сводная аналитика по активности.
- Управление шаблонами, ролями, системным состоянием.
- Отдельная страница Economy Ops для финансовых операций.

#### 3) Economy Ops (двойная запись)
- Журнал проводок и линии проводок (`Dr/Cr`).
- Routing rules для автоматической контировки по категории.
- Workflow approve/reject для риск-операций.
- Reconciliation (импорт игровых логов + контроль расхождений).
- Audit trail всех значимых действий.

### Экономические категории и функции

#### Dashboard
- KPI: `Balance`, `Weekly Profit`, `Cash Gap`, `Mismatches`.
- `Recent Transactions` и превью проблем (`alerts/discrepancies`).
- `API Status` с авто-обновлением и sparkline по latency.
- Фильтры и пороги алертов (скрыты по умолчанию).

#### Operation
- Карточки с модальными формами (первая строка — широкая `New Operation`, далее две строки по 3 карточки):
  - New Operation
  - Guild Tasks
  - Award Payout
  - Routing Rules
  - CSV Import
  - Market Price
  - Loot Buyback
  - Regear Request

#### Journal
- Очередь pending проводок.
- `Approve / Reject` с фиксацией reviewer и note.

#### Reconciliation
- Таблицы задач, выплат, правил, импортов.
- Статусы Buyback/Regear.
- Кнопка `Issue` для финализации regear.

#### Reports
- `Balance Snapshot`, `PnL Summary`, `Cashflow Summary`, `Forecast`.
- Полный `Audit Trail`.

### Спец-модули экономики

#### Loot Buyback
- Выкуп лута у игроков: `market - 20%`.
- Цена фиксируется в момент запроса через Albion pricing API.
- Авто-апрув при сумме <= `auto_approve_limit`.
- Бухгалтерия (при approved): `Дт 1200 / Кт 1000`.

#### Regear / Insurance
- Создание заявки (pending) с обязательным `screenshot_url`.
- Отдельный шаг выдачи (`issue`) после проверки.
- Бухгалтерия (при issue): `Дт 5210 / Кт 1210`.

### Хранение данных и устойчивость

Данные не держатся только в UI и не теряются при перезапуске рендера:
- Проводки: `econ_journal_entries`, `econ_journal_lines`
- Правила: `econ_routing_rules`
- Задачи/выплаты: `econ_guild_bonus_tasks`, `econ_guild_bonus_awards`
- Импорты/расхождения: `econ_game_log_imports`, `econ_import_discrepancies`
- Алерты/конфиг: `econ_alerts`, `econ_config`
- Buyback/Regear: `econ_loot_buyback_requests`, `econ_regear_requests`
- Аудит: `econ_audit_log`

Схема инициализируется безопасно (`CREATE TABLE IF NOT EXISTS`), сиды используют insert-if-missing/upsert и не перетирают рабочие данные.

### Основные API-маршруты Economy

- `GET /dashboard/api/economy/data`
- `GET /dashboard/api/economy/reports`
- `POST /dashboard/api/economy/route-op`
- `POST /dashboard/api/economy/task`
- `POST /dashboard/api/economy/task/delete`
- `POST /dashboard/api/economy/award`
- `POST /dashboard/api/economy/routing-rule`
- `POST /dashboard/api/economy/import-log`
- `POST /dashboard/api/economy/config`
- `POST /dashboard/api/economy/review-entry`
- `POST /dashboard/api/economy/alert/ack`
- `POST /dashboard/api/economy/discrepancy/resolve`
- `GET /dashboard/api/economy/price`
- `POST /dashboard/api/economy/loot-buyback`
- `POST /dashboard/api/economy/regear`

### Запуск и конфигурация

#### Обязательные переменные
- `DISCORD_TOKEN`
- `DATABASE_URL`
- `DASHBOARD_SECRET`

#### Рекомендуемые переменные
- `GUILD_IDS` (или `GUILD_ID`/`GUILD_ID2`)
- `DISCORD_FORCE_COMMAND_SYNC`
- `DISCORD_SKIP_COMMAND_SYNC`
- `DISCORD_COMMAND_SYNC_DEFER_SEC`
- `DISCORD_COMMAND_SYNC_JITTER_SEC`
- `DISCORD_CF1015_RETRY_AFTER_SEC`
- `ECON_DATABASE_URL` (отдельная БД для экономики, опционально)

#### Локальный старт
1. `pip install -r requirements.txt`
2. Создать `.env` с обязательными переменными
3. `python bot.py`
4. Открыть `/dashboard` и авторизоваться через `DASHBOARD_SECRET`

---

## EN

### What this project is

`Albion Analytics Bot` is a unified guild operations platform:
- Discord bot for daily workflows (events, tickets, role access, stats).
- Web dashboard for oversight and administration.
- Economy subsystem with double-entry accounting, approvals, reconciliation, and audit.

### Main components

#### 1) Discord Bot
- Ticket lifecycle: create, assign, review, rate.
- Event lifecycle: templates, slot signup, roster management.
- Role/access tiers: member / mentor / founder / economy.
- Player analytics and mentor payroll tooling.

#### 2) Web Dashboard
- KPI and operational analytics.
- Role assist, template management, system diagnostics.
- Dedicated Economy Ops page for accounting operations.

#### 3) Economy Ops (double-entry)
- Journal entries and journal lines (`Dr/Cr`).
- Routing rules for category-based posting.
- Approval flow (`approve/reject`) for controlled posting.
- Reconciliation from imported game logs.
- Full audit trail.

### Economy categories and functions

#### Dashboard
- KPI cards: `Balance`, `Weekly Profit`, `Cash Gap`, `Mismatches`.
- Recent transactions and risk preview.
- API health with auto-refresh and latency sparkline.
- Collapsed-by-default filters and alert thresholds.

#### Operation
- Card-based modal layout (first row has a wide `New Operation`, next rows use 3 cards each):
  - New Operation
  - Guild Tasks
  - Award Payout
  - Routing Rules
  - CSV Import
  - Market Price
  - Loot Buyback
  - Regear Request

#### Journal
- Pending approval queue.
- Approve/reject actions with reviewer metadata.

#### Reconciliation
- Tasks, awards, rules, imports overview.
- Buyback/regear status tracking.
- Regear `Issue` completion action.

#### Reports
- Balance, PnL, cashflow, forecast.
- Immutable audit trail.

### Dedicated economy modules

#### Loot Buyback
- Player loot buyback at `market - 20%`.
- Market snapshot pricing via Albion pricing API.
- Auto-approval under `auto_approve_limit`.
- Accounting (approved): `Dr 1200 / Cr 1000`.

#### Regear / Insurance
- Claim creation (`pending`) with mandatory screenshot URL.
- Separate `issue` step after treasury review.
- Accounting (issue): `Dr 5210 / Cr 1210`.

### Data persistence and reload safety

Economy data is persisted in DB and reloaded on every dashboard refresh:
- `econ_journal_entries`, `econ_journal_lines`
- `econ_routing_rules`
- `econ_guild_bonus_tasks`, `econ_guild_bonus_awards`
- `econ_game_log_imports`, `econ_import_discrepancies`
- `econ_alerts`, `econ_config`
- `econ_loot_buyback_requests`, `econ_regear_requests`
- `econ_audit_log`

Schema initialization is non-destructive (`CREATE TABLE IF NOT EXISTS`), and seed/config writes use insert-if-missing/upsert semantics.

### Economy API routes

- `GET /dashboard/api/economy/data`
- `GET /dashboard/api/economy/reports`
- `POST /dashboard/api/economy/route-op`
- `POST /dashboard/api/economy/task`
- `POST /dashboard/api/economy/task/delete`
- `POST /dashboard/api/economy/award`
- `POST /dashboard/api/economy/routing-rule`
- `POST /dashboard/api/economy/import-log`
- `POST /dashboard/api/economy/config`
- `POST /dashboard/api/economy/review-entry`
- `POST /dashboard/api/economy/alert/ack`
- `POST /dashboard/api/economy/discrepancy/resolve`
- `GET /dashboard/api/economy/price`
- `POST /dashboard/api/economy/loot-buyback`
- `POST /dashboard/api/economy/regear`

### Setup

#### Required environment variables
- `DISCORD_TOKEN`
- `DATABASE_URL`
- `DASHBOARD_SECRET`

#### Recommended environment variables
- `GUILD_IDS` (or `GUILD_ID`/`GUILD_ID2`)
- `DISCORD_FORCE_COMMAND_SYNC`
- `DISCORD_SKIP_COMMAND_SYNC`
- `DISCORD_COMMAND_SYNC_DEFER_SEC`
- `DISCORD_COMMAND_SYNC_JITTER_SEC`
- `DISCORD_CF1015_RETRY_AFTER_SEC`
- `ECON_DATABASE_URL` (optional dedicated economy DB)

#### Local run
1. `pip install -r requirements.txt`
2. Create `.env` with required variables
3. Start: `python bot.py`
4. Open `/dashboard` and authenticate with `DASHBOARD_SECRET`
