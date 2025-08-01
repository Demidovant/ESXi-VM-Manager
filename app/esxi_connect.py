from pyVim.connect import SmartConnect, Disconnect
import ssl
from dotenv import load_dotenv
import os
import sys
import traceback
from datetime import datetime
import socket
from pyVmomi import vim


# Загружаем переменные из .env
try:
    load_dotenv()
    print("Успешно загружены переменные окружения из .env файла")
except Exception as e:
    print(f"[X] Ошибка загрузки .env файла: {str(e)}")
    sys.exit(1)

# Получение параметров подключения с проверками
try:
    ESXI_HOST = os.getenv("ESXI_HOST")
    ESXI_USER = os.getenv("ESXI_USER")
    ESXI_PASSWORD = os.getenv("ESXI_PASSWORD")
    ESXI_PORT = int(os.getenv("ESXI_PORT", "443"))

    if not all([ESXI_HOST, ESXI_USER, ESXI_PASSWORD]):
        raise ValueError("Не все обязательные переменные окружения заданы")

    IGNORE_SSL = os.getenv("IGNORE_SSL", "true").lower() == "true"

    print(f"Параметры подключения: host={ESXI_HOST}, user={ESXI_USER}, port={ESXI_PORT}, ignore_ssl={IGNORE_SSL}")
except ValueError as ve:
    print(f"[X] Ошибка в параметрах подключения: {str(ve)}")
    sys.exit(1)
except Exception as e:
    print(f"[X] Неожиданная ошибка при получении параметров: {str(e)}")
    sys.exit(1)


def connect_to_host(
        host=ESXI_HOST,
        user=ESXI_USER,
        password=ESXI_PASSWORD,
        port=ESXI_PORT,
        ignore_ssl=IGNORE_SSL
):
    """
    Подключение к ESXi с обработкой ошибок.
    Возвращает service_instance или None при ошибке.
    """
    try:
        print(f"Попытка подключения к {host}:{port}...")

        # Проверка доступности хоста с таймаутом 3 секунды
        try:
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
        except socket.timeout:
            print(f"[X] Не удалось подключиться к {host}:{port}")
            return None
        except socket.error as se:
            print(f"[X] Ошибка подключения к {host}:{port}: {str(se)}")
            return None

        # Настройка SSL контекста
        context = None
        if ignore_ssl:
            context = ssl._create_unverified_context()
        else:
            print("[!] Используется строгая проверка SSL сертификата")
            context = ssl.create_default_context()

        # Подключение
        si = SmartConnect(
            host=host,
            user=user,
            pwd=password,
            port=port,
            sslContext=context
        )

        print(f"Успешное подключение к {host}")
        return si

    except vim.fault.InvalidLogin as il:
        print(f"[X] Ошибка аутентификации: {str(il)}")
    except vim.fault.HostConnectFault as hcf:
        print(f"[X] Ошибка подключения к хосту: {str(hcf)}")
    except ssl.SSLError as ssle:
        print(f"[X] SSL ошибка: {str(ssle)}")
    except Exception as e:
        print(f"[X] Неожиданная ошибка подключения: {str(e)}")
        print(f"[!] Трассировка ошибки:\n{traceback.format_exc()}")

    finally:
        print("=" * 70)

    return None


def disconnect_from_host(service_instance):
    """
    Безопасное отключение от ESXi.
    """
    if service_instance is None:
        print("[!] Попытка отключения при отсутствующем подключении")
        return

    try:
        print("Попытка отключения от ESXi...")
        Disconnect(service_instance)
        print("Успешное отключение от ESXi")
    except Exception as e:
        print(f"[X] Ошибка при отключении: {str(e)}")
        print(f"[!] Трассировка ошибки:\n{traceback.format_exc()}")