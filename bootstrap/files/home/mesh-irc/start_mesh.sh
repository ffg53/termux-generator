#!/data/data/com.termux/files/usr/bin/bash

# Убиваем старый ngIRCd, если есть
pkill ngircd 2>/dev/null

# Инициализируем конфиг (генерируем уникальное имя, если конфига нет)
python3 ~/mesh-irc/init_mesh.py

# Запускаем ngIRCd в фоне
ngircd --nodaemon 2>&1 &

# Запускаем UDP-сервер (хаб)
python3 ~/mesh-irc/hub_irc_manager.py &
