# Start from the official Airflow image
FROM apache/airflow:2.9.2

USER root
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends docker.io && \
    apt-get clean
RUN usermod -aG docker airflow
USER airflow

# --- THIS IS THE CHANGE ---
# Copy the NEW, Airflow-specific requirements file
COPY requirements-airflow.txt .

# Install the Python dependencies from that file
RUN pip install --no-cache-dir -r requirements-airflow.txt