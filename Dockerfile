# Используем официальный образ Python
FROM python:3.14-slim

# Устанавливаем системные зависимости (именно то, что не получалось сделать через apt-get)
RUN apt-get update && apt-get install -y \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота в контейнер
COPY . .

# Команда для запуска бота
CMD ["python", "main.py"]