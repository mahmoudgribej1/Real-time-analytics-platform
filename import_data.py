import pandas as pd
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://airflow:airflow@localhost:5435/airflow')

def safe_import(table, csv_path):
    df = pd.read_csv(csv_path)

    with engine.begin() as conn:
        # Truncate table first
        conn.execute(text(f'TRUNCATE TABLE {table} CASCADE'))
        # Import data
        df.to_sql(
            name=table,
            con=conn,
            if_exists='append',
            index=False
        )
    print(f"Imported {len(df)} rows to {table}")

tables = [
    ('cities', 'data/synthetic/cities.csv'),
    ('users', 'data/synthetic/users.csv'),
    ('restaurants', 'data/synthetic/restaurants.csv'),
    ('menu_items', 'data/synthetic/menu_items.csv'),
    ('delivery_personnel', 'data/synthetic/delivery_personnel.csv'),
    ('posts', 'data/synthetic/posts.csv'),
    ('weather_conditions', 'data/synthetic/weather_conditions.csv'),
    ('festivals_holidays', 'data/synthetic/festivals_holidays.csv'),
    ('orders', 'data/synthetic/orders.csv')
]

for table, csv_path in tables:
    safe_import(table, csv_path)