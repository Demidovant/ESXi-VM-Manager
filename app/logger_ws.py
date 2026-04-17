import threading
import json
from flask_sock import Sock
import sys
from io import StringIO
import os

log_buffer = []
connections_lock = threading.Lock()
active_connections = set()

class PrintCapture:
    def __init__(self):
        # Сохраняем оригинальный stdout, если он существует, иначе devnull
        self.original_stdout = sys.stdout if sys.stdout is not None else open(os.devnull, 'w')
        self.buffer = StringIO()

    def write(self, message):
        try:
            self.buffer.write(message)
            if self.original_stdout:
                self.original_stdout.write(message)
        except Exception:
            pass  # Игнорируем ошибки записи в буфер/консоль

        # Отправляем во все активные WebSocket-соединения
        with connections_lock:
            for ws in list(active_connections):  # безопасная итерация по копии
                try:
                    ws.send(json.dumps({'type': 'log', 'message': message}))
                except Exception:
                    # Удаляем разорванное соединение
                    active_connections.discard(ws)

    def flush(self):
        try:
            self.buffer.flush()
            if self.original_stdout:
                self.original_stdout.flush()
        except Exception:
            pass

def init_log_socket(app):
    sock = Sock(app)

    @sock.route('/api/logs')
    def handle_logs(ws):
        with connections_lock:
            active_connections.add(ws)

        try:
            for message in log_buffer:
                ws.send(json.dumps({'type': 'log', 'message': message}))
            while True:
                data = ws.receive()
                if data == 'close':
                    break
        finally:
            with connections_lock:
                active_connections.discard(ws)