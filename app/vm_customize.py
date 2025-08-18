from pyVmomi import vim
import time
import platform
import subprocess
from vm_operations import vm_power_on, vm_power_off, vm_detect_os_type, wait_for_task


def customize_vm_os(service_instance, vm, vm_config):
    """
    Настраивает существующую ВМ после запуска
    :param service_instance: подключение к ESXi
    :param vm: объект виртуальной машины (vim.VirtualMachine)
    :param static_ip: статический IP
    :param netmask: маска сети
    :param gateway: шлюз
    :param dns: DNS сервер
    :param network_name: имя сети (если нужно изменить)
    :param username: пользователь гостевой ОС
    :param password: пароль гостевой ОС
    :param timeout: время ожидания готовности ОС (сек)
    """

    static_ip = vm_config.get('STATIC_IP')
    netmask = vm_config.get('NETMASK')
    gateway = vm_config.get('GATEWAY')
    dns = vm_config.get('DNS')
    network_name = vm_config.get('NETWORK_NAME')
    username = vm_config.get('OS_USER_NAME')
    password = vm_config.get('OS_USER_PASSWORD')
    hostname = vm_config.get('TARGET_VM_HOSTNAME')

    if not vm:
        raise ValueError("Не удается произвести настройку ВМ. Не передан объект виртуальной машины")

    os_type = vm_detect_os_type(vm)
    print(f"[*] Обнаружена ОС: {os_type}")


    # Запускаем ВМ если она выключена
    if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
        print("[*] Запускаем ВМ для настройки...")
        vm_power_on(vm)

    # Ожидаем полной инициализации гостевой ОС
    wait_for_guest_ready(vm, service_instance, timeout=300)

    # Если указаны сетевые настройки
    if os_type == 'windows':
        customize_windows(vm, static_ip, netmask, gateway, dns, username, password, service_instance, hostname)
    elif os_type in ['ubuntu', 'debian']:
        customize_ubuntu_debian(vm, static_ip, netmask, gateway, dns, username, password, service_instance, hostname)
    elif os_type in ['centos', 'redhat']:
        customize_centos(vm, static_ip, netmask, gateway, dns, username, password, service_instance, hostname)
    elif os_type == 'linux':
        customize_generic_linux(vm, static_ip, netmask, gateway, dns, username, password, service_instance, hostname)
    else:
        print(f"[!] Настройка для ОС {os_type} не реализована")

    print("=" * 70)


def wait_for_guest_ready(vm, service_instance, timeout=300):
    """
    Улучшенное ожидание готовности гостевой ОС с пересозданием объекта ВМ.
    """
    def refresh_vm(vm, service_instance):
        content = service_instance.RetrieveContent()
        vm_name = vm.name
        vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        try:
            for new_vm in vm_view.view:
                if new_vm.name == vm_name:
                    return new_vm
        finally:
            vm_view.Destroy()
        raise Exception(f"Не удалось обновить объект VM: {vm.name}")

    print("[*] Расширенная проверка готовности гостевой ОС...")
    start_time = time.time()
    last_report_time = start_time
    tools_ready = False
    ip_detected = False
    ping_success = False

    while time.time() - start_time < timeout:
        try:
            vm = refresh_vm(vm, service_instance)
            current_time = time.time()

            # Проверка 1: VMware Tools
            tools_status = getattr(vm.guest, 'toolsRunningStatus', 'guestToolsNotRunning')
            if tools_status == 'guestToolsRunning':
                if not tools_ready:
                    print("[+] VMware Tools работают")
                tools_ready = True

            # Проверка 2: Получен IP-адрес
            ip_address = None
            if tools_ready and vm.guest and vm.guest.net:
                for nic in vm.guest.net:
                    if hasattr(nic, 'ipConfig') and nic.ipConfig:
                        for ip in nic.ipConfig.ipAddress:
                            if ip.state == 'preferred':
                                ip_address = ip.ipAddress
                                break
                    elif nic.ipAddress:
                        # fallback для старых версий ESXi
                        ip_address = nic.ipAddress[0]
                    if ip_address:
                        break
                if ip_address:
                    if not ip_detected:
                        print(f"[+] Обнаружен IP: {ip_address}")
                    ip_detected = True

            # Проверка 3: ping
            if ip_address and not ping_success:
                if _ping_host(ip_address):
                    print(f"[+] Успешный ping: {ip_address}")
                    ping_success = True

            # Все проверки пройдены
            if tools_ready and ip_detected and ping_success:
                print("[+++] Гостевая ОС полностью готова")
                return True

            # Периодический отчёт
            if current_time - last_report_time > 30:
                status = {
                    "Tools": "Ready" if tools_ready else "Waiting",
                    "IP": ip_address or "Waiting",
                    "Ping": "Success" if ping_success else "Waiting"
                }
                print(f"[*] Текущий статус: {status}")
                last_report_time = current_time

            time.sleep(5)

        except Exception as e:
            print(f"[!] Ошибка проверки состояния: {str(e)}")
            time.sleep(10)

    # Подробный отчёт о таймауте
    problems = []
    if not tools_ready:
        problems.append("VMware Tools не работают")
    if not ip_detected:
        problems.append("IP не получен")
    if not ping_success:
        problems.append("ping не проходит")

    raise Exception(f"Таймаут ожидания готовности гостевой ОС: {', '.join(problems)}")


