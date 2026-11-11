# Runs fully offline on the customer's own machine: no data leaves the box.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tracking_audit tracking_audit
COPY scripts scripts
COPY tests tests
RUN python -m unittest discover -s tests -t .
ENTRYPOINT ["python", "-m", "tracking_audit.cli"]
