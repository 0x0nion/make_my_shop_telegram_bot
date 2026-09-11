from deep_translator import GoogleTranslator


class LiveTranslator:
    def __init__(self):
        self.to_en = GoogleTranslator(source='auto', target='en')
        self.to_es = GoogleTranslator(source='auto', target='es')
        self.to_ru = GoogleTranslator(source='auto', target='ru')

    def translate_all(self, text: str) -> dict:
        """Переводит входящий текст сразу на три языка и возвращает словарь."""
        if not text.strip():
            return {"en": "", "es": "", "ru": ""}

        return {
            "en": self.to_en.translate(text),
            "es": self.to_es.translate(text),
            "ru": self.to_ru.translate(text)
        }


# --- Пример использования ---
if __name__ == "__main__":
    translator = LiveTranslator()

    user_input = "Привет, как твои дела? Что делаешь сегодня вечером?"

    translations = translator.translate_all(user_input)

    print("Оригинал:", user_input)
    print("EN:", translations["en"])  # Hello, how are you? What are you doing tonight?
    print("ES:", translations["es"])  # Hola, ¿cómo estás? ¿Qué haces esta noche?
    print("RU:", translations["ru"])  # Привет, как твои дела? Что делаешь сегодня вечером?