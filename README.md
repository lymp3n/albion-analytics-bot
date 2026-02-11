# 🎮 Albion Analytics Bot

A professional coaching and analytics solution for Albion Online guilds and alliances. This bot streamlines session reviews, tracks player performance with high-quality visualizations, and automates mentor rewards.

---

## 🌍 Language Support
This bot is fully localized in **English**. All commands, charts, and internal logs are in English to support global alliance environments.

---

## ✨ Key Features / Основные функции

### 1. 🎫 Session Review System (Tickets)
- **Automated Workflow**: Players create tickets for session reviews (ZvZ, Crystals, etc.).
- **Dynamic Channels**: Each ticket gets a private channel for communication between the player and mentor.
- **Persistence**: Replay links and session descriptions are permanently stored and formatted into clean embeds.
- **Auto-Cleanup**: Channels are automatically deleted after a successful evaluation to prevent clutter.

### 2. 📊 Advanced Player Dashboard
- **Single Infographic**: All stats are combined into a high-quality dashboard image.
- **Montserrat Typography**: Professional look using the Montserrat font.
- **Insights include**:
  - **Global Rank**: See where you stand in the whole guild.
  - **Score Trends**: Track your growth over weeks.
  - **Role Mastery**: Identify your strongest roles.
  - **Error Distribution**: Learn from your most common mistakes.

### 3. 💰 Professional Payroll System
- **Activity Tracking**: Track mentor performance across 7-day, 14-day, and all-time windows.
- **Fair Distribution**: Automatically calculate silver rewards based on the volume of reviewed sessions.
- **Transparency**: Detailed breakdowns for each mentor's share of the budget.

---

## 🇷🇺 Справка для пользователей (Russian)

### Начало работы
1.  **Регистрация**: Используйте `/register <code>`, чтобы привязать свой Discord к гильдии. Код выдается основателем (Founder).
2.  **Главное меню**: Используйте `/menu`, чтобы быстро получить доступ к созданию тикетов и статистике.

### Просмотр игр (Тикеты)
- Чтобы отправить игру на разбор, нажмите "Create Ticket" в меню или используйте `/ticket create`.
- Укажите ссылку на реплей и вашу роль. Бот создаст отдельный канал для общения с ментором.
- После того как ментор оценит игру, вы получите уведомление в ЛС с подробным фидбеком и оценкой.

### Статистика
- Команда `/stats` выводит вашу полную карточку игрока. 
- На ней отображается ваш рейтинг (Rank), средний балл (Avg Score) и подробные графики ваших успехов и ошибок.

---

## 🇬🇧 User Guide (English)

### Getting Started
1.  **Registration**: Use `/register <code>` to link your Discord account to the guild. Codes are provided by the Guild Founder.
2.  **Main Menu**: Use `/menu` for quick access to ticket creation and your statistics.

### Session Reviews (Tickets)
- To submit a session for review, click "Create Ticket" in the menu or use `/ticket create`.
- Provide the replay link and your role. The bot will create a dedicated channel for your review.
- Once a mentor evaluates your session, you will receive a DM with detailed feedback and your score.

### Statistics
- The `/stats` command generates your comprehensive player dashboard.
- It displays your Global Rank, Average Score, and detailed visualizations of your performance and recurring errors.

---

## 🛠 Commands Reference / Список команд

| Command | Description (English) | Описание (Russian) | Access |
| :--- | :--- | :--- | :--- |
| `/menu` | Bot's main control panel | Главная панель управления | Member |
| `/register` | Link Discord to Guild | Регистрация в гильдии | All |
| `/stats` | View player dashboard | Карточка статистики игрока | Member |
| `/ticket create` | Open a review ticket | Создать заявку на разбор | Member |
| `/ticket list` | View active reviews | Список активных заявок | Mentor |
| `/payroll` | Calculate mentor rewards | Расчет выплат менторам | Founder |
| `/admin` | System management | Управление системой | Founder |

---

## ⚙️ Technical Setup / Техническая настройка

### Environment Variables
- `DISCORD_TOKEN`: Your bot application token.
- `DATABASE_URL`: Connection string (PostgreSQL recommended for production).
- `GUILD_ID`: Your target Discord server ID.

### Deployment (Render.com)
1.  **Web Service**: Connect your GitHub repository.
2.  **Build Command**: `pip install -r requirements.txt`
3.  **Start Command**: `python bot.py`
4.  **Health Check**: Route `/` is available via `keep_alive.py` to maintain uptime.

---
*Created by Albion Analytics. Empowering guilds through data-driven coaching.*
