from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import pandas as pd
from sqlalchemy import create_engine, text

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 3, 16),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
}


def create_food_delivery_database(**kwargs):
    """
    Connect to the default 'postgres' DB and create the 'food_delivery' database if it doesn't exist.
    """
    # Connect to the default database "postgres"
    engine = create_engine("postgresql+psycopg2://airflow:airflow@postgres:5432/postgres")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname='food_delivery'"))
        exists = result.scalar()
        if not exists:
            # Commit the current transaction before creating a new DB
            conn.execute(text("COMMIT"))
            conn.execute(text("CREATE DATABASE food_delivery"))
            print("Created food_delivery database")
        else:
            print("food_delivery database already exists")


def load_csv_to_postgres(**kwargs):
    """
    Connects to the 'food_delivery' database, creates the necessary tables (if not exist),
    and loads CSV data into them.
    """
    # Connect to the target "food_delivery" database
    engine = create_engine("postgresql+psycopg2://airflow:airflow@postgres:5432/food_delivery")

    # Table definitions (matching your data-generation output)
    table_definitions = {
        "cities": """
            CREATE TABLE IF NOT EXISTS cities (
                city_id INTEGER PRIMARY KEY,
                city_name VARCHAR(100),
                governorate VARCHAR(100),
                latitude FLOAT,
                longitude FLOAT,
                country VARCHAR(50)
            )
        """,
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username VARCHAR(100),
                email VARCHAR(100),
                password VARCHAR(100),
                address VARCHAR(200),
                city_id INTEGER,
                registration_date TIMESTAMP
            )
        """,
        "restaurants": """
            CREATE TABLE IF NOT EXISTS restaurants (
                restaurant_id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                description TEXT,
                latitude FLOAT,
                longitude FLOAT,
                city_id INTEGER,
                rating FLOAT
            )
        """,
        "menu_items": """
            CREATE TABLE IF NOT EXISTS menu_items (
                item_id INTEGER PRIMARY KEY,
                restaurant_id INTEGER,
                item_name VARCHAR(100),
                item_category VARCHAR(50),
                item_price FLOAT,
                available_quantity INTEGER
            )
        """,
        "delivery_personnel": """
            CREATE TABLE IF NOT EXISTS delivery_personnel (
                delivery_person_id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                age INTEGER,
                ratings FLOAT,
                vehicle_type VARCHAR(50),
                vehicle_condition INTEGER,
                city_id INTEGER
            )
        """,
        "posts": """
            CREATE TABLE IF NOT EXISTS posts (
                post_id INTEGER PRIMARY KEY,
                restaurant_id INTEGER,
                image_url VARCHAR(200),
                description TEXT,
                posted_at TIMESTAMP
            )
        """,
        "orders": """
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                restaurant_id INTEGER,
                post_id INTEGER,
                delivery_person_id INTEGER,
                order_timestamp TIMESTAMP,
                pickup_time TIMESTAMP,
                delivery_latitude FLOAT,
                delivery_longitude FLOAT,
                status VARCHAR(20),
                total_price FLOAT,
                time_taken_minutes INTEGER,
                city_id INTEGER
            )
        """,
        "weather_conditions": """
            CREATE TABLE IF NOT EXISTS weather_conditions (
                weather_id INTEGER PRIMARY KEY,
                city_id INTEGER,
                timestamp TIMESTAMP,
                weather VARCHAR(50)
            )
        """,
        "festivals_holidays": """
            CREATE TABLE IF NOT EXISTS festivals_holidays (
                festival_id INTEGER PRIMARY KEY,
                city_id INTEGER,
                festival_name VARCHAR(100),
                date DATE,
                type VARCHAR(50)
            )
        """
    }

    with engine.connect() as conn:
        for table_name, create_stmt in table_definitions.items():
            conn.execute(text(create_stmt))
            # Commit after each table creation
            conn.execute(text("COMMIT"))
        print("Created all necessary tables.")

    # Mapping of table names to corresponding CSV filenames
    files = {
        "cities": "cities.csv",
        "users": "users.csv",
        "restaurants": "restaurants.csv",
        "menu_items": "menu_items.csv",
        "delivery_personnel": "delivery_personnel.csv",
        "posts": "posts.csv",
        "orders": "orders.csv",
        "weather_conditions": "weather_conditions.csv",
        "festivals_holidays": "festivals_holidays.csv"
    }

    # Base path for CSV files (ensure your volume mapping makes this available)
    base_path = "/opt/airflow/data/synthetic"
    os.makedirs(base_path, exist_ok=True)

    print(f"Current working directory: {os.getcwd()}")
    if os.path.exists("/opt/airflow/data"):
        print(f"Contents of /opt/airflow/data: {os.listdir('/opt/airflow/data')}")
    else:
        print("Directory /opt/airflow/data not found.")

    loaded_files = 0
    for table, filename in files.items():
        file_path = os.path.join(base_path, filename)
        try:
            if not os.path.exists(file_path):
                print(f"Warning: File {file_path} does not exist. Skipping.")
                continue
            df = pd.read_csv(file_path)
            df.to_sql(table, engine, if_exists="append", index=False)
            print(f"Successfully loaded {filename} into {table} table.")
            loaded_files += 1
        except Exception as e:
            print(f"Failed to load {filename}: {str(e)}")

    print(f"Loaded {loaded_files} out of {len(files)} files.")
    if loaded_files == 0:
        print("WARNING: No data files were found or loaded. Expected location:", base_path)


with DAG(
        'load_synthetic_data_dag',
        default_args=default_args,
        description='Load synthetic data into PostgreSQL',
        schedule_interval=None,
        catchup=False,
        tags=['data_loading'],
) as dag:
    create_database = PythonOperator(
        task_id='create_food_delivery_database',
        python_callable=create_food_delivery_database,
    )

    load_data = PythonOperator(
        task_id='load_csv_to_postgres',
        python_callable=load_csv_to_postgres,
    )

    create_database >> load_data
