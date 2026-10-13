# SHOPCRM

A Telegram bot for managing a small shop: catalog, cart, orders, payment and an admin panel — all in one chat.

**Язык / Language / Idioma:** [Русский](README.md) | [English](README.en.md) | [Español](README.es.md)

## Resources

- 🤖 **Bot:** [@make_my_shop_bot](https://t.me/make_my_shop_bot)
- 🌐 **Website:** [needl3.net](https://needl3.net/)

## Features

- **Product catalog** — categories, search, cards with photo and price
- **Cart** — add, change quantity, remove
- **Checkout** — delivery address, comment, total amount
- **Payment** — attaching a receipt (photo / text), confirmation by the admin
- **Order history** — statuses, support chat for each order
- **Admin panel** — managing products, categories, order statuses
- **Multilingual** — RU / EN / ES (switchable in the bot)

## Requirements

- Python **3.11+**
- SQLite (default) or PostgreSQL 14+ for production

## Installation

```bash
# 1. Clone
git clone <repo-url> shopcrm
cd shopcrm

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Dependencies
pip install -e packages/core -e apps/bot

# 4. Configuration
cp .env.example .env
# Open .env and fill in the values
```

## Configuration

All settings are provided via environment variables (`.env` file):

| Variable        | Description                                       | Example / default                  |
|-----------------|---------------------------------------------------|------------------------------------|
| `BOT_TOKEN`     | Telegram bot token (from @BotFather)              | —                                  |
| `DATABASE_URL`  | DB connection string (async)                      | `postgresql+asyncpg://user:pass@localhost/shopcrm` |
| `ADMIN_ID`      | Telegram IDs of the administrators (list)         | `[123456789]`                      |
| `LOG_LEVEL`     | Logging level                                     | `INFO`                             |
| `DEBUG`         | Debug mode                                        | `false`                            |
| `FSM_STORAGE`   | FSM storage: `memory` or `redis`                  | `memory`                           |
| `REDIS_URL`     | Redis URL (only when `FSM_STORAGE=redis`)         | `redis://localhost:6379/0`         |
| `MANAGER_URL`   | Manager URL (button on the product card); if empty — the button is hidden | `https://t.me/your_manager` |
| `LOGS_DIR`      | Directory for log files                           | `logs`                             |

## Running

```bash
# 1. DB migrations
alembic upgrade head

# 2. Bot
python -m shopcrm_bot
```

The bot starts in long polling mode. To stop it — `Ctrl+C`.

## DB Schema

- **Production / external services** — the schema is managed by migrations: `alembic upgrade head`.
  The migration chain is in sync with the `shopcrm_core` models (autogenerate).
- **Local development** — with `DEBUG=true` the bot creates/extends the tables
  itself via `create_all` (migrations are not required).
- **External service** (admin panel, etc.) — `shopcrm-core` is used as a
  library: the engine and sessions are created by the factories from
  `shopcrm_core.db.connection`, and the metadata for your own migrations —
  via `shopcrm_core.db.get_metadata()`.

## License

[MIT](LICENSE)
