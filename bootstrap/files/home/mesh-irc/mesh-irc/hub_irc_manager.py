#!/data/data/com.termux/files/usr/bin/python3
import socket
import os
import time
import subprocess
import sys
import threading

try:
    import netifaces
except ImportError:
    print("netifaces not installed, falling back to manual broadcast")
    netifaces = None

CONFIG_FILE = "/data/data/com.termux/files/usr/etc/ngircd.conf"
UDP_PORT = 6668      # для регистрации
HELLO_PORT = 6669    # для HELLO-пакетов
PASSWORD = "meshpass"
PREFERRED_INTERFACES = ['ap0', 'wlan0', 'eth0']  # приоритетные интерфейсы

def restart_ngircd():
    subprocess.run(["pkill", "ngircd"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.Popen(["ngircd"])
    print(f"[{time.ctime()}] Restarted ngircd")

def read_config():
    if not os.path.exists(CONFIG_FILE):
        return ""
    with open(CONFIG_FILE, 'r') as f:
        return f.read()

def write_config(content):
    with open(CONFIG_FILE, 'w') as f:
        f.write(content)

def add_node_to_config(node_name):
    content = read_config()
    if f"Name = {node_name}" in content:
        print(f"[{time.ctime()}] Node {node_name} already registered")
        return False
    new_section = f"""
[Server]
Name = {node_name}
Passive = yes
MyPassword = {PASSWORD}
PeerPassword = {PASSWORD}
"""
    if not content.endswith("\n"):
        content += "\n"
    content += new_section
    write_config(content)
    print(f"[{time.ctime()}] Added node {node_name}")
    return True

def get_my_server_name():
    try:
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('Name ='):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        name = parts[1].strip()
                        if name:
                            return name
    except Exception as e:
        print(f"Error reading config: {e}")
    return None

def get_broadcast_address():
    """Вычисляет широковещательный адрес для приоритетного интерфейса."""
    if netifaces is None:
        print("netifaces unavailable, using fallback 255.255.255.255")
        return '255.255.255.255'

    # Сначала проверяем приоритетные интерфейсы
    for iface in PREFERRED_INTERFACES:
        if iface not in netifaces.interfaces():
            continue
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET not in addrs:
            continue
        for addr in addrs[netifaces.AF_INET]:
            if 'addr' in addr and 'netmask' in addr and not addr['addr'].startswith('127.'):
                ip = addr['addr']
                mask = addr['netmask']
                ip_parts = [int(x) for x in ip.split('.')]
                mask_parts = [int(x) for x in mask.split('.')]
                broadcast_parts = [str(ip_parts[i] | (~mask_parts[i] & 255)) for i in range(4)]
                bc_addr = '.'.join(broadcast_parts)
                print(f"[{time.ctime()}] Using {iface} IP {ip}, broadcast {bc_addr}")
                return bc_addr

    # Если не нашли, пробуем любой интерфейс (кроме loopback)
    for iface in netifaces.interfaces():
        if iface == 'lo':
            continue
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET not in addrs:
            continue
        for addr in addrs[netifaces.AF_INET]:
            if 'addr' in addr and 'netmask' in addr and not addr['addr'].startswith('127.'):
                ip = addr['addr']
                mask = addr['netmask']
                ip_parts = [int(x) for x in ip.split('.')]
                mask_parts = [int(x) for x in mask.split('.')]
                broadcast_parts = [str(ip_parts[i] | (~mask_parts[i] & 255)) for i in range(4)]
                bc_addr = '.'.join(broadcast_parts)
                print(f"[{time.ctime()}] Using fallback {iface} IP {ip}, broadcast {bc_addr}")
                return bc_addr

    print("[{time.ctime()}] No suitable interface, using fallback 255.255.255.255")
    return '255.255.255.255'

def send_hello():
    """Периодически отправляет HELLO-пакеты на широковещательный адрес."""
    bc_addr = get_broadcast_address()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    name = get_my_server_name() or "unknown.local"
    msg = f"HELLO name={name}".encode()
    while True:
        try:
            sock.sendto(msg, (bc_addr, HELLO_PORT))
            print(f"[{time.ctime()}] Sent HELLO from {name} to {bc_addr}:{HELLO_PORT}")
        except Exception as e:
            print(f"HELLO send error: {e}")
        time.sleep(5)  # каждые 5 секунд

def handle_request(data, addr, sock):
    msg = data.decode().strip().split()
    if not msg:
        return
    cmd = msg[0]
    if cmd == "GET_HUB_NAME":
        hub_name = get_my_server_name() or "unknown.local"
        sock.sendto(hub_name.encode(), addr)
        print(f"[{time.ctime()}] Sent hub name '{hub_name}' to {addr}")
    elif cmd == "REG" and len(msg) > 1:
        node_name = msg[1]
        if add_node_to_config(node_name):
            restart_ngircd()
        sock.sendto(b"OK", addr)
    else:
        sock.sendto(b"ERROR", addr)

def main():
    # Создаём конфиг, если отсутствует
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write("""[Global]
Name = android.local
AdminInfo1 = Mesh IRC
AdminInfo2 = Android
AdminEmail = admin@mesh
Listen = 0.0.0.0
Ports = 6667
Compression = no

[Options]
PAM = no
""")
        restart_ngircd()
    else:
        # Проверяем, есть ли Compression = no, и добавляем при необходимости
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        if not any('Compression' in line for line in lines):
            # Добавляем в секцию Global
            with open(CONFIG_FILE, 'a') as f:
                f.write("\nCompression = no\n")
            print(f"[{time.ctime()}] Added Compression = no to config")

    # Запускаем поток для HELLO-рассылки
    hello_thread = threading.Thread(target=send_hello, daemon=True)
    hello_thread.start()

    # Основной UDP-сервер для регистрации на порту 6668
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', UDP_PORT))
    print(f"[{time.ctime()}] UDP server listening on port {UDP_PORT}")
    while True:
        data, addr = sock.recvfrom(1024)
        handle_request(data, addr, sock)

if __name__ == "__main__":
    main()
