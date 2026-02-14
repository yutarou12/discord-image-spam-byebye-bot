FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel
RUN python -m pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "main.py"]