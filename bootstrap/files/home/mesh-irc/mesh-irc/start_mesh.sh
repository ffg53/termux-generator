#!/data/data/com.termux/files/usr/bin/bash

# Убиваем старые процессы
pkill ngircd 2>/dev/null
pkill -f hub_irc_manager.py 2>/dev/null
pkill -f node_irc_register.py 2>/dev/null

# Инициализируем конфиг (генерируем уникальное имя, если конфига нет)
python3 ~/mesh-irc/init_mesh.py

# Запускаем ngIRCd в фоне
ngircd --nodaemon 2>&1 &

# Запускаем UDP-сервер (хаб) + HELLO-рассылку
python3 ~/mesh-irc/hub_irc_manager.py &

# Запускаем слушатель HELLO и регистратор
python3 ~/mesh-irc/node_irc_register.py &

# Ждём
while true; do
    sleep 60
done
