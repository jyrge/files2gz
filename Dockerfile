FROM python:3.12.5-slim
WORKDIR /app
RUN mkdir /app/source /app/target /app/logs
ENV FILES2GZ_SOURCE_DIR="/app/source" \
    FILES2GZ_TARGET_DIR="/app/target" \
    FILES2GZ_LOG_DIR="/app/logs" \
    FILES2GZ_LOG_LEVEL="info"

COPY files2gz.py requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT [ "python", "files2gz.py" ]
