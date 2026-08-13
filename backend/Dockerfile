FROM python:3.11.9-slim

# Dépendances système
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 tesseract-ocr \
    build-essential g++ cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY tests/ ./tests/
COPY pytest.ini .
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY start.sh .

RUN mkdir -p uploads models
RUN chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
