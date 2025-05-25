import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import random
from datetime import datetime

# ============================
# CONFIGURATION
# ============================
DB_PARAMS = {
    'host': 'localhost',
    'port': 5435,
    'database': 'airflow',
    'user': 'airflow',
    'password': 'airflow'
}
BASE_PATH = 'E:/flavor-trend-streamsPFE/data/raw/'

# Robust CSV loader with encoding fallback
def read_csv(path, **kwargs):
    try:
        return pd.read_csv(path, **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding='latin1', **kwargs)

# ============================
# 1. LOAD CSVs
# ============================
stores_df     = read_csv(BASE_PATH + 'stores.csv')
hubs_df       = read_csv(BASE_PATH + 'hubs.csv')
drivers_df    = read_csv(BASE_PATH + 'drivers.csv')
orders_df     = read_csv(BASE_PATH + 'orders.csv')
deliveries_df = read_csv(BASE_PATH + 'deliveries.csv')

# ============================
# 2. PARSE DATES
# ============================
orders_df['order_moment_created'] = pd.to_datetime(
    orders_df['order_moment_created'], format='%Y-%m-%d %H:%M:%S', errors='coerce'
)
orders_df['order_moment_collected'] = pd.to_datetime(
    orders_df['order_moment_collected'], format='%Y-%m-%d %H:%M:%S', errors='coerce'
)

# ============================
# 3. CONNECT & FETCH lookups
# ============================
conn = psycopg2.connect(**DB_PARAMS)
cur  = conn.cursor()

# Governorates
cur.execute("SELECT city_id FROM cities;")
GOV_IDS = [row[0] for row in cur.fetchall()]

# ============================
# 4. UPSERT restaurants
# ============================
stores_merged = stores_df.merge(hubs_df[['hub_id','hub_city']],
                                on='hub_id', how='left')
first_order = orders_df.groupby('store_id')['order_moment_created'].min().to_dict()
rest_records = []
for r in stores_merged.itertuples(index=False):
    opening = first_order.get(r.store_id)
    if pd.isna(opening):
        opening = datetime.now()
    lat = float(r.store_latitude) if pd.notna(r.store_latitude) else 0.0
    lon = float(r.store_longitude) if pd.notna(r.store_longitude) else 0.0
    rest_records.append((
        int(r.store_id), r.store_name, r.store_segment,
        lat, lon, random.choice(GOV_IDS),
        0.0, opening
    ))
execute_values(cur, """
INSERT INTO restaurants
  (restaurant_id,name,description,latitude,longitude,city_id,rating,opening_date)
VALUES %s
ON CONFLICT (restaurant_id) DO UPDATE SET
  name=EXCLUDED.name,
  description=EXCLUDED.description,
  latitude=EXCLUDED.latitude,
  longitude=EXCLUDED.longitude,
  city_id=EXCLUDED.city_id,
  rating=EXCLUDED.rating,
  opening_date=EXCLUDED.opening_date;
""", rest_records)
conn.commit()

# ============================
# 5. UPSERT delivery_personnel
# ============================
drv_records = [
    (int(d.driver_id), d.driver_modal, 0, 0.0,
     d.driver_modal, 5, 1.0, random.choice(GOV_IDS))
    for d in drivers_df.itertuples(index=False)
]
execute_values(cur, """
INSERT INTO delivery_personnel
  (delivery_person_id,name,age,ratings,vehicle_type,vehicle_condition,speed_multiplier,city_id)
VALUES %s
ON CONFLICT (delivery_person_id) DO UPDATE SET
  name=EXCLUDED.name, age=EXCLUDED.age, ratings=EXCLUDED.ratings,
  vehicle_type=EXCLUDED.vehicle_type, vehicle_condition=EXCLUDED.vehicle_condition,
  speed_multiplier=EXCLUDED.speed_multiplier, city_id=EXCLUDED.city_id;
""", drv_records)
conn.commit()

# Fetch all driver IDs for fallback
cur.execute("SELECT delivery_person_id FROM delivery_personnel;")
DRIVER_IDS = [row[0] for row in cur.fetchall()]

# ============================
# 6. SYNTHETIC users
# ============================
orders_info = orders_df.set_index('order_id')['order_moment_created'].to_dict()
usr_records = []
for oid, tm in orders_info.items():
    reg = tm if not pd.isna(tm) else datetime.now()
    usr_records.append((
        f"user_{oid}", f"user_{oid}@example.tn", 'changeme', '',
        random.choice(GOV_IDS), reg, 0.0, 0.0
    ))
execute_values(cur, """
INSERT INTO users (username,email,password,address,city_id,registration_date,latitude,longitude)
VALUES %s ON CONFLICT (username) DO NOTHING;
""", usr_records)
conn.commit()

cur.execute("SELECT username,user_id FROM users;")
user_map = dict(cur.fetchall())

# ============================
# 7. INSERT orders fact (fill missing delivery_person_id)
# ============================
deliveries_df['driver_id'] = deliveries_df['driver_id'].astype('Int64')
orders_full = orders_df.merge(
    deliveries_df, left_on='order_id', right_on='delivery_order_id', how='left'
)

order_records = []
for r in orders_full.itertuples(index=False):
    order_ts = r.order_moment_created if not pd.isna(r.order_moment_created) else datetime.now()
    pickup_ts = r.order_moment_collected if not pd.isna(r.order_moment_collected) else order_ts
    duration = int(r.order_metric_cycle_time) if pd.notna(r.order_metric_cycle_time) else 0
    dp_id = int(r.driver_id) if pd.notna(r.driver_id) else random.choice(DRIVER_IDS)
    order_records.append((
        user_map.get(f"user_{int(r.order_id)}"),
        int(r.store_id),
        None,
        dp_id,
        order_ts,
        pickup_ts,
        0.0,
        0.0,
        'Completed' if r.order_status=='DELIVERED' else 'Cancelled',
        float(r.order_amount or 0.0),
        duration,
        random.choice(GOV_IDS)
    ))

print(f"Inserting {len(order_records)} orders...")
execute_values(cur, """
INSERT INTO orders
  (user_id,restaurant_id,post_id,delivery_person_id,
   order_timestamp,pickup_time,delivery_latitude,delivery_longitude,
   status,total_price,time_taken_minutes,city_id)
VALUES %s ON CONFLICT DO NOTHING;
""", order_records)
conn.commit()

cur.close()
conn.close()
print("✅ Full ETL complete: restaurants, delivery_personnel, users, orders loaded.")
