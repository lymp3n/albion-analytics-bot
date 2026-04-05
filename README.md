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
| **System** | Краткий **статус связи бота с Discord** (понятная плашка для не-разработчиков), оценка занятого места в БД относительно квоты (см. `DASHBOARD_DB_QUOTA_BYTES`), время ответа БД, аптайм HTTP и развёрнутый JSON для диагностики. |
| **Role assist** | Переопределение Discord role ID для уровней member / mentor / founder **по гильдии в БД**; пустое поле = как в `config.yaml` + встроенные доп. ID. Подгрузка имён ролей с сервера кнопкой **Load role names** (см. «Недавние обновления дашборда»). Без редеплоя. |

**Недавние обновления дашборда**

- **Экран загрузки** — перед первым ответом `/dashboard/api/data` и при каждом **Refresh data** показывается полноэкранный слой (бренд, спиннер, краткий текст; плавное скрытие после ответа сервера).
- **Страница входа** — над формой токена отображается GIF **`/video/secret.gif`**; файл лежит в репозитории как `video/secret.gif` (можно заменить своим).
- **Блокировка / rate limit Discord** — если процесс бота фиксирует глобальный 429 или аналог при подключении, дашборд после загрузки данных может показать полноэкранное предупреждение с **`/video/ban.gif`** (`video/ban.gif` в репо). Кнопка ведёт только на вкладку **System**; остальные вкладки скрыты, пока флаг активен. После **Refresh** экран снова появится, если ограничение ещё действует.
- **Role assist / имена ролей** — запрос имён к Discord выполняется **отдельно для каждой гильдии** (несколько серверов можно обрабатывать параллельно). При успешной загрузке ячейки имён **обновляются** из ответа API (не только пустые поля).

Статические GIF раздаются маршрутом **`/video/<имя>`** для файлов из белого списка (`ban.gif`, `secret.gif`).

**Логи: `rate limited ... /applications/.../commands`.** Discord ограничивает частоту **регистрации slash-команд**. Сообщение означает, что запрос временно отклонён — клиент подождёт и повторит попытку. Чтобы снизить нагрузку: задайте **`GUILD_IDS`** / **`GUILD_ID`** — синк только для этих серверов; синхронизация **одним** вызовом для всего списка (без цикла по гильдиям, чтобы не множить служебные запросы к API). После **успешного** синка бот сохраняет в БД отпечаток дерева команд и при следующих перезапусках **пропускает** повторный `sync_commands`, пока код команд или список целевых гильдий не изменились (экономия запросов к API). Чтобы принудительно зарегистрировать команды снова: **`DISCORD_FORCE_COMMAND_SYNC=1`** на один запуск. Опционально **`DISCORD_COMMAND_SYNC_DEFER_SEC`**, **`DISCORD_COMMAND_SYNC_JITTER_SEC`** (случайная пауза 0…N с перед синком) и **`DISCORD_SKIP_COMMAND_SYNC=1`** только для отладки.

**Логи: HTML Cloudflare, `Error 1015`, «You are being rate limited» на discord.com.** Это **блокировка исходящего IP** вашего хостинга (часто у датацентров), а не обычный лимит API. Код бота это не обходит: подождите (иногда до суток), смените **регион** или провайдера (другой egress IP), убедитесь, что с токеном работает **один** процесс. Между попытками входа бот делает **длинную** паузу; интервал задаётся **`DISCORD_CF1015_RETRY_AFTER_SEC`** (по умолчанию 3600 с).

**GIF на входе и на экране блокировки.** Тяжёлые GIF могут подлагивать при первом кадре: для входа включён **preload** `secret.gif`, на обеих страницах показывается **плейсхолдер со спиннером** фиксированного размера до загрузки картинки, затем плавное появление GIF.

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
| **Role assist** | Override Discord role IDs for member / mentor / founder tiers **per DB guild**; blank field inherits `config.yaml` + built-in extras. **Load role names** pulls labels from Discord (see **Recent dashboard updates** below). No redeploy. |
| **System** | Plain-language **Discord bot connectivity** hint, database size vs quota (`DASHBOARD_DB_QUOTA_BYTES`), DB round-trip time, HTTP uptime, and raw JSON for deeper checks. |

**Recent dashboard updates**

- **Boot screen** — a full-viewport loading layer (brand, spinner, short status copy) shows until `/dashboard/api/data` returns, and again on every **Refresh data**; it fades out when the response is handled.
- **Login page** — optional hero GIF at **`/video/secret.gif`** (`video/secret.gif` in the repo; replace with your asset).
- **Discord API block / rate limit** — when the bot process records a startup-level global 429 (or similar), the dashboard can show a full-screen notice with **`/video/ban.gif`** (`video/ban.gif`). A button opens **only the System tab**; other tabs stay hidden while the flag is set. **Refresh** shows the screen again if the block is still active.
- **Role assist / role names** — Discord role-name fetches run **per guild card** (you can load several servers in parallel). Successful loads **overwrite** name cells from the API, not only empty ones.

