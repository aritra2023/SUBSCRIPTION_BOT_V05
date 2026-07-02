FROM python:3.11-slim

WORKDIR /app

COPY bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

ENV PYTHONUNBUFFERED=1

CMD ["python3", "bot/main.py"]
