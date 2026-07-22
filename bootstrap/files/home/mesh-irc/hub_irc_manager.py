#!/data/data/com.termux/files/usr/bin/python3
import socket
import os
import time
import subprocess
import sys

CONFIG_FILE = "/data/data/com.termux/files/usr/etc/ngircd.conf"
UDP_PORT = 6668
PASSWORD = "meshpass"

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
    """Читает имя сервера из секции [Global] конфига"""
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

def main():
    # Создаём базовый конфиг, если отсутствует
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write("""[Global]
Name = android.local
AdminInfo1 = Mesh IRC
AdminInfo2 = Android
AdminEmail = admin@mesh
Listen = 0.0.0.0
Ports = 6667
""")
        restart_ngircd()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_PORT))
    print(f"[{time.ctime()}] UDP server listening on port {UDP_PORT}")
    while True:
        data, addr = sock.recvfrom(1024)
        handle_request(data, addr, sock)

if __name__ == "__main__":
    main()
