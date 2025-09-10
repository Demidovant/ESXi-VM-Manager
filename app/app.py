# Для сборки exe
# pyinstaller --clean --onefile --noconsole --name ESXi_VM_Manager --paths app --add-data "static;static" --add-data "templates;templates" --hidden-import=flask --hidden-import=webview --hidden-import=pyVim --hidden-import=pyVmomi --hidden-import=dotenv --icon static/img/icon.ico app/app.py


import threading
from flask import Flask, render_template, jsonify, request, Response
import webview
import uuid

import sys, os
sys.path.append(os.path.dirname(__file__))

from esxi_connect import *
from vm_operations import *
from vm_snapshot import *
from vm_customize import *
from vm_list import *
from logger_ws import *
from system_tray import *
from utils import *

# Определяем базовую директорию
if getattr(sys, 'frozen', False):
    # exe запущен
    BASE_DIR = os.path.dirname(sys.executable)  # рядом с exe
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

print(f"Базовая директория: {BASE_DIR}")


# Функция для поиска файлов рядом с exe
def find_file_near_exe(filename, default_name=None):
    """
    Ищет файл в директории с exe
    """
    file_path = os.path.join(BASE_DIR, filename)
    if os.path.exists(file_path):
        return file_path

    # Если файл не найден и указано default имя
    if default_name:
        default_path = os.path.join(BASE_DIR, default_name)
        if os.path.exists(default_path):
            return default_path

    # Если файл не существует, возвращаем путь для создания
    return os.path.join(BASE_DIR, default_name or filename)


# Загрузка .env файла
env_file_name = os.getenv('ENV_FILE', '.env')
env_file_path = find_file_near_exe(env_file_name, '.env')

print(f"Путь к env файлу: {env_file_path}")

# Загружаем .env если он существует
if os.path.exists(env_file_path):
    from dotenv import load_dotenv

    load_dotenv(env_file_path)
    print(f"Успешно загружены переменные из {env_file_path}")
else:
    print(f"Env файл {env_file_path} не найден, используем переменные окружения системы")

# Загрузка CSV файла
csv_file_env = os.getenv('CSV_FILE', 'vm.csv')
csv_file = find_file_near_exe(csv_file_env, 'vm.csv')

print(f"Путь к CSV файлу: {csv_file}")

# Проверяем существование CSV файла
if not os.path.exists(csv_file):
    print(f"ВНИМАНИЕ: CSV файл {csv_file} не найден!")
    print("Создайте файл vm.csv рядом с исполняемым файлом")

active_sessions = {}

app = Flask(__name__,
            template_folder = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), 'templates'),
            static_folder = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), 'static'))
operation_interrupted = threading.Event()
sock = init_log_socket(app)

# Глобальный перехватчик лога
sys.stdout = PrintCapture()

def on_window_minimized():
    app_tray.is_app_hidden = True


@app.route('/')
def index():
    # csv_file = '../vm.csv'
    if not os.path.exists(csv_file):
        return f"CSV file {csv_file} not found", 404

    vm_configs, groups = parse_vm_csv(csv_file)

    return render_template('index.html', groups=groups)


@app.route('/api/vms', methods=['GET'])
def get_vms():
    # csv_file = '../vm.csv'
    vm_configs, groups = parse_vm_csv(csv_file)
    return jsonify(vm_configs)


@app.route('/api/start-operations', methods=['POST'])
def start_operations():
    global operation_interrupted
    operation_interrupted.clear()

    data = request.json
    vm_operations = data.get('vmOperations', [])

    try:
        vm_configs, _ = parse_vm_csv(csv_file)
        vm_config_map = {vm['TARGET_VM_NAME']: vm for vm in vm_configs}

        # Подключаемся к ESXi один раз для всех операций
        si = connect_to_host()
        if si is None:
            raise Exception("Не удалось подключиться к ESXi")

        # Возвращаем идентификатор сессии
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = {
            'si': si,
            'vm_config_map': vm_config_map,
            'vm_operations': vm_operations,
            'success_count': 0,
            'errors': [],
            'operation_results': {},
            'vm_errors': {}
        }

        return jsonify({
            "status": "success",
            "message": "Сессия операций создана",
            "session_id": session_id
        })

    except Exception as e:
        if 'si' in locals() and si:
            disconnect_from_host(si)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/execute-operation', methods=['POST'])
