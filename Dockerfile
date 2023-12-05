FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY main.py /app/main.py

CMD ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "5555"]