GIFs are served from **`/video/<filename>`** for an allowlisted set (`ban.gif`, `secret.gif`).

**Login / ban GIF UX.** Large GIFs can stutter on first decode; the login page **preloads** `secret.gif` and both pages show a **spinner placeholder** in a fixed-size slot until the image has loaded, then fade the GIF in.

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
- `GUILD_ID` / `GUILD_ID2` — legacy target Discord server ID(s).
- `GUILD_IDS` — optional comma- or space-separated guild IDs. **Recommended** when the bot is in **multiple** servers: slash commands are registered **only** for these guilds (plus legacy `GUILD_ID`/`GUILD_ID2`), which greatly reduces Discord **application command** rate limits on startup.
- `DISCORD_COMMAND_SYNC_DEFER_SEC` — optional; seconds to sleep in `on_ready` before syncing slash commands (spread load after deploys).
- `DISCORD_COMMAND_SYNC_JITTER_SEC` — optional; e.g. `20` adds a random **0…20s** sleep before sync so multiple instances or quick redeploys don’t hit the command API at the same instant.
- `DISCORD_SKIP_COMMAND_SYNC` — optional; set to `1` / `true` to skip slash command registration for this run (debug only).
- `DISCORD_FORCE_COMMAND_SYNC` — optional; set to `1` / `true` to always run `sync_commands` and refresh the stored fingerprint (use after changing slash commands, or if Discord’s copy is out of sync).
- `DISCORD_CF1015_RETRY_AFTER_SEC` — optional; when Discord’s edge returns **Cloudflare error 1015** (temporary **IP ban** for your host’s egress), the bot waits this many seconds between login attempts (default **3600**). Shorter retries do not unblock the IP; change region/provider or wait it out.
- `DASHBOARD_SECRET` — long random token for the web dashboard login (`https://<your-service>.onrender.com/dashboard`).
- `FLASK_SECRET_KEY` — optional; cookie signing (defaults to `DASHBOARD_SECRET`).
- `DASHBOARD_DB_QUOTA_BYTES` — optional; database size quota in bytes for the System tab (default ~512 MiB, e.g. Neon free tier).
- `EVENT_TEMPLATES_PATH` — optional; absolute path to `events_templates.txt` if not beside `bot.py`.

### Logs: `rate limited ... /applications/.../commands`

Discord limits how often **slash commands** can be registered. The library will back off (sometimes hundreds of seconds) when that limit is hit.

This bot registers commands **once** after login (`on_ready`). To avoid unnecessary API traffic:

- Set **`GUILD_IDS`** (and/or `GUILD_ID`) to the Discord server id(s) you actually use. The bot **does not** sync commands to every server it was invited to when these env vars are set.
- The bot disables **automatic** sync on every `on_connect` and runs **one** `sync_commands` call in `on_ready` for the whole guild list (splitting into a per-guild loop would repeat Discord’s internal global-command checks and **worsen** rate limits).
- Optional **`DISCORD_COMMAND_SYNC_DEFER_SEC`** (e.g. `5`–`30`) — fixed wait after `on_ready` before syncing.
- Optional **`DISCORD_COMMAND_SYNC_JITTER_SEC`** (e.g. `15`–`30`) — extra random **0…N** second delay so staggered deploys don’t synchronize on the same API window.
- Optional **`DISCORD_SKIP_COMMAND_SYNC=1`** — skip registration for this process (debug only; slash commands may be missing until you unset it and redeploy).
- After a **successful** sync, the bot stores a **fingerprint** of the slash command tree and guild/global sync mode in the database (`bot_kv`). On later startups it **skips** `sync_commands` when nothing changed, which cuts Discord application-command API traffic. Set **`DISCORD_FORCE_COMMAND_SYNC=1`** for one run after you edit commands or if the developer portal / Discord state diverged (e.g. you only changed a description).
- **Cloudflare 1015 / “You are being rate limited” HTML from discord.com** means Discord blocked your **server’s public IP**, not a normal REST 429. Fix: wait (often hours), redeploy to another **region** or host, ensure **one** bot process per token. The bot uses a **long** retry (see `DISCORD_CF1015_RETRY_AFTER_SEC`) so it does not hammer the edge while banned.
- Avoid rapid restart loops (e.g. crash → restart) while developing.

### Deployment (Render)
1. Connect your GitHub repository.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python bot.py`
4. Health check: `GET /` (from `keep_alive.py`). Analytics UI: `GET /dashboard` (log in with `DASHBOARD_SECRET`).

**Port check:** The HTTP server starts **before** the Discord client and heavy cog imports (e.g. matplotlib for `/stats`), so Render’s port probe should see `$PORT` open quickly. Use a **single** Web Service instance unless you know how to avoid duplicate Discord sessions.

