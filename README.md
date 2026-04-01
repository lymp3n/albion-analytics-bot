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

### Deployment (Render)
1. Connect your GitHub repository.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python bot.py`
4. Health endpoint is provided by `keep_alive.py`.
