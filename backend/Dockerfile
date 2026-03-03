FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data

# Install SharekhanApi from GitHub (not on PyPI as standard package)
RUN pip install --no-cache-dir \
    "git+https://github.com/Sharekhan-API/shareconnectpython.git" || true

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
