FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

EXPOSE 3000

CMD ["python", "main.py"]