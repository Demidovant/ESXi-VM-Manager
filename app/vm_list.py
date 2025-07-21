from pyVmomi import vim
from esxi_connect import connect_to_host, disconnect_from_host
from vm_snapshot import list_all_snapshots_names

def get_vm_info(vm):
    summary = vm.summary
    config = summary.config
    runtime = summary.runtime
    return {
        'obj': vm,
        'name': config.name,
        'guestFullName': config.guestFullName,
        'numCpu': config.numCpu,
        'memorySizeMB': config.memorySizeMB,
        'powerState': runtime.powerState,
        'ipAddress': summary.guest.ipAddress if summary.guest else None,
        'vmPathName': config.vmPathName
    }

def list_vms(si):
    content = si.RetrieveContent()
    vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    vms = vm_view.view
    info_list = [get_vm_info(vm) for vm in vms]
    vm_view.Destroy()
    return info_list


def get_vm_by_name(si, name):
    content = get_content(si)
    vm_view = content.viewManager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True)
    try:
        for vm in vm_view.view:
            if vm.name == name:
                return vm
        print(f"[!] ВМ {name} не найдена !!!")
        return None
    finally:
        vm_view.Destroy()


def get_content(si):
    content = si.RetrieveContent()
    return content


if __name__ == "__main__":
    si = connect_to_host()

    try:
        for vm in list_vms(si):
            print(f"{vm['name']}: {vm['powerState']} | {vm['numCpu']} CPU | {vm['memorySizeMB'] / 1024} GB | {vm['ipAddress']} | {vm['guestFullName']} | {vm['vmPathName']}")
            snapshots = list_all_snapshots_names(vm['obj'])
            if snapshots:
                print("Список всех снапшотов:")
                for snap in snapshots:
                    print("-", snap)
    finally:
        disconnect_from_host(si)
