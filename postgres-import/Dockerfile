FROM python:3.11-slim

WORKDIR /app

# Installiere Dependencies
RUN pip install --no-cache-dir asyncpg lxml xmltodict

# Kopiere Skripte
COPY import_tei_to_postgres.py .
COPY schema.sql .

# Hilfe-Command als Default
CMD ["python", "import_tei_to_postgres.py", "--help"]