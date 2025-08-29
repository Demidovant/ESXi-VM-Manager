from pyVmomi import vim
from datetime import datetime
from vm_operations import vm_power_on, vm_power_off, wait_for_task


def find_snapshot(vm, snapshot_name):
    """Рекурсивно ищет снапшот по имени в дереве снапшотов ВМ."""

    def recurse(snapshot_list):
        for snapshot in snapshot_list:
            #print("Проверка снапшота:", snapshot.name)
            if snapshot.name == snapshot_name:
                # print("Найден снапшот:", snapshot.name)
                return snapshot
            if snapshot.childSnapshotList:
                result = recurse(snapshot.childSnapshotList)
                if result:
                    return result
        return None

    if not vm.snapshot:
        print("VM не содержит снапшотов")
        return None

    return recurse(vm.snapshot.rootSnapshotList)



def revert_to_snapshot(vm, snapshot_name):
    """Откатывает ВМ к указанному снапшоту, если это необходимо"""
    snapshot = find_snapshot(vm, snapshot_name)
    if not snapshot:
        raise Exception(f"Снапшот '{snapshot_name}' не найден")

    # Получаем текущее состояние ВМ
    was_powered_on = vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn

    if was_powered_on:
        vm_power_off(vm)

    try:
        # current_snapshot = vm.snapshot.currentSnapshot if vm.snapshot else None
        #
        # if current_snapshot and current_snapshot._moId == snapshot.snapshot._moId:
        #     print(f"[=] ВМ {vm.name} уже находится в снапшоте '{snapshot_name}', откат не требуется")
        #     print("=" * 70)
        #     return

        print(f"[*] Откатываем ВМ {vm.name} к снапшоту '{snapshot_name}'...")
        task = snapshot.snapshot.RevertToSnapshot_Task()
        wait_for_task(task, "Откат к снапшоту")
        print("[+] Снапшот успешно восстановлен")

        print("=" * 70)

        if was_powered_on:
            print("[*] Включаем ВМ так как изначально она была включена...")
            vm_power_on(vm)

    except Exception as e:
        print(f"[-] Ошибка при создании снапшота: {str(e)}")
        print("=" * 70)
        if was_powered_on:
            print("[*] Включаем ВМ так как изначально она была включена...")
            vm_power_on(vm)
        raise



def list_all_snapshots_names(vm):
    """Возвращает список всех снапшотов ВМ (только имена, без путей)."""

    def recurse(snapshot_list):
        snapshots = []
        for snapshot in snapshot_list:
            snapshots.append(snapshot.name)
            if snapshot.childSnapshotList:
                snapshots.extend(recurse(snapshot.childSnapshotList))
        return snapshots

    if not vm.snapshot:
        print("У ВМ нет снапшотов")
        return []

    return recurse(vm.snapshot.rootSnapshotList)


def create_snapshot(vm, vm_config, memory=False, quiesce=False):
    """
    Создаёт снапшот ВМ с указанным именем и описанием.

    :param vm: Объект виртуальной машины
    :param vm_config: Конфиг ВМ
    :param memory: Сохранять память ВМ (по умолчанию False)
    :param quiesce: Применять quiescing (по умолчанию False)
    """

    snapshot_name = (
        vm_config.get('snapshot_name') or  # из поля ввода в браузере
        vm_config.get('TARGET_SNAPSHOT_NAME') or  # из CSV
        f"snapshot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"  # по умолчанию
    )
    # snapshot_name = vm_config.get('TARGET_SNAPSHOT_NAME') or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Определяем description
    if vm_config.get('snapshot_name'):  # Если имя задано в браузере
        description = ""
    else:  # Если имя из CSV или по умолчанию
        description = vm_config.get('TARGET_SNAPSHOT_DESCRIPTION', "")

    print(f"[*] Создание снапшота '{snapshot_name}' для ВМ {vm.name}...")

    # Получаем текущее состояние ВМ
    was_powered_on = vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn

    if was_powered_on:
        vm_power_off(vm)

    task = vm.CreateSnapshot_Task(
        name=snapshot_name,
        description=description,
        memory=memory,
        quiesce=quiesce
    )

    try:
        wait_for_task(task, description=f"Создание снапшота '{snapshot_name}'")
        print(f"[+] Снапшот '{snapshot_name}' успешно создан")

        print("=" * 70)

        if was_powered_on:
            print("[*] Включаем ВМ так как изначально она была включена...")
            vm_power_on(vm)

    except Exception as e:
        print(f"[-] Ошибка при создании снапшота: {str(e)}")
        print("=" * 70)
        if was_powered_on:
            print("[*] Включаем ВМ так как изначально она была включена...")
            vm_power_on(vm)
        raise
