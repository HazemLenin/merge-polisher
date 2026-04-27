FROM python:3.13-slim

WORKDIR /app

# If you later split runtime/dev deps, copy runtime file instead
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# script.py is the entrypoint in this repo
CMD ["python", "script.py"]