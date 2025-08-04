import time
from pyVmomi import vim
from tqdm import tqdm


def vm_detect_os_type(vm) -> str:
    """
    Определяет ОС виртуальной машины по guestId и guestFullName.
    Возвращает один из: 'windows', 'ubuntu', 'centos', 'debian', 'redos', 'astra', 'linux', 'unknown'
    """
    try:
        guest_id = (vm.config.guestId or "").lower()
        guest_name = (vm.config.guestFullName or "").lower()
        combined = guest_id + " " + guest_name

        if "windows" in combined:
            return "windows"
        elif "ubuntu" in combined:
            return "ubuntu"
        elif "centos" in combined:
            return "centos"
        elif "debian" in combined:
            return "debian"
        elif "redos" in combined:
            return "redos"
        elif "astra" in combined:
            return "astra"
        elif "linux" in combined:
            return "linux"
        else:
            return "unknown"
    except Exception:
        return "unknown"


def wait_for_task(task, description="Операция"):
    # Сначала даем задаче хотя бы немного времени на старт
    time.sleep(0.1)

    while task.info.state == vim.TaskInfo.State.running:
        time.sleep(0.1)  # Уменьшаем интервал проверки

    if task.info.state == vim.TaskInfo.State.success:
        return task.info.result
    else:
        err = task.info.error
        if err is None:
            raise Exception(f"{description} завершилась с ошибкой, но информация об ошибке отсутствует.")
        # Пытаемся получить подробное сообщение
        msg = getattr(err, 'localizedMessage', None)
        if not msg:
            # Если localizedMessage нет, пытаемся вывести всю ошибку как есть
            msg = str(err)
        raise Exception(f"{description} завершилась с ошибкой: {msg}")


# def vm_power_off(vm):
#     if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
#         print(f"[*] Останавливаем ВМ {vm.name} ...")
#         task = vm.PowerOffVM_Task()
#         wait_for_task(task, description=f"Выключение ВМ {vm.name}")
#         print(f"[+] ВМ {vm.name} успешно выключена.")
#     else:
#         print(f"[!] ВМ {vm.name} уже выключена.")

def vm_power_off(vm, shutdown_timeout=60, poweroff_timeout=10):
    """
    Выключает виртуальную машину с попыткой graceful shutdown через гостевую ОС.
    Если гостевые инструменты недоступны или выключение не завершается в течение shutdown_timeout,
    выполняется принудительное выключение (power off).

    :param vm: Объект виртуальной машины
    :param shutdown_timeout: Таймаут ожидания graceful shutdown (секунды)
    :param poweroff_timeout: Таймаут ожидания принудительного выключения (секунды)
    """
    if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
        print(f"[!] ВМ {vm.name} уже выключена.")
        print("=" * 70)
        return

    print(f"[*] Начинаем процесс выключения ВМ {vm.name}")

    # 1. Проверяем доступность гостевых инструментов
    try:
        tools_status = getattr(vm.guest, 'toolsRunningStatus', 'guestToolsNotRunning')
        if tools_status == 'guestToolsRunning':
            print(f"[+] VMware Tools работают, пробуем graceful shutdown...")

            # 2. Пробуем выполнить graceful shutdown
            try:
                vm.ShutdownGuest()
                print(f"[*] Ожидаем завершения работы (таймаут {shutdown_timeout} сек)...")

                # 3. Ожидаем выключения
                start_time = time.time()
                while time.time() - start_time < shutdown_timeout:
                    if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                        print(f"[+] ВМ {vm.name} успешно выключена через graceful shutdown.")
                        print("=" * 70)
                        return
                    time.sleep(2)

                print(f"[!] ВМ {vm.name} не выключилась за {shutdown_timeout} сек")
                print("=" * 70)

            except Exception as shutdown_error:
                print(f"[!] Ошибка graceful shutdown: {str(shutdown_error)}")
                print("=" * 70)

        else:
            print(f"[!] VMware Tools не работают (status: {tools_status})")
            print("=" * 70)

    except Exception as tools_check_error:
        print(f"[!] Ошибка проверки VMware Tools: {str(tools_check_error)}")
        print("=" * 70)

    # 4. Если graceful shutdown не сработал или Tools не доступны - выполняем power off
    print(f"[*] Выполняем принудительное выключение (power off)...")
    try:
        task = vm.PowerOffVM_Task()
        wait_for_task(task, description=f"Принудительное выключение ВМ {vm.name}")
        print(f"[+] ВМ {vm.name} успешно выключена через power off.")
    except Exception as poweroff_error:
        print(f"[!!!] Критическая ошибка при power off ВМ {vm.name}: {str(poweroff_error)}")
    finally:
        print("=" * 70)

def vm_power_on(vm):
    if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
        print(f"[*] Запускаем ВМ {vm.name} ...")
        task = vm.PowerOnVM_Task()
        wait_for_task(task, description=f"Запуск ВМ {vm.name}")
        print(f"[+] ВМ {vm.name} успешно запущена.")
    else:
        print(f"[!] ВМ {vm.name} уже запущена.")

    print("=" * 70)


