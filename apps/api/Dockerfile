FROM python:3.12.8-slim-bookworm

WORKDIR /app

RUN addgroup --system veta && adduser --system --ingroup veta veta

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY app ./app
RUN mkdir -p /app/media && chown -R veta:veta /app

USER veta
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
