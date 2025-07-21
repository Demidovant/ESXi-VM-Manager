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

    current_snapshot = vm.snapshot.currentSnapshot if vm.snapshot else None

    if current_snapshot and current_snapshot._moId == snapshot.snapshot._moId:
        print(f"[=] ВМ {vm.name} уже находится в снапшоте '{snapshot_name}', откат не требуется")
        return

    print(f"[*] Откатываем ВМ {vm.name} к снапшоту '{snapshot_name}'...")
    task = snapshot.snapshot.RevertToSnapshot_Task()
    wait_for_task(task, "Откат к снапшоту")
    print("[+] Снапшот успешно восстановлен")



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

    name = vm_config.get('TARGET_SNAPSHOT_NAME') or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    description = vm_config.get('TARGET_SNAPSHOT_DESCRIPTION') or ""

    print(f"[*] Создание снапшота '{name}' для ВМ {vm.name}...")

    task = vm.CreateSnapshot_Task(
        name=name,
        description=description,
        memory=memory,
        quiesce=quiesce
    )

    wait_for_task(task, description=f"Создание снапшота '{name}'")
    print(f"[+] Снапшот '{name}' успешно создан")
