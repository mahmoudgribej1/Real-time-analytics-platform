import requests

KAFKA_CONNECT_URL = "http://localhost:8085/connectors"

tables_increment_columns = {
    'cities': 'city_id',
    'users': 'user_id',
    'restaurants': 'restaurant_id',
    'menu_items': 'item_id',
    'orders': 'order_id',
    'delivery_personnel': 'delivery_person_id',
    'posts': 'post_id',
    'weather_conditions': 'weather_id',
    'festivals_holidays': 'festival_id'
}

def create_connector(table):
    connector_config = {
        "name": f"debezium-postgres-{table}-connector",
        "config": {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "database.hostname": "postgres",
            "database.port": "5432",
            "database.user": "airflow",
            "database.password": "airflow",
            "database.dbname": "airflow",
            "database.server.name": "postgres",
            "table.include.list": f"public.{table}",  # Format: schema.table
            "topic.prefix": f"postgres-{table}-",
            "slot.name": f"debezium_{table}",  # Replication slot
            "publication.name": f"debezium_pub_{table}",
            "plugin.name": "pgoutput",  # Default logical decoding plugin
            "snapshot.mode": "initial"  # Take initial snapshot
        }
    }

    response = requests.post(
        KAFKA_CONNECT_URL,
        json=connector_config
    )
    if response.status_code == 201:
        print(f"[SUCCESS] {table} connector created successfully.")
    else:
        print(f"[ERROR] Failed to create connector for {table}: {response.text}")

if __name__ == "__main__":
    for table, inc_col in tables_increment_columns.items():
        create_connector(table)
