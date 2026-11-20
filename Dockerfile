FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RADAR_DATA=/var/lib/radar
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=radar_ca if [ -f /run/secrets/radar_ca ]; then cp /run/secrets/radar_ca /etc/ssl/certs/ca-certificates.crt; fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt PIP_CERT=/etc/ssl/certs/ca-certificates.crt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home radar && mkdir -p /var/lib/radar && chown radar:radar /var/lib/radar
COPY --chown=radar:radar radar ./radar
COPY --chown=radar:radar data ./data
USER radar
CMD ["uvicorn","radar.api:app","--host","0.0.0.0","--port","8170"]
