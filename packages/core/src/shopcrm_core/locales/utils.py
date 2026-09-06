# locales/utils.py

class SafeDict(dict):
    """Словарь для безопасного format_map(), защищает от KeyError."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