def _ping_host(ip_address, timeout=2):
    """Проверяет доступность хоста через ping"""
    try:
        if platform.system().lower() == "windows":
            command = f"ping -n 1 -w {timeout * 1000} {ip_address}"
        else:
            command = f"ping -c 1 -W {timeout} {ip_address}"

        return subprocess.call(command,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0
    except:
        return False



def customize_windows(vm, static_ip, netmask, gateway, dns, username, password, si, hostname):
    """Настройка Windows ВМ"""
    print("[*] Начинаем настройку Windows ВМ")

    ps_script = f"""
    # Настройка сети
    $adapter = Get-NetAdapter | Where-Object {{ $_.Status -eq 'Up' }}
    Write-host $adapter.ifIndex
    
    if ($adapter) {{
        Set-NetIPInterface -InterfaceIndex $adapter.ifIndex -Dhcp Disabled
        
        # Очистка старых IP
        Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
        # Очистка шлюза
        Remove-NetRoute -InterfaceIndex $adapter.ifIndex -DestinationPrefix "0.0.0.0/0" -Confirm:$false -ErrorAction SilentlyContinue
        # Сброс всех DNS-серверов
        Set-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -ResetServerAddresses

        # Установка нового IP и шлюза
        New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress {static_ip} -PrefixLength {netmask} -DefaultGateway {gateway}
        # Настройка DNS
        Set-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -ServerAddresses '{dns}'
    }}

    # Настройка hostname
    Rename-Computer -NewName '{hostname}' -Force -PassThru
    """

    try:
        _execute_guest_command(
            vm,
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            f"-Command \"{ps_script}\"",
            username or "Administrator",
            password,
            si
        )
    except Exception as e:
        print(f"[X] Ошибка: {e}")

    print("[+] Настройка Windows завершена")


def customize_ubuntu_debian(vm, static_ip, netmask, gateway, dns, username, password, service_instance, hostname):
    """Настройка Ubuntu/Debian ВМ"""
    print("[*] Начинаем настройку Ubuntu/Debian ВМ")

    print("[*] Настраиваем hostname...")
    # Установка /etc/hostname
    cmd = f"-c 'echo \"{password}\" | sudo -S sh -c \"echo \\\"{hostname}\\\" > /etc/hostname\"'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    # Обновление /etc/hosts
    cmd = f"-c 'echo \"{password}\" | sudo -S sh -c \"sed -i \\\"/127.0.1.1/d\\\" /etc/hosts && echo \\\"127.0.1.1 {hostname}\\\" >> /etc/hosts\"'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    # Применение hostname
    cmd = f"-c 'echo \"{password}\" | sudo -S hostnamectl set-hostname {hostname}'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    print("[+] Настройка hostname завершена")

    yaml_content = f"""network:
        ethernets:
            ens33:
                addresses:
                - {static_ip}/{netmask}
                nameservers:
                    addresses:
                    - {dns}
                    search: []
                routes:
                -   to: default
                    via: {gateway}
        version: 2
    """

    # Очистка старых конфигов netplan
    print("[*] Удаляем старые конфиги Netplan...")
    cmd = f"-c 'echo \"{password}\" | sudo -S sh -c \"rm -f /etc/netplan/*\"'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    # Отключаем cloud-init управление сетью
    print("[*] Отключаем cloud-init управление сетью...")
    cmd = f"-c 'echo \"{password}\" | sudo -S sh -c \"echo \\\"network: {{config: disabled}}\\\" > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg\"'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    # Экранируем кавычки и новые строки для bash
    yaml_content_escaped = yaml_content.replace("'", "'\"'\"'").replace("\n", "\\n")

    print("[*] Записываем netplan конфиг...")
    cmd = f"-c 'echo \"{password}\" | sudo -S sh -c \"printf \\\"{yaml_content_escaped}\\\" > /etc/netplan/01-netcfg.yaml\"'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    # Применение конфига
    print("[*] Применяем Netplan...")
    cmd = f"-c 'echo \"{password}\" | sudo -S netplan apply && sudo -S shutdown now'"
    _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    # # Перезапуск networking (для надежности)
    # print("[*] Перезапускаем networking сервис...")
    # cmd = f"-c 'echo \"{password}\" | sudo -S systemctl restart systemd-networkd'"
    # _execute_guest_command(vm, "/bin/bash", cmd, username, password, service_instance)

    print("[+] Настройка сети завершена")
    print("[+] Настройка Ubuntu/Debian завершена")



def customize_centos(vm, static_ip, netmask, gateway, dns, username, password, hostname):
    """Настройка CentOS/RHEL ВМ"""
    print("[*] Начинаем настройку CentOS ВМ")

    commands = [
        "cat > /etc/sysconfig/network-scripts/ifcfg-eth0 <<EOF",
        "DEVICE=eth0",
        "BOOTPROTO=none",
        "ONBOOT=yes",
        f"IPADDR={static_ip}",
        f"NETMASK={netmask}",
        f"GATEWAY={gateway}",
        f"DNS1={dns}",
        "EOF",

        # Настройка hostname
        f"echo '{hostname}' > /etc/hostname",
        f"hostnamectl set-hostname {hostname}",

        # Обновление /etc/hosts
        f"sed -i '/127.0.1.1/d' /etc/hosts || true",
        f"grep -q '127.0.0.1' /etc/hosts && sed -i 's/^127.0.0.1.*/127.0.0.1 localhost {hostname}/' /etc/hosts || echo '127.0.0.1 localhost {hostname}' >> /etc/hosts",

        # Перезапуск сети
        "systemctl restart network"
    ]

    _execute_guest_commands(vm, commands, username or "root", password)
    print("[+] Настройка CentOS завершена")


def customize_generic_linux(vm, static_ip, netmask, gateway, dns, username, password, service_instance, hostname):
    """Настройка для неизвестных Linux дистрибутивов"""
    print("[*] Пытаемся настроить generic Linux")

    try:
        customize_ubuntu_debian(vm, static_ip, netmask, gateway, dns, username, password, hostname)
    except Exception as e:
        print(f"[!] Ubuntu метод не сработал: {str(e)}")
        try:
            customize_centos(vm, static_ip, netmask, gateway, dns, username, password, hostname)
        except Exception as e:
            raise Exception(f"Не удалось настроить Linux: {str(e)}")


def _execute_guest_command(vm, program_path, arguments, username, password, service_instance=None):
    """Выполняет одну команду в гостевой ОС"""
    try:
        if service_instance is None:
            raise Exception("Не передан service_instance для запуска команды в гостевой ОС")

        # print(f"[+] Получаем менеджер процессов гостевой ОС...")
        process_manager = service_instance.content.guestOperationsManager.processManager

        # print(f"[+] Аутентификация с пользователем '{username}'...")
        auth = vim.vm.guest.NamePasswordAuthentication(
            username=username,
            password=password
        )

        pretty_cmd = arguments.replace("\\n", "\n")
        print("[*] Подготовка команды:")
        print(program_path + " " + pretty_cmd)
        spec = vim.vm.guest.ProcessManager.ProgramSpec(
            programPath=program_path,
            arguments=arguments
        )

        print(f"[+] Выполняем команду в гостевой ОС...")
        pid = process_manager.StartProgramInGuest(vm, auth, spec)

        if not pid:
            raise Exception("Команда вернула пустой PID (ошибка запуска)")

        print(f"[✓] Команда успешно запущена, PID: {pid}")

        return pid

    except vim.fault.InvalidGuestLogin as e:
        raise Exception(f"[Ошибка] Неверный логин или пароль для гостевой ОС: {str(e)}")
    except vim.fault.GuestOperationsFault as e:
        raise Exception(f"[Ошибка] Ошибка операций в гостевой ОС: {str(e)}")
    except vim.fault.ToolsUnavailable as e:
        raise Exception(f"[Ошибка] VMware Tools недоступны или не запущены: {str(e)}")
    except Exception as e:
        raise Exception(f"[Ошибка] Не удалось выполнить команду: {str(e)}")



def _execute_guest_commands(vm, commands, username, password, service_instance):
    """Выполняет несколько команд в гостевой ОС"""
    for cmd in commands:
        _execute_guest_command(
            vm,
            "/bin/bash",
            f"-c \"{cmd}\"",
            username,
            password,
            service_instance
        )



def _mask_to_prefix(netmask):
    """Конвертирует маску в префикс CIDR"""
    return sum(bin(int(x)).count('1') for x in netmask.split('.'))


def customize_vm_hardware(vm, vm_config):
    """
    Меняет конфигурацию CPU и RAM на уже существующей ВМ.
    Если ВМ включена — сначала выключает, затем включает обратно.
    """
    print(f"[*] Начинаем изменение аппаратной конфигурации ВМ '{vm.name}'...")

    cpu_count = int(cpu) if (cpu := vm_config.get('CPU_COUNT')) else None
    memory_mb = int(mem) if (mem := vm_config.get('MEMORY_MB')) else None
    network_name = vm_config.get('NETWORK_NAME')

    # Получаем текущее состояние ВМ
    was_powered_on = vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn

    if was_powered_on:
        vm_power_off(vm)

    try:
        # Создаем спецификацию новой конфигурации
        config_spec = vim.vm.ConfigSpec(
            numCPUs=cpu_count,
            memoryMB=memory_mb,
            numCoresPerSocket=cpu_count,  # Все ядра в одном сокете
            cpuHotAddEnabled=True,  # Включение HotAdd CPU
            memoryHotAddEnabled=True  # Включение HotAdd RAM
        )

        # Если указано сетевое имя - меняем сетевую карту
        if network_name:
            # Получаем список всех сетей на хосте
            host = vm.runtime.host
            network = None
            for net in host.network:
                if net.name == network_name:
                    network = net
                    break

            if not network:
                raise Exception(f"Сеть '{network_name}' не найдена на хосте")

            # Находим первый сетевой адаптер в конфигурации ВМ
            for dev in vm.config.hardware.device:
                if isinstance(dev, vim.vm.device.VirtualEthernetCard):
                    # Создаем спецификацию изменения устройства
                    nic_spec = vim.vm.device.VirtualDeviceSpec()
                    nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                    nic_spec.device = dev

                    # Создаем правильный backing в зависимости от типа сети
                    if isinstance(network, vim.Network):
                        nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                        nic_spec.device.backing.network = network
                        nic_spec.device.backing.deviceName = network_name
                    elif isinstance(network, vim.dvs.DistributedVirtualPortgroup):
                        nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                        nic_spec.device.backing.port = vim.dvs.PortConnection()
                        nic_spec.device.backing.port.portgroupKey = network.key
                        nic_spec.device.backing.port.switchUuid = network.config.distributedVirtualSwitch.uuid

                    # Обновляем connectable
                    nic_spec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                    nic_spec.device.connectable.connected = True
                    nic_spec.device.connectable.startConnected = True

                    # Добавляем изменение в конфигурацию
                    if not hasattr(config_spec, 'deviceChange'):
                        config_spec.deviceChange = []
                    config_spec.deviceChange.append(nic_spec)

                    print(f"[*] Меняем сетевой адаптер на сеть '{network_name}'...")
                    break

        print(f"[*] Применяем конфигурацию: {cpu_count} CPU, {memory_mb} MB RAM" +
              (f", сеть '{network_name}'" if network_name else "") + "...")
        task = vm.ReconfigVM_Task(config_spec)
        wait_for_task(task, "Изменение конфигурации ВМ")
        print("[+] Конфигурация ВМ успешно обновлена.")

        print("=" * 70)

        if was_powered_on:
            print("[*] Включаем ВМ так как изначально она была включена...")
            vm_power_on(vm)

    except Exception as e:
        print(f"[-] Ошибка при изменении конфигурации ВМ: {str(e)}")
        if was_powered_on:
            print("[*] Включаем ВМ так как изначально она была включена...")
            vm_power_on(vm)
        raise