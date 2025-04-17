import requests  # 💬 Для отправки запросов в Telegram API

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        self.token = token
        self.chat_id = chat_id

    def set_credentials(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, message):
        if not self.token or not self.chat_id:
            print("[⚠️ Ошибка]: Не указаны token или chat_id!")
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            response = requests.post(url, data={"chat_id": self.chat_id, "text": message})
            if response.status_code != 200:
                print(f"[❌ Telegram ошибка {response.status_code}]: {response.text}")
            else:
                print(f"📨 Уведомление отправлено: {message}")
        except Exception as e:
            print(f"[⚠️ Telegram Error]: {e}")
