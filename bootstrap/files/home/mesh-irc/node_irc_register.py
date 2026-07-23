#!/data/data/com.termux/files/usr/bin/python3
import socket
import subprocess
import time
import os
import sys
import threading

CONFIG_FILE = "/data/data/com.termux/files/usr/etc/ngircd.conf"
UDP_PORT = 6668  # для регистрации
HELLO_PORT = 6669  # для HELLO-пакетов
PASSWORD = "meshpass"
BROADCAST_ADDR = '255.255.255.255'

def get_my_name():
    # Используем сохранённое имя из ID-файла или генерируем
    id_file = "/data/data/com.termux/files/home/.mesh_id"
    if os.path.exists(id_file):
        with open(id_file, 'r') as f:
            name = f.read().strip()
            if name:
                return name
    # fallback
    try:
        mac = subprocess.check_output(["cat", "/sys/class/net/wlan0/address"], 
                                      text=True, stderr=subprocess.DEVNULL).strip().replace(":", "")
        if mac:
            name = f"node-{mac[-6:]}.local"
        else:
            raise Exception("no mac")
    except:
        name = f"node-{int(time.time())%10000}.local"
    # Сохраняем
    with open(id_file, 'w') as f:
        f.write(name)
    return name

def send_udp(msg, ip, port=UDP_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    sock.sendto(msg.encode(), (ip, port))
    try:
        data, _ = sock.recvfrom(1024)
        return data.decode()
    except:
        return None

def update_my_name_in_config(my_name):
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"""[Global]
Name = {my_name}
AdminInfo1 = Mesh IRC
AdminInfo2 = Android Node
AdminEmail = admin@mesh
Listen = 0.0.0.0
Ports = 6667
Compression = no

[Options]
PAM = no
""")
        return

    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()

    in_global = False
    name_found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped != '[Global]':
            in_global = False
        if stripped == '[Global]':
            in_global = True
            new_lines.append(line)
            continue
        if in_global and stripped.startswith('Name ='):
            new_lines.append(f'Name = {my_name}\n')
            name_found = True
            continue
        new_lines.append(line)

    if not name_found:
        for i, line in enumerate(new_lines):
            if line.strip() == '[Global]':
                new_lines.insert(i+1, f'Name = {my_name}\n')
                break

    # Убедимся, что Compression = no есть
    compression_found = any(line.strip().startswith('Compression') for line in new_lines)
    if not compression_found:
        for i, line in enumerate(new_lines):
            if line.strip() == '[Global]':
                new_lines.insert(i+2, 'Compression = no\n')
                break

    # Убедимся, что PAM = no
    has_options = any(line.strip().startswith('[Options]') for line in new_lines)
    if not has_options:
        for i, line in enumerate(new_lines):
            if line.strip() == '[Global]':
                new_lines.insert(i+3, '\n[Options]\nPAM = no\n')
                break
    else:
        pam_found = any(line.strip().startswith('PAM =') for line in new_lines)
        if not pam_found:
            for i, line in enumerate(new_lines):
                if line.strip() == '[Options]':
                    new_lines.insert(i+1, 'PAM = no\n')
                    break

    with open(CONFIG_FILE, 'w') as f:
        f.writelines(new_lines)

def add_hub_to_config(hub_name, hub_ip):
    with open(CONFIG_FILE, 'r') as f:
        content = f.read()
    if f"Name = {hub_name}" in content:
        print(f"Hub {hub_name} already in config")
        return False
    new_section = f"""
[Server]
Name = {hub_name}
Host = {hub_ip}
Port = 6667
MyPassword = {PASSWORD}
PeerPassword = {PASSWORD}
"""
    if not content.endswith("\n"):
        content += "\n"
    content += new_section
    with open(CONFIG_FILE, 'w') as f:
        f.write(content)
    print(f"Added hub {hub_name} to config")
    return True

def restart_ngircd():
    subprocess.run(["pkill", "ngircd"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.Popen(["ngircd"])
    print(f"[{time.ctime()}] Restarted ngircd")

def is_ngircd_running():
    try:
        subprocess.check_output(["pgrep", "ngircd"], stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def listen_for_hello():
    """Слушает HELLO-пакеты и регистрируется при обнаружении нового хаба"""
    my_name = get_my_name()
    update_my_name_in_config(my_name)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', HELLO_PORT))
    print(f"[{time.ctime()}] Listening for HELLO on port {HELLO_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode().strip()
            if not msg.startswith("HELLO"):
                continue
            # Извлекаем имя
            parts = msg.split()
            name = None
            for part in parts:
                if part.startswith("name="):
                    name = part.split("=", 1)[1]
                    break
            if not name:
                continue
            # Игнорируем себя
            if name == my_name:
                continue
            hub_ip = addr[0]
            print(f"[{time.ctime()}] Found hub: {name} at {hub_ip}")
            # Регистрируемся
            reply = send_udp(f"REG {my_name}", hub_ip)
            if reply == "OK":
                print(f"[{time.ctime()}] Registration successful with {name}")
                # Добавляем в конфиг и перезапускаем ngircd
                if add_hub_to_config(name, hub_ip):
                    restart_ngircd()
                else:
                    # Если уже есть, просто убедимся, что ngircd работает
                    if not is_ngircd_running():
                        subprocess.Popen(["ngircd"])
            else:
                print(f"[{time.ctime()}] Registration failed with {name}")
        except Exception as e:
            print(f"Error in listen_for_hello: {e}")

def main():
    # Запускаем прослушивание HELLO в отдельном потоке
    listener_thread = threading.Thread(target=listen_for_hello, daemon=True)
    listener_thread.start()

    # Основной поток будет ждать (или можно сделать бесконечный цикл)
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
