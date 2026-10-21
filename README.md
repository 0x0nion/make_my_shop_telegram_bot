# SHOPCRM

Telegram-бот для управления небольшим магазином: каталог, корзина, заказы, оплата и админ-панель — всё в одном чате.

**Язык / Language / Idioma:** [Русский](README.md) | [English](README.en.md) | [Español](README.es.md)

## Ресурсы

- 🤖 **Бот:** [@make_my_shop_bot](https://t.me/make_my_shop_bot)
- 🌐 **Сайт:** [needl3.net](https://needl3.net/)

## Возможности

- **Каталог товаров** — категории, поиск, карточки с фото и ценой
- **Корзина** — добавление, изменение количества, удаление
- **Оформление заказа** — адрес доставки, комментарий, итоговая сумма
- **Оплата** — прикрепление чека (фото / текст), подтверждение админом
- **История заказов** — статусы, чат с поддержкой по каждому заказу
- **Админ-панель** — управление товарами, категориями, статусами заказов
- **Мультиязычность** — RU / EN / ES (переключается в боте)

## Требования

- Python **3.11+**
- SQLite (по умолчанию) или PostgreSQL 14+ для продакшена

## Установка

```bash
# 1. Клонируем
git clone <repo-url> shopcrm
cd shopcrm

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Зависимости
pip install -e packages/core -e apps/bot

# 4. Конфигурация
cp .env.example .env
# Откройте .env и заполните значения
```

## Конфигурация

Все настройки задаются через переменные окружения (файл `.env`):

| Переменная      | Описание                                      | Пример / по умолчанию          |
|-----------------|-----------------------------------------------|--------------------------------|
| `BOT_TOKEN`     | Токен Telegram-бота (от @BotFather)           | —                              |
| `DATABASE_URL`  | Строка подключения БД (async)                 | `postgresql+asyncpg://user:pass@localhost/shopcrm` |
| `ADMIN_ID`      | Telegram ID администраторов (список)          | `[123456789]`                  |
| `LOG_LEVEL`     | Уровень логирования                           | `INFO`                         |
| `DEBUG`         | Режим отладки                                 | `false`                        |
| `FSM_STORAGE`   | Хранилище FSM: `memory` или `redis`           | `memory`                       |
| `REDIS_URL`     | URL Redis (только при `FSM_STORAGE=redis`)    | `redis://localhost:6379/0`     |
| `MANAGER_URL`   | URL менеджера (кнопка в карточке товара); если пусто — кнопка скрыта | `https://t.me/your_manager` |
| `LOGS_DIR`      | Каталог для лог-файлов                        | `logs`                         |

## Запуск

```bash
# 1. Миграции БД
alembic upgrade head

# 2. Бот
python -m shopcrm_bot
```

Бот стартует в режиме long polling. Для остановки — `Ctrl+C`.

## Схема БД

- **Продакшен / внешние сервисы** — схема управляется миграциями: `alembic upgrade head`.
  Цепочка миграций синхронизирована с моделями `shopcrm_core` (autogenerate).
- **Локальная разработка** — при `DEBUG=true` бот сам создаёт/дополняет таблицы
  через `create_all` (миграции не обязательны).
- **Внешний сервис** (админ-панель и т.п.) — `shopcrm-core` используется как
  библиотека: движок и сессии создаются фабриками из `shopcrm_core.db.connection`,
  а метаданные для собственных миграций — через `shopcrm_core.db.get_metadata()`.

## Встраивание админ-секции во внешнее приложение

Для hosting-платформ и других приложений, которые переиспользуют редактор
магазина (каталог/товары/приветствие/заказы) без запуска полноценного core-бота.

### Подключение

```python
from aiogram import Dispatcher
from shopcrm_bot.embedding import (
    extract_admin_group_router,
    is_admin_shop_callback,
)

dp = Dispatcher()
dp.include_router(extract_admin_group_router())
```

`extract_admin_group_router()` открепляет `admin_group_router` от дерева
core-бота и возвращает его. Функция идемпотентна. После вызова core-бот в том
же процессе админ-секцию не получит — не запускайте core-бота рядом.

### DI-контракт

Хэндлеры админ-секции ожидают в workflow data (middleware внешнего
приложения обязан их поставить для callback'ов редактора):

| Ключ            | Тип                | Описание                                        |
|-----------------|--------------------|-------------------------------------------------|
| `admin_repo`    | `AdminRepository`  | репозиторий магазина (сессия нужной схемы)      |
| `admin_service` | `AdminShopService` | сервис магазина (обёртка над репозиторием)      |
| `user`          | `User`             | текущий админ (модель `shopcrm_core`)           |
| `locale`        | `Locale`           | локаль (`shopcrm_core.locales`)                 |
| `admin_ids`     | `list[int]`        | id админов (для `IsAdminFilter`)                |

### Callback-гейтинг

Используйте `is_admin_shop_callback(data)` (или константу
`ADMIN_SHOP_CALLBACK_PREFIXES`) для решения, на какие callback'ы создавать
сессию схемы и DI-объекты. Список префиксов живёт в ядре — единый источник
истины, дублировать его во внешнем приложении не нужно.

`admin_main_menu` (кнопка возврата в меню) в список не входит — её перехватывает
внешнее приложение само.

### FSM-состояния

Редактор использует группы: `AdminState`, `EditProduct`, `EditWelcome`,
`AdminOrderState`, `EditPaymentDetails`, `AdminContactStates`. Внешнее
приложение должно использовать тот же FSM storage, что и core-бот, если они
работают с одними пользователями.

## Лицензия

[MIT](LICENSE)