def execute_operation():
    global operation_interrupted

    data = request.json
    session_id = data.get('session_id')
    vm_name = data.get('vm_name')
    operation = data.get('operation')
    snapshot_name = data.get('snapshot_name')
    revert_name = data.get('revert_name')

    if not session_id or session_id not in active_sessions:
        return jsonify({"status": "error", "message": "Недействительная сессия"}), 400

    session = active_sessions[session_id]
    operation_key = f"{vm_name}_{operation}"

    try:
        # Отправляем статус начала операции
        session['operation_results'][operation_key] = 'active'
        # print(json.dumps({"operation": operation_key, "status": "active"}))

        # Проверяем подключение к хосту
        if not session['si']:
            raise Exception("Нет подключения к ESXi")

        try:
            if operation == 'clone':
                vm_clone(session['si'], session['vm_config_map'].get(vm_name, {}))
            else:
                vm = get_vm_by_name(session['si'], vm_name)
                if not vm:
                    raise Exception(f"ВМ {vm_name} не найдена")

                if operation == 'delete':
                    vm_delete(vm)
                elif operation == 'customize':
                    customize_vm_os(session['si'], vm, session['vm_config_map'].get(vm_name, {}))
                elif operation == 'hardware':
                    customize_vm_hardware(vm, session['vm_config_map'].get(vm_name, {}))
                elif operation == 'snapshot':
                    config = session['vm_config_map'].get(vm_name, {}).copy()
                    if snapshot_name:
                        config['snapshot_name'] = snapshot_name
                    create_snapshot(vm, config)
                elif operation == 'revert':
                    if not revert_name:
                        raise Exception("Не указано имя снапшота для отката")
                    revert_to_snapshot(vm, revert_name)
                elif operation == 'poweroff':
                    vm_power_off(vm)
                elif operation == 'poweron':
                    vm_power_on(vm)

            session['success_count'] += 1
            session['operation_results'][operation_key] = 'success'

            return jsonify({
                "status": "success",
                "operation": operation_key,
                "vm_name": vm_name
            })


        except Exception as op_error:
            # Ошибка в конкретной операции
            error_msg = f"Ошибка операции '{operation}' для {vm_name}: {str(op_error)}"
            session['errors'].append(error_msg)
            session['vm_errors'].setdefault(vm_name, []).append(error_msg)
            session['operation_results'][operation_key] = 'error'  # Устанавливаем статус ошибки
            return jsonify({
                "status": "error",  # Явно указываем статус ошибки
                "message": error_msg,
                "operation": operation_key,
                "vm_name": vm_name
            })

    except Exception as e:
        # Критическая ошибка (только при подключении) - прерываем все
        if "подключ" in str(e).lower() or "connect" in str(e).lower():
            error_msg = f"Критическая ошибка подключения: {str(e)}"
            session['errors'].append(error_msg)
            session['operation_results'][operation_key] = 'error'
            return jsonify({
                "status": "critical_error",
                "message": error_msg,
                "operation": operation_key
            }), 500
        else:
            # Все остальные ошибки считаем не критическими
            error_msg = f"Ошибка: {str(e)}"
            session['errors'].append(error_msg)
            session['vm_errors'].setdefault(vm_name, []).append(error_msg)
            session['operation_results'][operation_key] = 'error'
            return jsonify({
                "status": "success",
                "message": error_msg,
                "operation": operation_key,
                "vm_name": vm_name
            })


