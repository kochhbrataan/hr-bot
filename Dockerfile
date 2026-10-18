FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads

ENV PORT=8000
ENV DB_PATH=/data/hr_bot.db
ENV UPLOAD_DIR=/data/uploads

EXPOSE 8000

CMD ["python", "main.py"]