def vm_reboot(vm):
    if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
        print(f"[*] Перезапуск ВМ {vm.name} ...")
        vm_power_off(vm)
        time.sleep(2)  # небольшая пауза между выключением и запуском
        vm_power_on(vm)
        print(f"[+] ВМ {vm.name} успешно перезапущена.")
    else:
        print(f"[!] ВМ {vm.name} уже выключена. Просто запускаем.")
        vm_power_on(vm)

    print("=" * 70)


def vm_clone(si, vm_config):
    """Клонирует ВМ без изменения сетевых настроек"""

    source_vm_name = vm_config.get('SOURCE_VM_NAME')
    source_snapshot_name = vm_config.get('SOURCE_SNAPSHOT_NAME')
    target_datastore_name = vm_config.get('TARGET_DATASTORE_NAME')
    target_vm_name = vm_config.get('TARGET_VM_NAME')
    cpu_count = int(cpu) if (cpu := vm_config.get('CPU_COUNT')) else None
    memory_mb = int(mem) if (mem := vm_config.get('MEMORY_MB')) else None

    # Получаем объект source ВМ
    from vm_list import get_vm_by_name
    source_vm = get_vm_by_name(si, source_vm_name)

    # Находим target datastore
    # Получаем хост, на котором запущена ВМ
    esxi_host = source_vm.runtime.host
    # Находим datastore среди доступных на хосте
    datastore = next((ds for ds in esxi_host.datastore if ds.name == target_datastore_name), None)
    if not datastore:
        raise Exception(f"Datastore '{target_datastore_name}' не найден на хосте {esxi_host.name}")

    # Выключаем ВМ (если включена)
    vm_power_off(source_vm)

    # Откатываем к снапшоту
    from vm_snapshot import revert_to_snapshot
    revert_to_snapshot(source_vm, source_snapshot_name)

    # Отключаем все DVD-приводы
    config_spec = vim.vm.ConfigSpec()
    devices_to_edit = []

    for dev in source_vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualCdrom):
            # Создаем спецификацию для отключения этого устройства
            cd_spec = vim.vm.device.VirtualDeviceSpec()
            cd_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cd_spec.device = dev

            # Создаем пустую backing-спецификацию (это эквивалентно извлечению диска)
            cd_spec.device.backing = vim.vm.device.VirtualCdrom.RemotePassthroughBackingInfo()
            cd_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cd_spec.device.connectable.connected = False
            cd_spec.device.connectable.startConnected = False

            devices_to_edit.append(cd_spec)

    if devices_to_edit:
        config_spec.deviceChange = devices_to_edit
        print(f"[*] Извлекаем диски из DVD-приводов...")
        task = source_vm.ReconfigVM_Task(config_spec)
        wait_for_task(task)  # Нужно дождаться завершения

    # Настройки клонирования
    relocate_spec = vim.vm.RelocateSpec(datastore=datastore, pool=esxi_host.parent.resourcePool, diskMoveType='moveAllDiskBackingsAndDisallowSharing')

    clone_spec = vim.vm.CloneSpec(
        location=relocate_spec,
        powerOn=False,
        config=vim.vm.ConfigSpec(
            numCPUs=cpu_count,
            memoryMB=memory_mb
        )
    )

    print(f"[*] Клонируем ВМ '{source_vm.name}' в '{target_vm_name}'...")
    task = source_vm.CloneVM_Task(folder=source_vm.parent, name=target_vm_name, spec=clone_spec)

    # Отображаем прогресс с зелёным баром, временем и защитой от None
    GREEN = "\033[92m"
    RESET = "\033[0m"

    with tqdm(
            total=100,
            desc=f"{GREEN}Клонирование",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {elapsed} прошло" + RESET
    ) as pbar:
        last_progress = 0
        while task.info.state == vim.TaskInfo.State.running:
            time.sleep(1)
            current_progress = getattr(task.info, 'progress', last_progress)
            if current_progress is not None:
                pbar.n = current_progress
                last_progress = current_progress
                pbar.refresh()

    if task.info.state != vim.TaskInfo.State.success:
        error = getattr(task.info.error, 'localizedMessage', str(task.info.error))
        raise Exception(f"Ошибка клонирования: {error}")

    print(f"[+] ВМ '{target_vm_name}' успешно клонирована")
    return task.info.result

    print("=" * 70)


def vm_delete(vm):
    """
    Удаляет ВМ. Предварительно выключает её, если она включена.
    """
    print(f"[*] Удаление ВМ '{vm.name}'...")

    try:
        if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            print(f"[*] ВМ '{vm.name}' включена, выключаем перед удалением.")
            vm_power_off(vm)

        task = vm.Destroy_Task()
        # wait_for_task(task, description=f"Удаление ВМ {vm.name}")

        print(f"[+] ВМ '{vm.name}' успешно удалена.")
    except Exception as e:
        print(f"[!] Ошибка при удалении ВМ '{vm.name}': {e}")

    print("=" * 70)
