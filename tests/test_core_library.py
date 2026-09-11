"""Тесты: core — чистая библиотека (инжект движка/сессий, импорт без env).

До рефактора импорт ``shopcrm_core`` требовал env-переменные (модульный
``Settings()`` и ``create_async_engine``). Теперь core — библиотека:
импорт безопасен, движок и фабрика сессий создаются фабриками.
"""
import os
import subprocess
import sys

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker


def test_create_engine_and_session_factory():
    """Фабрики движка/сессий работают без env-переменных."""
    from shopcrm_core.db.connection import create_engine, create_session_factory

    engine = create_engine("sqlite+aiosqlite:///:memory:")
    assert isinstance(engine, AsyncEngine)

    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)


def test_import_core_without_env_vars():
    """Импорт core работает в чистом env (без BOT_TOKEN/DATABASE_URL/ADMIN_ID)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("BOT_TOKEN", "DATABASE_URL", "ADMIN_ID")
    }
    env["PYTHONPATH"] = os.pathsep.join(
        [
            os.path.join(repo_root, "packages", "core", "src"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    code = (
        "import shopcrm_core; "
        "import shopcrm_core.db.connection; "
        "import shopcrm_core.config"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert result.returncode == 0, f"import failed: {result.stderr}"
