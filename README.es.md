# SHOPCRM

Bot de Telegram para gestionar una tienda pequeña: catálogo, carrito, pedidos, pago y panel de administración — todo en un solo chat.

**Язык / Language / Idioma:** [Русский](README.md) | [English](README.en.md) | [Español](README.es.md)

## Recursos

- 🤖 **Bot:** [@make_my_shop_bot](https://t.me/make_my_shop_bot)
- 🌐 **Sitio web:** [needl3.net](https://needl3.net/)

## Funciones

- **Catálogo de productos** — categorías, búsqueda, tarjetas con foto y precio
- **Carrito** — añadir, cambiar cantidad, eliminar
- **Finalizar pedido** — dirección de entrega, comentario, importe total
- **Pago** — adjuntar comprobante (foto / texto), confirmación por el administrador
- **Historial de pedidos** — estados, chat de soporte para cada pedido
- **Panel de administración** — gestión de productos, categorías y estados de pedidos
- **Multilingüe** — RU / EN / ES (cambiable en el bot)

## Requisitos

- Python **3.11+**
- SQLite (por defecto) o PostgreSQL 14+ para producción

## Instalación

```bash
# 1. Clonar
git clone <repo-url> shopcrm
cd shopcrm

# 2. Entorno virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Dependencias
pip install -e packages/core -e apps/bot

# 4. Configuración
cp .env.example .env
# Abre .env y completa los valores
```

## Configuración

Todas las configuraciones se definen mediante variables de entorno (archivo `.env`):

| Variable        | Descripción                                       | Ejemplo / por defecto              |
|-----------------|---------------------------------------------------|------------------------------------|
| `BOT_TOKEN`     | Token del bot de Telegram (de @BotFather)         | —                                  |
| `DATABASE_URL`  | Cadena de conexión a la BD (async)                | `postgresql+asyncpg://user:pass@localhost/shopcrm` |
| `ADMIN_ID`      | IDs de Telegram de los administradores (lista)    | `[123456789]`                      |
| `LOG_LEVEL`     | Nivel de registro                                 | `INFO`                             |
| `DEBUG`         | Modo de depuración                                | `false`                            |
| `FSM_STORAGE`   | Almacenamiento FSM: `memory` o `redis`            | `memory`                           |
| `REDIS_URL`     | URL de Redis (solo con `FSM_STORAGE=redis`)       | `redis://localhost:6379/0`         |
| `MANAGER_URL`   | URL del gestor (botón en la tarjeta del producto); si está vacío — el botón se oculta | `https://t.me/your_manager` |
| `LOGS_DIR`      | Directorio para los archivos de registro          | `logs`                             |

## Ejecución

```bash
# 1. Migraciones de la BD
alembic upgrade head

# 2. Bot
python -m shopcrm_bot
```

El bot arranca en modo long polling. Para detenerlo — `Ctrl+C`.

## Esquema de la BD

- **Producción / servicios externos** — el esquema se gestiona con migraciones: `alembic upgrade head`.
  La cadena de migraciones está sincronizada con los modelos de `shopcrm_core` (autogenerate).
- **Desarrollo local** — con `DEBUG=true` el bot crea/amplía las tablas
  él mismo mediante `create_all` (las migraciones no son obligatorias).
- **Servicio externo** (panel de administración, etc.) — `shopcrm-core` se usa como
  biblioteca: el motor y las sesiones se crean con las fábricas de
  `shopcrm_core.db.connection`, y los metadatos para tus propias migraciones —
  mediante `shopcrm_core.db.get_metadata()`.

## Licencia

[MIT](LICENSE)
