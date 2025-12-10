FROM python:3.13.5-slim-bookworm

# Crea y entra al directorio de la app (en este caso, la app se llama ' web ')
WORKDIR /app

# Copia dependencias y app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
