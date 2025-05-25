# import requests
#
# KAFKA_CONNECT_URL = "http://localhost:8085/connectors"
#
# tables_increment_columns = {
#     'cities': 'city_id',
#     'users': 'user_id',
#     'restaurants': 'restaurant_id',
#     'menu_items': 'item_id',
#     'orders': 'order_id',
#     'delivery_personnel': 'delivery_person_id',
#     'posts': 'post_id',
#     'weather_conditions': 'weather_id',
#     'festivals_holidays': 'festival_id'
# }
#
# def create_connector(table):
#     connector_config = {
#         "name": f"debezium-postgres-{table}-connector",
#         "config": {
#             "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
#             "database.hostname": "postgres",
#             "database.port": "5432",
#             "database.user": "airflow",
#             "database.password": "airflow",
#             "database.dbname": "airflow",
#             "database.server.name": "postgres",
#             "table.include.list": f"public.{table}",  # Format: schema.table
#             "topic.prefix": f"postgres-{table}-",
#             "slot.name": f"debezium_{table}",  # Replication slot
#             "publication.name": f"debezium_pub_{table}",
#             "plugin.name": "pgoutput",  # Default logical decoding plugin
#             "snapshot.mode": "initial"  # Take initial snapshot
#         }
#     }
#
#     response = requests.post(
#         KAFKA_CONNECT_URL,
#         json=connector_config
#     )
#     if response.status_code == 201:
#         print(f"[SUCCESS] {table} connector created successfully.")
#     else:
#         print(f"[ERROR] Failed to create connector for {table}: {response.text}")
#
# if __name__ == "__main__":
#     for table, inc_col in tables_increment_columns.items():
#         create_connector(table)

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

def delete_existing_connector(name):
    try:
        resp = requests.delete(f"{KAFKA_CONNECT_URL}/{name}?deleteOffsets=true")
        if resp.status_code == 204:
            print(f"[INFO] Deleted existing connector: {name}")
    except Exception as e:
        print(f"[WARN] Could not delete {name}: {e}")

def create_connector(table):
    connector_name = f"debezium-postgres-{table}-connector"
    delete_existing_connector(connector_name)

    connector_config = {
        "name": connector_name,
        "config": {
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "database.hostname": "postgres",
            "database.port": "5432",
            "database.user": "airflow",
            "database.password": "airflow",
            "database.dbname": "airflow",
            "database.server.name": "postgres",
            "table.include.list": f"public.{table}",
            "topic.prefix": f"postgres-{table}-",
            "slot.name": f"debezium_{table}",
            "publication.name": f"debezium_pub_{table}",
            "plugin.name": "pgoutput",
            "snapshot.mode": "always",          # 🔄 force snapshot
            "slot.drop.on.stop": "true",       # 🧼 clean slot on shutdown
            "include.before": "true",          # ✅ ensure update `before` state
            "include.schema.changes": "false", # 🛑 skip schema changes if not needed
            "tombstones.on.delete": "false",
            "decimal.handling.mode": "string",
            "time.precision.mode": "adaptive_time_microseconds"
        }
    }

    response = requests.post(KAFKA_CONNECT_URL, json=connector_config)
    if response.status_code == 201:
        print(f"[✅] {table} connector created successfully.")
    else:
        print(f"[❌] Failed to create connector for {table}: {response.text}")

if __name__ == "__main__":
    for table in tables_increment_columns.keys():
        create_connector(table)

