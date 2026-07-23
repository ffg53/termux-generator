#!/data/data/com.termux/files/usr/bin/python3
import socket
import os
import time
import subprocess
import sys
import threading

CONFIG_FILE = "/data/data/com.termux/files/usr/etc/ngircd.conf"
UDP_PORT = 6668  # для регистрации
HELLO_PORT = 6669  # для HELLO-пакетов
PASSWORD = "meshpass"
BROADCAST_ADDR = '255.255.255.255'

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

def send_hello():
    """Функция для периодической рассылки HELLO-пакетов"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    name = get_my_server_name() or "unknown.local"
    msg = f"HELLO name={name}".encode()
    while True:
        try:
            sock.sendto(msg, (BROADCAST_ADDR, HELLO_PORT))
            print(f"[{time.ctime()}] Sent HELLO from {name}")
        except Exception as e:
            print(f"HELLO send error: {e}")
        time.sleep(5)  # каждые 5 секунд

def main():
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

    # Запускаем поток для HELLO-рассылки
    hello_thread = threading.Thread(target=send_hello, daemon=True)
    hello_thread.start()

    # Основной UDP-сервер для регистрации
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', UDP_PORT))
    print(f"[{time.ctime()}] UDP server listening on port {UDP_PORT}")
    while True:
        data, addr = sock.recvfrom(1024)
        handle_request(data, addr, sock)

if __name__ == "__main__":
    main()
