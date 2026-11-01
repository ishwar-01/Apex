# Same application, packaged for Render (or any Docker host). OCR needs the Tesseract binary, hence Docker instead of Render's native Python runtime.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_CLIENT_SHOW_ERROR_DETAILS=none \
    LOAN_APP_DATA_DIR=/var/data/loan_app LOAN_APP_REQUIRE_ENV_PASSWORDS=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN chmod +x docker-entrypoint.sh && chown -R app:app /app

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/_stcore/health' % os.environ.get('PORT','8501'), timeout=4)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Render supplies $PORT; locally it falls back to 8501. Binds to 0.0.0.0 so the platform proxy can reach it.
CMD ["sh", "-c", "exec streamlit run app/streamlit_app.py --server.address 0.0.0.0 --server.port ${PORT:-8501}"]
