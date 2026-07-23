#!/data/data/com.termux/files/usr/bin/python3
import os
import subprocess
import time

CONFIG_FILE = "/data/data/com.termux/files/usr/etc/ngircd.conf"

def generate_unique_name():
    """Генерирует уникальное имя на основе MAC-адреса wlan0"""
    try:
        mac = subprocess.check_output(["cat", "/sys/class/net/wlan0/address"], text=True).strip().replace(":", "")
        return f"node-{mac[-6:]}.local"
    except:
        # Если MAC не доступен, используем timestamp
        return f"node-{int(time.time())%10000}.local"

def create_default_config():
    """Создаёт конфиг с уникальным именем, если он отсутствует"""
    if os.path.exists(CONFIG_FILE):
        print(f"[{time.ctime()}] Config already exists, skipping init.")
        return

    my_name = generate_unique_name()
    print(f"[{time.ctime()}] Generating unique server name: {my_name}")

    config_content = f"""[Global]
Name = {my_name}
AdminInfo1 = Mesh IRC
AdminInfo2 = Android
AdminEmail = admin@mesh
Listen = 0.0.0.0
Ports = 6667

[Options]
PAM = no
"""
    with open(CONFIG_FILE, 'w') as f:
        f.write(config_content)
    print(f"[{time.ctime()}] Config created with name {my_name}")

if __name__ == "__main__":
    create_default_config()
