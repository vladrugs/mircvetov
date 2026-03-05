#!/usr/bin/env bash
# Установка системных зависимостей
apt-get update
apt-get install -y libzbar0

# Установка Python зависимостей
pip install -r requirements.txt