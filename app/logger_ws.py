import threading
import json
from flask_sock import Sock
import sys
from io import StringIO


# Глобальный буфер для логов
log_buffer = []
connections_lock = threading.Lock()
active_connections = set()


class PrintCapture:
    def __init__(self):
        self.original_stdout = sys.stdout
        self.buffer = StringIO()

    def write(self, message):
        self.buffer.write(message)
        self.original_stdout.write(message)

        # Отправляем во все активные соединения
        with connections_lock:
            for ws in active_connections:
                try:
                    ws.send(json.dumps({'type': 'log', 'message': message}))

                except:
                    pass

    def flush(self):
        self.buffer.flush()
        self.original_stdout.flush()


def init_log_socket(app):
    sock = Sock(app)

    @sock.route('/api/logs')
    def handle_logs(ws):
        with connections_lock:
            active_connections.add(ws)

        try:
            # Отправить буферизированные логи
            for message in log_buffer:
                ws.send(json.dumps({'type': 'log', 'message': message}))

            while True:
                data = ws.receive()
                if data == 'close':
                    break
        finally:
            with connections_lock:
                active_connections.remove(ws)