@app.route('/api/finish-operations', methods=['POST'])
def finish_operations():
    global operation_interrupted

    data = request.json
    session_id = data.get('session_id')

    if not session_id or session_id not in active_sessions:
        return jsonify({"status": "error", "message": "Недействительная сессия"}), 400

    session = active_sessions.pop(session_id)
    si = session['si']

    try:
        # Формируем итоговый отчет
        total_operations = sum(len(vm['operations']) for vm in session['vm_operations'])
        success_count = session['success_count']
        errors = session['errors']

        print('.')
        print('..')
        print('...')
        print('..')
        print('.')

        print("\n" + "=" * 70)
        print("ИТОГОВЫЙ ОТЧЕТ О ВЫПОЛНЕНИИ ОПЕРАЦИЙ")
        print("=" * 70)
        print(f"Всего операций: {total_operations}")
        print(f"Успешно выполнено: {success_count}")
        print(f"Ошибок: {len(errors)}")
        print("-" * 70)

        # Выводим статистику по ВМ
        for vm_data in session['vm_operations']:
            vm_name = vm_data['vm']
            print("-" * 70)
            print(f"\nВМ: {vm_name}")
            print("-" * 70)

            for op_name in vm_data['operations']:
                op_key = f"{vm_name}_{op_name}"
                status = session['operation_results'].get(op_key, 'unknown')
                status_icon = "✓" if status == 'success' else "✗"
                print(
                    f"  {status_icon} Операция: {op_name.ljust(10)} - {'Успешно' if status == 'success' else 'Ошибка'}")

            if vm_name in session['vm_errors']:
                print("\n  Ошибки:")
                for error in session['vm_errors'][vm_name]:
                    print(f"    • {error}")

        # Общие ошибки (если есть)
        if errors:
            print("\n" + "=" * 70)
            print("СПИСОК ОШИБОК:")
            for i, error in enumerate(errors, 1):
                print(f"{i}. {error}")

        print("\n" + "=" * 70)
        print("ВЫПОЛНЕНИЕ ОПЕРАЦИЙ ЗАВЕРШЕНО")
        print("=" * 70 + "\n")

        status = "error" if errors else "success"
        message = f"Выполнено: {success_count} из {total_operations}"
        if errors:
            message += f", ошибок: {len(errors)}"

        return jsonify({
            "status": status,
            "message": message,
            "success_count": success_count,
            "total_operations": total_operations,
            "errors": errors,
            "vm_errors": session['vm_errors'],
            "operationResults": session['operation_results']
        })

    finally:
        if si:
            disconnect_from_host(si)
        operation_interrupted.clear()


@app.route('/api/cancel-operations', methods=['POST'])
def cancel_operations():
    global operation_interrupted
    operation_interrupted.set()

    data = request.json
    session_id = data.get('session_id')

    if session_id in active_sessions:
        session = active_sessions.pop(session_id)
        if session['si']:
            disconnect_from_host(session['si'])

    return jsonify({
        "status": "success",
        "message": "Операции прерваны"
    })

@app.route('/api/operation-updates')
def operation_updates():
    def generate():
        # Здесь можно реализовать отправку обновлений через Server-Sent Events
        # Но в нашем случае мы просто перенаправляем вывод print
        pass
    return Response(generate(), mimetype="text/event-stream")

def start_flask():
    app.run(host='0.0.0.0', debug=False, port=5000)


if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=start_flask, daemon=True).start()

    # Создаем и запускаем окно приложения
    window = webview.create_window(
        'ESXi VM Manager',
        'http://127.0.0.1:5000',
        # width=1366,
        # height=768,
        resizable=True,
        maximized=True,
        # hidden = True,
    )

    # Создаем иконку в трее
    app_tray = AppTray(window)

    # Настраиваем обработчики событий окна
    window.events.minimized += on_window_minimized
    window.events.closed += app_tray.stop

    webview.start()
