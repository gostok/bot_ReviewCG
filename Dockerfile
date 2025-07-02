FROM python:3.12-slim
WORKDIR /bot_ReviewCG
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "run_bot.py"]
