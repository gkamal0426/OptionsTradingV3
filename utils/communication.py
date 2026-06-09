import requests
import os
import threading
import logging
import queue
from variables.start_from_here import to_start_get
from utils.setuplogger import _filepath
from dotenv import load_dotenv
from datetime import datetime
import json


class CallTelegram:
    def __init__(self, env_files = None):
        if not isinstance(env_files, list) or not env_files:
            env_files = ["client1", "client2", "ksem"]
        self.message_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.chat_id, self.bot_token = self._resolve_credentials(env_files)

    @staticmethod
    def _resolve_credentials(env_files):
        for env_file in env_files:
            load_dotenv(to_start_get(env_file))
            ci, bt = os.getenv("ci"), os.getenv("bt")
            if ci and bt:
                return ci, bt
        return None, None



    def _connect_telegram_server(self, message, i):
        if not (self.chat_id and self.bot_token):
            return None
        try:
            url = f'https://api.telegram.org/bot{self.bot_token}/sendMessage'
            payload = {'chat_id': self.chat_id, 'text': message}
            response = requests.post(url, data=payload, timeout=30)
            return response.json()
        except Exception as e:
            logging.exception(f"❌ attempt {i+1} Exception in telegram message:\n{e}")
            return None


    @staticmethod
    def _failure_response(message, retry):
        return {
            "OK": False,
            "result": "Failure",
            "text": message,
            "attempts": retry,
            "timestamp": datetime.now().isoformat()
        }


    def _log_response(self, response, username):
        filepath = _filepath(None, f"{username}_TELEGRAM_LOG")
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(response) + "\n")
        except Exception as e:
            logging.error(f"Failed to log Telegram response for {username}: {e}")


    def _send_message(self, message, retry):
        for i in range(retry):
            response = self._connect_telegram_server(message, i)
            if response:
                return response
        logging.error(f"📉 telegram_message failed after {retry} attempts")
        return self._failure_response(message, retry)


    def _worker(self):
        while True:
            message, username, retry = self.message_queue.get()
            try:
                response = self._send_message(message, retry)
                self._log_response(response, username)
            finally:
                self.message_queue.task_done()


    def telegram_message(self, message, username="default", retry=3):
        self.message_queue.put((message, username, retry))



