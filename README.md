# Albion Analytics Bot

RU: Бот для обучения игроков, аналитики, событий и менеджмента тикетов в Albion Online.  
EN: A Discord bot for Albion Online coaching, analytics, event management, and mentor workflows.

---

## Русский

### Основные возможности
- Тикеты на разбор сессий: создание, очередь, захват ментором, оценка, детали.
- Статистика игроков: инфографика, ранги, динамика, ошибки, лидерборд.
- Ивенты и ростер: создание события, набор в слоты, ручное управление составом.
- Выплаты менторам: расчет фонда по активности за выбранный период.
- Гильдейские роли и доступ: регистрация по коду, approve/promote/demote/info.
- Веб-дашборд (dark synth UI) на том же Render Web Service — см. раздел [«Веб-дашборд»](#dashboard-ru) ниже.

<a id="dashboard-ru"></a>

### Веб-дашборд

**Зачем он нужен.** Дашборд — это отдельная веб-страница для **офицеров, менторов и руководства гильдии**: в одном месте видно срез активности и базы бота **без** длинных цепочек slash-команд в Discord и без ручной выгрузки в таблицы. Данные читаются из **той же базы**, что использует бот (PostgreSQL или SQLite), поэтому цифры согласованы с тикетами, сессиями и ивентами в каналах.

**Почему это удачное дополнение к боту, а не замена ему.**

- **Один сервис на Render** — HTTP для health-check и дашборда крутится вместе с процессом бота; не нужен отдельный фронтенд-проект или второй билд.
- **Доступ по секрету** — страница открывается только после ввода `DASHBOARD_SECRET`; это не публичная витрина, а внутренний инструмент гильдии.
- **Обзор «сверху»** — KPI и таблицы за выбранный период и гильдию обновляются кнопкой **Refresh data**; так быстрее оценить нагрузку на менторов, очередь тикетов и вовлечённость в ивенты, чем собирать то же из чата.
- **Discord остаётся местом действия** — игроки по-прежнему создают тикеты, записываются на ивенты и общаются в каналах; дашборд для **анализа, планирования и диагностики**, а не для повседневной переписки.

**Как открыть и пользоваться.**

1. Адрес: `https://<ваш-сервис>.onrender.com/dashboard` (тот же хост, что и у бота).
2. На экране входа вставьте **Access token** = значение переменной **`DASHBOARD_SECRET`** из настроек Render (храните секрет только у доверенных людей).
3. В шапке задайте **Period (days)** — глубину окна для метрик (сессии, закрытые тикеты, **закрытые** ивенты и т.д.).
4. При необходимости выберите **Guild** (фильтр по гильдии в БД) или оставьте «все гильдии».
5. Для вкладки **Mentors** можно задать **Mentor fund (silver)** — тот же смысл, что у `/payroll`, сумма вручную.
6. Нажмите **Refresh data**, чтобы подтянуть актуальные данные из БД.

**Вкладки и функции.**

| Вкладка | Содержание |
|--------|------------|
| **Overview** | Открытые тикеты, закрытые тикеты за период, сессии за период, количество **закрытых** ивентов за период. |
| **Players** | Игроки с числом сессий и средним баллом за окно, гильдия, **статус в БД** (pending / active / mentor / founder), **активные тикеты** (все не в статусе `closed`). Сортировка по активности в периоде. |
| **Tickets** | Сводка по статусам тикетов и список недавних тикетов. |
| **Events** | Аналитика посещаемости **только по ивентам со статусом `closed`** — открытые тестовые посты в статистике не участвуют. Таблицы по контенту, «никогда не был на ивенте», низкая и стабильная посещаемость; длинные списки прокручиваются внутри блока. Внизу — **Event records (cleanup)**: выбор записей и удаление из таблицы `events` (ошибочные/тестовые строки; связанные подписи удаляются каскадом). Не удаляет сообщения в Discord. |
| **Mentors** | Распределение выбранного фонда между менторами по логике, близкой к `/payroll`, за выбранное число дней. |
| **Event templates** | Редактирование `events_templates.txt`: шаблоны ростера для `/event create` подхватываются **сразу** после сохранения (тот же процесс, что и бот). |
| **Guild roles** | Переопределение Discord role ID для уровней member / mentor / founder **по гильдии в БД**; пустое поле = как в `config.yaml` + встроенные доп. ID. Без редеплоя. |
| **System** | Краткий **статус связи бота с Discord** (понятная плашка для не-разработчиков), оценка занятого места в БД относительно квоты (см. `DASHBOARD_DB_QUOTA_BYTES`), время ответа БД, аптайм HTTP и развёрнутый JSON для диагностики. |

**Важно про ивенты.** В аналитике учитываются только **завершённые** ивенты. Чтобы убрать мусор из базы, используйте блок cleanup на вкладке Events или SQL-скрипты в репозитории (например, `scripts/delete_first_three_events.sql` для точечной чистки по правилам файла).

### Новые функции (последние обновления)
- В `Manage` для ивента можно вводить не только ID, но и:
  - серверный ник,
  - username/global name,
  - mention (`@user`),
  - numeric ID.
- Если по введенному имени найдено несколько людей, бот показывает ephemeral-список выбора.
- Для `Remove` кандидаты сортируются так, что участники текущего event идут первыми.
- Добавлен автокомплит `event_id` в командах управления ивентами:
  - `/event close`
  - `/event add_player`
  - `/event remove_player`
  - `/event swap_players`
  - `/event add_extra`
- Улучшена устойчивость к `Unknown interaction` в кнопках управления событием.

### Быстрый старт
1. Используйте `/register <code>`, чтобы привязать Discord-аккаунт к гильдии.
2. Откройте `/menu` для быстрого доступа к основным функциям.
3. Создайте тикет `/ticket create` или событие `/event create`.

### Команды

#### Профиль и доступ
- `/register` — регистрация в гильдии по коду.
- `/guild action:<approve|promote|demote|info>` — управление ролями/статусом.
- `/menu` — главное меню бота.

#### Тикеты (разборы)
- `/ticket create` — создать тикет.
- `/ticket list` — список активных тикетов.
- `/ticket claim` — взять тикет в работу (Mentor).
- `/ticket rate` — оценить тикет (Mentor).
- `/ticket unclaim` — снять тикет с себя (Mentor).
- `/ticket info` — подробная информация о тикете.

#### Ивенты
- `/event create` — создать событие по шаблону.
- `/event close` — закрыть событие.
- `/event add_player` — добавить/переместить игрока в слот.
- `/event remove_player` — удалить игрока из ростера.
- `/event swap_players` — поменять двух игроков местами.
- `/event add_extra` — добавить extra-слот и назначить игрока.
- Кнопки под постом события: `Join`, `Leave`, `Close Event`, `Manage`.
- Важно: если событие фактически не состоялось, его **нельзя закрывать**. Удалите сообщение события, чтобы фейковая статистика не сохранялась в базе.

#### Статистика и выплаты
- `/stats` — персональная или целевая статистика игрока.
- `/stats_top` — топ игроков.
- `/stats_seed_test` — тестовые данные (Founder).
- `/payroll` — расчет выплат менторам.

---

## English

### Core Features
- Session review tickets: creation, queueing, claiming, rating, and inspection.
- Player analytics: dashboard visuals, rankings, trends, and error breakdowns.
- Event roster management: event posts, slot signup, and manual roster control.
- Mentor payroll: budget split based on mentoring activity over a selected period.
- Guild access control: invite-code registration and role management actions.
- Web dashboard (dark synth UI) on the same Render Web Service — see [Web dashboard](#dashboard-en) below.

<a id="dashboard-en"></a>

### Web dashboard

**Purpose.** The dashboard is a **web control deck for officers, mentors, and guild leadership**: a single place to read bot-backed metrics **without** long chains of Discord slash commands or manual exports. It queries the **same database** as the bot (PostgreSQL or SQLite), so numbers stay aligned with tickets, sessions, and events in your server.

**Why it complements the bot (and does not replace it).**

- **Single Render service** — the HTTP server (health check + dashboard) runs in the **same process** as the bot; no separate frontend deployment.
- **Secret-gated access** — `/dashboard` is protected by **`DASHBOARD_SECRET`**; it is an internal tool, not a public page.
- **Top-down view** — KPIs and tables for a chosen **period** and optional **guild** refresh with one click; faster to judge mentor load, ticket backlog, and event participation than piecing it together from chat.
- **Discord stays the workplace** — players still use channels for tickets, signups, and chat; the dashboard is for **oversight, planning, and troubleshooting**.

**How to use it.**

1. Open `https://<your-service>.onrender.com/dashboard`.
2. Sign in with **Access token** = your **`DASHBOARD_SECRET`** from Render (share only with trusted staff).
3. Set **Period (days)** for time-windowed metrics (sessions, closed tickets, **closed** events, etc.).
4. Optionally pick **Guild** or leave “all guilds”.
5. On **Mentors**, set **Mentor fund (silver)** if you want a payroll-style split (same idea as `/payroll`).
6. Click **Refresh data** to reload from the database.

**Tabs at a glance.**

| Tab | What you get |
|-----|----------------|
| **Overview** | Open tickets, tickets closed in the period, sessions in the period, **closed** events in the period. |
| **Players** | Per-player sessions and average score in the window, guild, **DB role** (pending / active / mentor / founder), **active tickets** (any ticket not `closed`). Sorted by activity in the period. |
| **Tickets** | Counts by ticket status and a recent-ticket list. |
| **Events** | Attendance analytics for **`closed` events only** — open test posts do not inflate stats. Scrollable player lists. **Event records (cleanup)** at the bottom: select rows and delete from `events` (bad/test data; signups cascade). Does **not** remove Discord messages. |
| **Mentors** | Split the chosen silver pool across mentors using logic close to `/payroll` for the selected days. |
| **Event templates** | Edit `events_templates.txt` for `/event create`; changes apply **immediately** after save (same process as the bot). |
| **Guild roles** | Override Discord role IDs for member / mentor / founder tiers **per DB guild**; blank field inherits `config.yaml` + built-in extras. No redeploy. |
| **System** | Plain-language **Discord bot connectivity** hint, database size vs quota (`DASHBOARD_DB_QUOTA_BYTES`), DB round-trip time, HTTP uptime, and raw JSON for deeper checks. |

**Events note.** Analytics count **finished** events only. To clean bad rows, use the Events-tab cleanup or repository SQL helpers (e.g. `scripts/delete_first_three_events.sql` — follow the comments in that file).

### New Features (recent updates)
- Event `Manage` input now accepts:
  - server nickname,
  - username/global name,
  - mention (`@user`),
  - numeric ID.
- If multiple users match the input, the bot shows an ephemeral user picker.
- In `Remove`, matched candidates are sorted with current event participants first.
- Added `event_id` autocomplete for event roster slash commands:
  - `/event close`
  - `/event add_player`
  - `/event remove_player`
  - `/event swap_players`
  - `/event add_extra`
- Improved interaction safety to reduce `Unknown interaction` errors in event controls.

### Quick Start
1. Run `/register <code>` to link your Discord account to the guild.
2. Run `/menu` for quick access to core actions.
3. Create a ticket with `/ticket create` or an event with `/event create`.

### Commands

#### Profile and Access
- `/register` — register with guild invite code.
- `/guild action:<approve|promote|demote|info>` — role/status management.
- `/menu` — open main bot panel.

#### Tickets (Session Reviews)
- `/ticket create` — create a review ticket.
- `/ticket list` — list active tickets.
- `/ticket claim` — claim ticket (Mentor).
- `/ticket rate` — rate ticket (Mentor).
- `/ticket unclaim` — release ticket (Mentor).
- `/ticket info` — view ticket details.

#### Events
- `/event create` — create an event from a template.
- `/event close` — close event.
- `/event add_player` — add/move a player to a slot.
- `/event remove_player` — remove player from roster.
- `/event swap_players` — swap two players.
- `/event add_extra` — add extra slot and assign a player.
- Event message buttons: `Join`, `Leave`, `Close Event`, `Manage`.
- Important: if an event did not actually happen, do **not** close it. Delete the event message so fake stats are not written to the database.

#### Analytics and Payroll
- `/stats` — personal or target player statistics.
- `/stats_top` — top players leaderboard.
- `/stats_seed_test` — seed test data (Founder).
- `/payroll` — mentor payroll calculation.

---

## Setup

### Environment Variables
- `DISCORD_TOKEN` — bot token.
- `DATABASE_URL` — PostgreSQL connection string.
- `GUILD_ID` — target Discord server ID.
- `DASHBOARD_SECRET` — long random token for the web dashboard login (`https://<your-service>.onrender.com/dashboard`).
- `FLASK_SECRET_KEY` — optional; cookie signing (defaults to `DASHBOARD_SECRET`).
- `DASHBOARD_DB_QUOTA_BYTES` — optional; database size quota in bytes for the System tab (default ~512 MiB, e.g. Neon free tier).
- `EVENT_TEMPLATES_PATH` — optional; absolute path to `events_templates.txt` if not beside `bot.py`.

### Deployment (Render)
1. Connect your GitHub repository.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python bot.py`
4. Health check: `GET /` (from `keep_alive.py`). Analytics UI: `GET /dashboard` (log in with `DASHBOARD_SECRET`).
