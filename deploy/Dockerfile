FROM python:3.12-slim
RUN useradd -r -u 10001 app && mkdir /data && chown app /data
COPY trackgate_api.py /app/trackgate_api.py
USER app
ENV PYTHONUNBUFFERED=1 TRACKGATE_DATA=/data PORT=8095
EXPOSE 8095
CMD ["python", "/app/trackgate_api.py"]
