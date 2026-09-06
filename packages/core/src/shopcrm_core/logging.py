import sys
from pathlib import Path
from loguru import logger

# Определяем путь к папке logs в корне проекта
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Полностью очищаем стандартные обработчики loguru
logger.remove()

# 1. Настройка вывода в консоль (для разработки и дебага в реальном времени)
logger.add(
    sys.stdout,
    level="DEBUG",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True
)

# 2. Основной файл логов (общий поток INFO и выше)
# Ротация по достижении 5 МБ, храним максимум 5 последних файлов
logger.add(
    LOGS_DIR / "app.log",
    rotation="5 MB",
    retention=5,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    encoding="utf-8",
    enqueue=True  # Безопасно для асинхронного кода
)

# 3. Отдельный файл для критических ошибок и ошибок (ERROR и выше)
# Помогает быстро находить баги, не копаясь в тоннах обычных логов
logger.add(
    LOGS_DIR / "errors.log",
    rotation="5 MB",
    retention=5,
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
    encoding="utf-8",
    enqueue=True
)

__all__ = ["logger"]