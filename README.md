# SHOPCRM

Monorepo CRM-приложения: Telegram-бот (aiogram) + общее ядро + задел под веб-приложение.

## Структура

```
apps/
├── bot/                  # Telegram-бот (aiogram)
│   ├── pyproject.toml    # пакет shopcrm-bot
│   └── src/shopcrm_bot/
│       ├── main.py       # точка входа: python -m shopcrm_bot
│       ├── handlers/     # хэндлеры (admin / client)
│       ├── middlewares/  # aiogram-мидлвары (сессии БД)
│       ├── filters/      # фильтры (IsAdminFilter)
│       ├── keyboards/    # фабрика inline-клавиатур
│       ├── states/       # FSM-состояния
│       ├── services/     # бот-сервисы (уведомления в Telegram)
│       ├── ui/           # UIManager + пресентеры экранов
│       └── locales.py    # BotLocale = Locale(core) + keyboards
└── web/                  # плейсхолдер будущего веб-приложения

packages/
└── core/                 # общее ядро (без зависимостей от Telegram)
    ├── pyproject.toml    # пакет shopcrm-core
    └── src/shopcrm_core/
        ├── config.py     # настройки (pydantic-settings, .env)
        ├── constants.py  # доменные константы (статусы, типы)
        ├── logging.py    # логгер (loguru)
        ├── db/           # SQLAlchemy: models, repositories, connection
        ├── locales/      # locale.json + Locale (тексты, валюты, единицы)
        └── services/     # бизнес-логика (заказы, магазин, адреса)

alembic/                  # миграции БД (версионируются!)
alembic.ini
pyproject.toml            # конфиг инструментов (ruff, pytest)
requirements.txt          # runtime-зависимости (справочно)
```

## Правило зависимостей

```
shopcrm-bot  ->  shopcrm-core  ->  (sqlalchemy, pydantic, ...)
```

- `shopcrm_bot` **может** импортировать `shopcrm_core`.
- `shopcrm_core` **не должен** импортировать aiogram и любой бот-код.
- Будущее веб-приложение (`apps/web`) зависит от `shopcrm_core`, но не от `shopcrm_bot`.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e packages/core -e apps/bot
cp .env.example .env   # заполнить BOT_TOKEN, DATABASE_URL, ADMIN_ID
```

## Запуск

```bash
# миграции
alembic upgrade head

# бот
python -m shopcrm_bot
```

## Переменные окружения

| Переменная   | Описание                                    | По умолчанию |
|--------------|---------------------------------------------|--------------|
| `BOT_TOKEN`  | Токен Telegram-бота                         | —            |
| `DATABASE_URL` | Строка подключения БД (async)             | —            |
| `ADMIN_ID`   | ID администраторов (список через запятую)   | —            |
| `LOG_LEVEL`  | Уровень логирования                         | `INFO`       |
| `DEBUG`      | Режим отладки                               | `False`      |

