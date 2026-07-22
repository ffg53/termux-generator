#!/data/data/com.termux/files/usr/bin/python3
import socket
import subprocess
import time
import os
import sys

CONFIG_FILE = "/data/data/com.termux/files/usr/etc/ngircd.conf"
UDP_PORT = 6668
PASSWORD = "meshpass"

def get_gateway_ip():
    try:
        route = subprocess.check_output(["netstat", "-rn"], text=True)
        for line in route.splitlines():
            if line.startswith("0.0.0.0"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass
    return None

def get_my_name():
    try:
        mac = subprocess.check_output(["cat", "/sys/class/net/wlan0/address"], text=True).strip().replace(":", "")
        return f"node-{mac[-6:]}.local"
    except:
        return f"node-{int(time.time())%10000}.local"

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
    """Обновляет имя сервера в секции [Global]"""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"""[Global]
Name = {my_name}
AdminInfo1 = Mesh IRC
AdminInfo2 = Android Node
AdminEmail = admin@mesh
Listen = 0.0.0.0
Ports = 6667
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
        # Вставляем Name сразу после [Global]
        for i, line in enumerate(new_lines):
            if line.strip() == '[Global]':
                new_lines.insert(i+1, f'Name = {my_name}\n')
                break

    with open(CONFIG_FILE, 'w') as f:
        f.writelines(new_lines)

def add_hub_to_config(hub_name, hub_ip):
    """Добавляет секцию [Server] для хаба"""
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

def main():
    gateway = get_gateway_ip()
    if not gateway:
        print("No gateway found")
        sys.exit(1)
    my_name = get_my_name()
    print(f"My name: {my_name}")
    reply = send_udp("GET_HUB_NAME", gateway)
    if not reply:
        print("No response from hub")
        sys.exit(0)
    hub_name = reply.strip()
    print(f"Hub name: {hub_name}")
    reply = send_udp(f"REG {my_name}", gateway)
    if reply != "OK":
        print("Registration failed")
        sys.exit(1)
    print("Registration successful")

    # Обновляем своё имя в конфиге
    update_my_name_in_config(my_name)
    # Добавляем хаб как сервер
    if add_hub_to_config(hub_name, gateway):
        restart_ngircd()

if __name__ == "__main__":
    main()
