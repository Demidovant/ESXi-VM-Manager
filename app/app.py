import threading
from flask import Flask, render_template, jsonify, request
import webview

from esxi_connect import *
from vm_operations import *
from vm_snapshot import *
from vm_customize import *
from vm_list import *
from logger_ws import *
from system_tray import *
from utils import *

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
csv_file = os.getenv('CSV_FILE', False)
if csv_file:
    csv_file = os.path.join(BASE_DIR, csv_file)
else:
    csv_file = os.path.join(BASE_DIR, 'vm.csv')


app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
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


@app.route('/api/cancel', methods=['POST'])
def cancel_operations():
    global operation_interrupted
    operation_interrupted.set()
    print("[!] Получен запрос на прерывание операций")
    return jsonify({"status": "success", "message": "Запрос на прерывание принят"})


@app.route('/api/execute', methods=['POST'])
def execute_operations():
    global operation_interrupted
    operation_interrupted.clear()

    data = request.json
    vm_operations = data.get('vmOperations', [])
    success_count = 0
    errors = []
    operation_results = {}
    vm_errors = {}  # Словарь для группировки ошибок по ВМ

    total_operations = sum(len(vm['operations']) for vm in vm_operations)

    print(f"\nНАЧАЛО ВЫПОЛНЕНИЯ ОПЕРАЦИЙ: {total_operations} операций для {len(vm_operations)} ВМ")
    print("=" * 70)

    try:
        vm_configs, groups = parse_vm_csv(csv_file)
        vm_config_map = {vm['TARGET_VM_NAME']: vm for vm in vm_configs}
    except Exception as e:
        error_msg = f"Не удалось загрузить конфигурацию ВМ: {str(e)}"
        print(f"[X] КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")
        errors.append(error_msg)
        return jsonify({
            "status": "error",
            "message": error_msg,
            "success_count": 0,
            "total_operations": total_operations,
            "errors": errors,
            "vmOperations": vm_operations
        })

    si = connect_to_host()
    if si is None:
        error_msg = "Не удалось подключиться к ESXi"
        print(f"[X] КРИТИЧЕСКАЯ ОШИБКА: {error_msg}")
        errors.append(error_msg)
        return jsonify({
            "status": "error",
            "message": error_msg,
            "success_count": 0,
            "total_operations": total_operations,
            "errors": errors,
            "vmOperations": vm_operations
        })

    try:
        for vm_data in vm_operations:
            if operation_interrupted.is_set():
                print("[!] Выполнение прервано пользователем")
                errors.append("Выполнение прервано пользователем")
                break

            vm_name = vm_data['vm']
            operations = vm_data['operations']
            vm_config = vm_config_map.get(vm_name, {})
            vm_errors[vm_name] = []  # Инициализируем список ошибок для ВМ

            for op_name in operations:
                op_key = f"{vm_name}_{op_name}"
                try:
                    if operation_interrupted.is_set():
                        error_msg = f"Прервана операция '{op_name}' для ВМ {vm_name}"
                        errors.append(error_msg)
                        vm_errors[vm_name].append(error_msg)
                        operation_results[op_key] = 'error'
                        break

                    print(f"[*] Выполнение операции '{op_name}' для ВМ {vm_name}")

                    if op_name == 'clone':
                        vm_clone(si, vm_config)
                    else:
                        vm = get_vm_by_name(si, vm_name)
                        if not vm:
                            error_msg = f"ВМ {vm_name} не найдена"
                            errors.append(error_msg)
                            vm_errors[vm_name].append(error_msg)
                            operation_results[op_key] = 'error'
                            continue

                        if op_name == 'delete':
                            vm_delete(vm)
                        elif op_name == 'hardware':
                            customize_vm_hardware(vm, vm_config)
                        elif op_name == 'customize':
                            customize_vm_os(si, vm, vm_config)
                        elif op_name == 'snapshot':
                            create_snapshot(vm, vm_config)
                        elif op_name == 'poweroff':
                            vm_power_off(vm)
                        elif op_name == 'poweron':
                            vm_power_on(vm)

                    success_count += 1
                    operation_results[op_key] = 'success'

                except Exception as e:
                    error_msg = f"Ошибка операции '{op_name}' для {vm_name}: {str(e)}"
                    print(f"[X] {error_msg}")
                    errors.append(error_msg)
                    vm_errors[vm_name].append(error_msg)
                    operation_results[op_key] = 'error'

    finally:
        disconnect_from_host(si)
        operation_interrupted.clear()

    # Формируем красивый итоговый отчет
    print("\n" + "=" * 70)
    print("ИТОГОВЫЙ ОТЧЕТ О ВЫПОЛНЕНИИ ОПЕРАЦИЙ")
    print("=" * 70)
    print(f"Всего операций: {total_operations}")
    print(f"Успешно выполнено: {success_count}")
    print(f"Ошибок: {len(errors)}")
    print("-" * 70)

    # Выводим статистику по ВМ
    for vm_data in vm_operations:
        vm_name = vm_data['vm']
        print("-" * 70)
        print(f"\nВМ: {vm_name}")
        print("-" * 50)

        for op_name in vm_data['operations']:
            op_key = f"{vm_name}_{op_name}"
            status = operation_results.get(op_key, 'unknown')
            status_icon = "✓" if status == 'success' else "✗"
            print(f"  {status_icon} Операция: {op_name.ljust(10)} - {'Успешно' if status == 'success' else 'Ошибка'}")

        if vm_errors.get(vm_name):
            print("\n  Ошибки:")
            for error in vm_errors[vm_name]:
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
    message = f"Выполнено: {success_count}/{total_operations}"
    if errors:
        message += f", ошибок: {len(errors)}"

    return jsonify({
        "status": status,
        "message": message,
        "success_count": success_count,
        "total_operations": total_operations,
        "errors": errors,
        "vm_errors": vm_errors,  # Группировка ошибок по ВМ
        "vmOperations": vm_operations,
        "operationResults": operation_results,
        "summary": {
            "total": total_operations,
            "success": success_count,
            "failed": len(errors),
            "vms_with_errors": [vm for vm, errs in vm_errors.items() if errs]
        }
    })


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
