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


# ====================== ОПРЕДЕЛЕНИЕ ТИПА ПОДКЛЮЧЕНИЯ ======================
def is_vcenter(si):
    """Определяет, подключены ли мы к vCenter или к standalone ESXi"""
    try:
        content = si.RetrieveContent()
        about = content.about
        return about.productLineId == 'vpx'  # vCenter = 'vpx'
    except:
        return False


# ====================== ОСНОВНАЯ ФУНКЦИЯ КЛОНИРОВАНИЯ ======================
def vm_clone(si, vm_config):
    """Универсальное клонирование: автоматически выбирает метод в зависимости от vCenter/ESXi"""
    source_vm_name = vm_config.get('SOURCE_VM_NAME')
    source_snapshot_name = vm_config.get('SOURCE_SNAPSHOT_NAME')
    target_datastore_name = vm_config.get('TARGET_DATASTORE_NAME')
    target_vm_name = vm_config.get('TARGET_VM_NAME')
    cpu_count = int(cpu) if (cpu := vm_config.get('CPU_COUNT')) else None
    memory_mb = int(mem) if (mem := vm_config.get('MEMORY_MB')) else None

    if not all([source_vm_name, target_vm_name, target_datastore_name]):
        raise Exception("Не указаны обязательные параметры для клонирования (SOURCE_VM_NAME, TARGET_VM_NAME, TARGET_DATASTORE_NAME)")

    print(f"[*] Клонирование '{source_vm_name}' → '{target_vm_name}'")

    from vm_list import get_vm_by_name
    source_vm = get_vm_by_name(si, source_vm_name)
    if not source_vm:
        raise Exception(f"Исходная ВМ '{source_vm_name}' не найдена")

    # Автоопределение типа подключения
    if is_vcenter(si):
        print("[*] Обнаружен vCenter → используем быстрый метод CloneVM_Task")
        return clone_via_vcenter(si, source_vm, vm_config)
    else:
        print("[*] Обнаружен standalone ESXi → используем vmkfstools")
        return clone_via_esxi(si, source_vm, vm_config)


# ====================== БЫСТРЫЙ МЕТОД ЧЕРЕЗ VCENTER ======================
def clone_via_vcenter(si, source_vm, vm_config):
    """Метод клонирования через vCenter"""
    target_vm_name = vm_config.get('TARGET_VM_NAME')
    target_datastore_name = vm_config.get('TARGET_DATASTORE_NAME')
    cpu_count = int(cpu) if (cpu := vm_config.get('CPU_COUNT')) else None
    memory_mb = int(mem) if (mem := vm_config.get('MEMORY_MB')) else None

    datastore = next((ds for ds in source_vm.runtime.host.datastore if ds.name == target_datastore_name), None)
    if not datastore:
        raise Exception(f"Datastore '{target_datastore_name}' не найден на хосте")

    # Выключаем ВМ
    vm_power_off(source_vm)

    # Откат к снапшоту
    if vm_config.get('SOURCE_SNAPSHOT_NAME'):
        from vm_snapshot import revert_to_snapshot
        try:
            revert_to_snapshot(source_vm, vm_config['SOURCE_SNAPSHOT_NAME'])
        except Exception as e:
            print(f"[i] Снапшот не найден или ошибка отката: {e}")

    # Отключаем DVD-приводы
    config_spec = vim.vm.ConfigSpec()
    devices_to_edit = []
    for dev in source_vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualCdrom):
            cd_spec = vim.vm.device.VirtualDeviceSpec()
            cd_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            cd_spec.device = dev
            cd_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            cd_spec.device.connectable.connected = False
            cd_spec.device.connectable.startConnected = False
            devices_to_edit.append(cd_spec)

    if devices_to_edit:
        config_spec.deviceChange = devices_to_edit
        task = source_vm.ReconfigVM_Task(config_spec)
        wait_for_task(task)

    # Клонирование
    relocate_spec = vim.vm.RelocateSpec(datastore=datastore, diskMoveType='moveAllDiskBackingsAndDisallowSharing')
    clone_spec = vim.vm.CloneSpec(
        location=relocate_spec,
        powerOn=False,
        config=vim.vm.ConfigSpec(numCPUs=cpu_count, memoryMB=memory_mb)
    )

    print(f"[*] Клонируем ВМ через vCenter...")
    task = source_vm.CloneVM_Task(folder=source_vm.parent, name=target_vm_name, spec=clone_spec)

    with tqdm(total=100, desc="Клонирование", bar_format="{desc}: {percentage:3.0f}%|{bar}| {elapsed} прошло") as pbar:
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

    print(f"[+] ВМ '{target_vm_name}' успешно клонирована через vCenter")
    print("=" * 70)
    return task.info.result


