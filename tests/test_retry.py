"""Тесты утилиты retry_async с экспоненциальным backoff."""
import pytest

from shopcrm_core.utils.retry import (
    RetryConfig,
    TransientError,
    is_transient,
    retry_async,
)


class TestIsTransient:
    """Определение временных ошибок."""

    def test_transient_error_is_transient(self):
        assert is_transient(TransientError("x")) is True

    def test_connection_error_is_transient(self):
        assert is_transient(ConnectionError("x")) is True

    def test_timeout_error_is_transient(self):
        assert is_transient(TimeoutError("x")) is True

    def test_value_error_is_not_transient(self):
        assert is_transient(ValueError("x")) is False

    def test_extra_types_are_transient(self):
        class CustomError(Exception):
            pass

        assert is_transient(CustomError("x"), extra=(CustomError,)) is True
        assert is_transient(CustomError("x")) is False


class TestRetryAsync:
    """Повторные попытки с backoff."""

    async def test_success_first_attempt(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            return "ok"

        result = await retry_async(op, config=RetryConfig(max_attempts=3))
        assert result == "ok"
        assert calls == 1

    async def test_retries_on_transient_then_succeeds(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("boom")
            return "recovered"

        result = await retry_async(
            op, config=RetryConfig(max_attempts=5, base_delay=0.0, jitter=0.0)
        )
        assert result == "recovered"
        assert calls == 3

    async def test_raises_after_max_attempts(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            raise ConnectionError("boom")

        with pytest.raises(ConnectionError):
            await retry_async(
                op, config=RetryConfig(max_attempts=3, base_delay=0.0, jitter=0.0)
            )
        assert calls == 3

    async def test_non_transient_raises_immediately(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            raise ValueError("bad")

        with pytest.raises(ValueError):
            await retry_async(op, config=RetryConfig(max_attempts=5, base_delay=0.0))
        assert calls == 1

    async def test_retry_on_custom_type(self):
        class FlakyError(Exception):
            pass

        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise FlakyError("flaky")
            return "done"

        result = await retry_async(
            op,
            config=RetryConfig(max_attempts=3, base_delay=0.0, jitter=0.0),
            retry_on=(FlakyError,),
        )
        assert result == "done"
        assert calls == 2
