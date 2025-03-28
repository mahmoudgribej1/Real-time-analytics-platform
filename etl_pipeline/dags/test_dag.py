from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def hello_world():
    print("Hello, world!")

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 3, 17),
}

with DAG(
    'hello_world_dag',
    default_args=default_args,
    description='A simple hello world DAG for testing',
    schedule_interval=None,  # Set to None for manual trigger
    catchup=False,
) as dag:
    task = PythonOperator(
        task_id='hello_task',
        python_callable=hello_world
    )
