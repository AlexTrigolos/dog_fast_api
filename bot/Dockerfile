FROM python:3.11-slim

WORKDIR /bot

COPY ./requirements.txt /bot/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /bot/requirements.txt

COPY ./src /bot/bot

CMD ["python", "bot/main.py"]
