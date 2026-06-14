FROM python:3.12-slim

WORKDIR /app

# Instala dependências primeiro (cache de camadas Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
