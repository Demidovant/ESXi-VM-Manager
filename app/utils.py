import csv

def parse_vm_csv(csv_file):
    vm_configs = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            config = {
                'GROUP_NAME': row.get('groupName', ''),
                'SOURCE_VM_NAME': row.get('sourceVM', ''),
                'TARGET_VM_NAME': row.get('vmName', ''),
                'TARGET_VM_HOSTNAME': row.get('vmHostname', ''),
                'TARGET_DATASTORE_NAME': row.get('targetDatastore', ''),
                'NETWORK_NAME': row.get('adaptersLan', ''),
                'CPU_COUNT': row.get('cpuCount', ''),
                'MEMORY_MB': row.get('MemoryMB', ''),
                'STATIC_IP': row.get('ip', ''),
                'NETMASK': row.get('netmask', ''),
                'GATEWAY': row.get('ipGateway', ''),
                'DNS': row.get('ipDns', ''),
                'SOURCE_SNAPSHOT_NAME': row.get('sourceSnapshotName', ''),
                'OS_USER_NAME': row.get('osUserName', ''),
                'OS_USER_PASSWORD': row.get('osUserPassword', ''),
                'TARGET_SNAPSHOT_NAME': row.get('targetSnapshotName', ''),
                'TARGET_SNAPSHOT_DESCRIPTION': row.get('targetSnapshotDescription', '')
            }
            if config["TARGET_VM_NAME"]:
                if not config["GROUP_NAME"]:
                    config["GROUP_NAME"] = "[НЕТ ГРУППЫ]"
                vm_configs.append(config)

    # Формируем список групп
    groups = []
    if any(vm['GROUP_NAME'] == "[НЕТ ГРУППЫ]" for vm in vm_configs):
        groups.append("[НЕТ ГРУППЫ]")
    for vm in vm_configs:
        group_name = vm['GROUP_NAME']
        if group_name not in groups:
            groups.append(group_name)

    return vm_configs, groups