import paramiko


# ====================== АЛЬТЕРНАТИВНЫЙ МЕТОД ДЛЯ ESXi с vmkfstools ======================
def clone_via_esxi(si, source_vm, vm_config):
    """Клонирование на standalone ESXi с использованием vmkfstools -i -d thin через SSH"""
    source_vm_name = vm_config.get('SOURCE_VM_NAME')
    target_vm_name = vm_config.get('TARGET_VM_NAME')
    target_datastore_name = vm_config.get('TARGET_DATASTORE_NAME')
    cpu_count = int(cpu) if (cpu := vm_config.get('CPU_COUNT')) else None
    memory_mb = int(mem) if (mem := vm_config.get('MEMORY_MB')) else None
    source_snapshot_name = vm_config.get('SOURCE_SNAPSHOT_NAME')

    if not all([source_vm_name, target_vm_name, target_datastore_name]):
        raise Exception("Не указаны обязательные параметры для клонирования")

    print(f"[*] Клонирование '{source_vm_name}' → '{target_vm_name}' через vmkfstools (ESXi)")

    # Откат к снапшоту
    if source_snapshot_name:
        from vm_snapshot import revert_to_snapshot
        try:
            revert_to_snapshot(source_vm, source_snapshot_name)
        except Exception as e:
            print(f"[!] Не удалось откатить снапшот: {e}")

    # Выключаем исходную ВМ
    was_powered_on = source_vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn
    if was_powered_on:
        vm_power_off(source_vm)

    ssh = None
    try:
        # Импортируем параметры подключения
        from esxi_connect import ESXI_HOST, ESXI_USER, ESXI_PASSWORD, ESXI_PORT, SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT

        print(f"[*] Подключение по SSH к {SSH_HOST}...")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Улучшенные параметры подключения для ESXi
        ssh.connect(
            hostname=SSH_HOST,
            username=SSH_USER,
            password=SSH_PASSWORD,
            port=SSH_PORT,
            timeout=20,
            banner_timeout=10,
            auth_timeout=10,
            allow_agent=False,
            look_for_keys=False
        )
        print("[+] SSH подключение успешно")

        target_path = f"/vmfs/volumes/{target_datastore_name}/{target_vm_name}"
        print(f"[*] Создаём целевую папку: {target_path}")
        ssh.exec_command(f"mkdir -p '{target_path}'")

        # Клонируем диски через vmkfstools
        print(f"[*] Клонируем виртуальные диски с помощью vmkfstools...")
        for device in source_vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                backing = device.backing
                while backing.parent:
                    backing = backing.parent
                source_datastore_name = backing.datastore.name
                # print(f"Datastore : {source_datastore_name}")

        from vm_snapshot import find_snapshot
        if source_snapshot_name:
            needed_snapshot_tree = find_snapshot(source_vm, source_snapshot_name)
            if not needed_snapshot_tree:
                print(f"Снапшот {source_snapshot_name} не найден. Будет клонирован базовый диск.")
                source_vmdk_name = f"/vmfs/volumes/{source_datastore_name}/{source_vm.name}/{source_vm.name}.vmdk"
            else:
                needed_snapshot = needed_snapshot_tree.snapshot

                for device in needed_snapshot.config.hardware.device:
                    if isinstance(device, vim.vm.device.VirtualDisk):
                        source_vmdk_name = device.backing.fileName
                        source_vmdk_name = f"/vmfs/volumes/{source_datastore_name}/{source_vm.name}/{source_vmdk_name.split('/')[-1]}"
        else:
            print(f"Снапшот не указан. Будет клонирован базовый диск.")
            source_vmdk_name = f"/vmfs/volumes/{source_datastore_name}/{source_vm.name}/{source_vm.name}.vmdk"

        # Новое имя диска в целевой папке
        target_vmdk_name = f"/vmfs/volumes/{target_datastore_name}/{target_vm_name}/{target_vm_name}.vmdk"

        print(f" → Клонируем:")
        print(f"{source_vmdk_name}")
        print("↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓")
        print(f"{target_vmdk_name}")

        cmd = f'vmkfstools -i "{source_vmdk_name}" "{target_vmdk_name}" -d thin'
        _, stdout, stderr = ssh.exec_command(cmd)

        output = stdout.read().decode().strip()
        error_out = stderr.read().decode().strip()

        if output:
            print(output)
        if error_out:
            print(f"[!] {error_out}")



        # Копируем vmx
        print(f"[*] Копируем vmx...")
        vmx_old = f"/vmfs/volumes/{source_datastore_name}/{source_vm.name}/{source_vm.name}.vmx"
        vmx_new = f"/vmfs/volumes/{target_datastore_name}/{target_vm_name}/{target_vm_name}.vmx"

        cmd = f'cp -r "{vmx_old}" "{vmx_new}" 2>/dev/null || true'
        _, stdout, stderr = ssh.exec_command(cmd)

        output = stdout.read().decode().strip()
        error_out = stderr.read().decode().strip()

        if output:
            print(output)
        if error_out:
            print(f"[!] {error_out}")


        # Переименовываем .vmx и исправляем содержимое
        print(f"[*] Обновляем .vmx файл...")
        ssh.exec_command(f'sed -i "s/{source_vm.name}/{target_vm_name}/g" "{vmx_new}"')

        target_disk_filename = f"{target_vm_name}.vmdk"
        cmd = f"""sed -i 's|^\\([a-zA-Z0-9]\\+:[0-9]\\+\\.fileName = \\)".*\\.vmdk"|\\1"{target_disk_filename}"|' "{vmx_new}" """
        ssh.exec_command(cmd)

        ssh.exec_command(f'echo \'uuid.action = "create"\' >> "{vmx_new}"')


        # Регистрируем VM
        print(f"[*] Регистрируем новую ВМ '{target_vm_name}'...")

        # Регистрируем через vim-cmd (самый надёжный способ на standalone ESXi)
        register_cmd = f'vim-cmd solo/registervm "{vmx_new}" "{target_vm_name}"'

        _, stdout, stderr = ssh.exec_command(register_cmd)

        output = stdout.read().decode().strip()
        error_out = stderr.read().decode().strip()

        if error_out:
            print(f"[!] Ошибка регистрации: {error_out}")
            raise Exception(f"Не удалось зарегистрировать ВМ: {error_out}")

        if output:
            print(f"[+] vim-cmd вывод: {output}")

        # Получаем объект новой ВМ
        print(f"[*] Поиск зарегистрированной ВМ '{target_vm_name}'...")

        # Ждём немного, пока ВМ появится в inventory
        time.sleep(2)

        def find_vm_by_name(content, name):
            container = content.viewManager.CreateContainerView(content.rootFolder,[vim.VirtualMachine],True)
            for vm in container.view:
                if vm.name == name:
                    print(f"Зарегистрирована ВМ '{vm.name}'")
                    return vm
            return None

        new_vm = find_vm_by_name(si.RetrieveContent(), target_vm_name)

        if not new_vm:
            raise Exception(f"Не удалось найти ВМ '{target_vm_name}'")

        if was_powered_on:
            vm_power_on(new_vm)

        print(f"[+] Клонирование успешно завершено через vmkfstools!")
        print("=" * 70)

        # Переконфигурируем (CPU, RAM)
        reconfig_vm_after_clone(new_vm, cpu_count, memory_mb)

        if was_powered_on and source_vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
            vm_power_on(source_vm)

        return new_vm

    except paramiko.SSHException as ssh_err:
        raise Exception(f"Ошибка SSH подключения: {str(ssh_err)}")
    except Exception as e:
        raise Exception(f"Ошибка клонирования через vmkfstools: {str(e)}")
    finally:
        if ssh:
            try:
                ssh.close()
            except:
                pass


def reconfig_vm_after_clone(vm, cpu_count=None, memory_mb=None):
    """Настройка новой ВМ после клонирования на ESXi"""
    config_spec = vim.vm.ConfigSpec()

    if cpu_count:
        config_spec.numCPUs = cpu_count
        config_spec.numCoresPerSocket = cpu_count

    if memory_mb:
        config_spec.memoryMB = memory_mb

    # Удаляем DVD-приводы
    device_changes = []
    for dev in vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualCdrom):
            spec = vim.vm.device.VirtualDeviceSpec()
            spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
            spec.device = dev
            device_changes.append(spec)

    if device_changes:
        config_spec.deviceChange = device_changes

    if config_spec.numCPUs or config_spec.memoryMB or device_changes:
        task = vm.ReconfigVM_Task(config_spec)
        wait_for_task(task, "Настройка новой ВМ")

    print("[+] Параметры новой ВМ применены")


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