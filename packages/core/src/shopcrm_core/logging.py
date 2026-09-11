"""Единая настройка логирования SHOPCRM.

loguru — единственный логгер приложения:
  - цветной вывод в консоль (для разработки и дебага);
  - ротируемый файл app.log (общий поток, уровень настраивается);
  - отдельный файл errors.log (ERROR и выше, с полным traceback).

Стандартный `logging` (используется в разных модулях) маршрутизируется
в loguru через InterceptHandler, поэтому все записи попадают в один поток.
"""
import logging
import sys
from pathlib import Path
from typing import Union

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"


class _InterceptHandler(logging.Handler):
    """Перенаправляет записи стандартного `logging` в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Переводим уровень stdlib в уровень loguru.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Подставляем реальный caller из stdlib LogRecord в loguru record.
        # (depth через InterceptHandler не может точно определить caller,
        #  а LogRecord уже содержит pathname/funcName/lineno.)
        def _patch(rec):
            rec["name"] = Path(record.pathname).name
            rec["function"] = record.funcName
            rec["line"] = record.lineno
            return rec

        logger.patch(_patch).opt(exception=record.exc_info).log(level, record.getMessage())


def setup_logging(level: str = "INFO", logs_dir: Union[str, Path] = "logs") -> None:
    """Настраивает loguru и маршрутизирует stdlib logging в него.

    Идиотентична: повторный вызов пересоздаёт обработчики.

    :param level: минимальный уровень для консоли и app.log (например, "INFO").
    :param logs_dir: папка для ротируемых файлов логов.
    """
    level = (level or "INFO").upper()
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)

    logger.remove()

    # 1. Консоль (цветной вывод для разработки и дебага в реальном времени).
    logger.add(
        sys.stdout,
        level=level,
        format=_CONSOLE_FORMAT,
        colorize=True,
    )

    # 2. Основной файл (общий поток, ротация 5 МБ, храним 5 последних).
    logger.add(
        logs_path / "app.log",
        rotation="5 MB",
        retention=5,
        level=level,
        format=_FILE_FORMAT,
        encoding="utf-8",
        enqueue=True,  # Безопасно для асинхронного кода
    )

    # 3. Отдельный файл для ошибок (ERROR и выше, с полным traceback).
    logger.add(
        logs_path / "errors.log",
        rotation="5 MB",
        retention=5,
        level="ERROR",
        format=_FILE_FORMAT + "\n{exception}",
        encoding="utf-8",
        enqueue=True,
    )

    # Маршрутизируем стандартный logging в loguru (единый поток записей).
    root = logging.getLogger()
    root.handlers = [_InterceptHandler()]
    root.setLevel(level)


def shutdown_logging() -> None:
    """Грациозно закрывает loguru-синки.

    Ожидает завершения enqueue-потоков (все отложенные записи дописаны в файлы),
    затем удаляет все обработчики. Вызывается при остановке приложения.
    """
    try:
        logger.complete()
    except Exception:  # noqa: BLE001 — shutdown не должен падать
        pass
    logger.remove()


__all__ = ["logger", "setup_logging", "shutdown_logging"]