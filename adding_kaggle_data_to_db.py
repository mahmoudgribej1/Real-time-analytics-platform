import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import random
import os
from datetime import datetime, timedelta
from faker import Faker

# ---------------------------
# CONFIGURATION
# ---------------------------
DB_PARAMS = {
    'host': 'localhost', 'port': 5435,
    'database': 'airflow', 'user': 'airflow', 'password': 'airflow'
}
CSV_PATH = 'E:/flavor-trend-streamsPFE/data/raw/train.csv'

# Governorate groups for mapping Kaggle City labels
METROPOLITAN = ["Tunis", "Ariana", "Ben Arous", "Manouba"]
URBAN        = ["Sfax", "Sousse", "Monastir", "Nabeul", "Bizerte", "Mahdia"]
RURAL        = ["Beja", "Gabes", "Gafsa", "Jendouba", "Kairouan", "Kasserine",
                "Kebili", "Kef", "Medenine", "Sidi Bouzid", "Siliana",
                "Tataouine", "Tozeur", "Zaghouan"]

# Faker setup
fake = Faker()

# ---------------------------
# 1. READ & CLEAN CSV
# ---------------------------
df = pd.read_csv(CSV_PATH)
# strip whitespace on column names
df.columns = [c.strip() for c in df.columns]

# Clean weather and time fields
df['weather'] = df['Weatherconditions'] \
    .str.replace('conditions ', '', regex=False) \
    .str.strip()
df['time_taken'] = df['Time_taken(min)'] \
    .str.extract(r"(\d+)") \
    .astype(int)

# Parse timestamps
df['order_timestamp'] = pd.to_datetime(
    df['Order_Date'] + ' ' + df['Time_Orderd'],
    format='%d-%m-%Y %H:%M:%S', dayfirst=True, errors='coerce'
)
df['pickup_time'] = pd.to_datetime(
    df['Order_Date'] + ' ' + df['Time_Order_picked'],
    format='%d-%m-%Y %H:%M:%S', dayfirst=True, errors='coerce'
)
# Drop rows missing order_timestamp, fill missing pickup_time
df = df[df['order_timestamp'].notna()].copy()
df['pickup_time'] = df['pickup_time'].fillna(df['order_timestamp'])

# ---------------------------
# 2. CONNECT & LOAD LOOKUPS
# ---------------------------
conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor()

# city_name -> city_id
cur.execute("SELECT city_name, city_id FROM cities;")
city_map = dict(cur.fetchall())

# city_id -> (lat, lon)
cur.execute("SELECT city_id, latitude, longitude FROM cities;")
CITY_LOCS = {cid: (lat, lon) for cid, lat, lon in cur.fetchall()}

# restaurant and courier IDs
cur.execute("SELECT restaurant_id FROM restaurants;")
REST_IDS = [r[0] for r in cur.fetchall()]
cur.execute("SELECT delivery_person_id FROM delivery_personnel;")
COURIER_IDS = [r[0] for r in cur.fetchall()]

# ---------------------------
# 3. CITY_ID RESOLUTION
# ---------------------------
def resolve_city_id(label):
    lbl = str(label).strip()
    if lbl in city_map:
        return city_map[lbl]
    low = lbl.lower()
    if low == 'urban':
        return city_map[random.choice(URBAN)]
    if low == 'metropolitian':
        return city_map[random.choice(METROPOLITAN)]
    if low in ('semi-urban', 'semi urban'):
        return city_map[random.choice(RURAL)]
    return None

# ---------------------------
# 4. BUILD & UPSERT USERS
# ---------------------------
user_rows = []
order_to_user = {}
for idx, row in df.iterrows():
    # unique username and email
    first = fake.first_name(); last = fake.last_name()
    uid = f"{first}{last}{idx}"
    email = f"{uid.lower()}@example.tn"
    # registration date before order_timestamp
    delta = timedelta(days=random.randint(1, 365), seconds=random.randint(0, 86400))
    reg_date = row['order_timestamp'] - delta
    # map city and jitter location
    city_id = resolve_city_id(row['City'])
    if city_id is None:
        city_id = random.choice(list(city_map.values()))
    base_lat, base_lon = CITY_LOCS.get(city_id, (36.8, 10.1))
    lat = round(base_lat + random.uniform(-0.02, 0.02), 6)
    lon = round(base_lon + random.uniform(-0.02, 0.02), 6)
    user_rows.append((
        uid, email, fake.password(length=10),
        fake.address().replace('\n', ', '),
        city_id, reg_date, lat, lon
    ))
    order_to_user[idx] = uid

# Upsert users
execute_values(cur, """
INSERT INTO users
  (username, email, password, address, city_id, registration_date, latitude, longitude)
VALUES %s
ON CONFLICT (username) DO NOTHING;
""", user_rows)
conn.commit()

# Refresh user mapping
cur.execute("SELECT username, user_id FROM users;")
user_map = dict(cur.fetchall())

# ---------------------------
# 5. BUILD & INSERT WEATHER_CONDITIONS
# ---------------------------
weather_rows = []
for idx, row in df.iterrows():
    cid = resolve_city_id(row['City'])
    if cid is None:
        cid = random.choice(list(city_map.values()))
    weather_rows.append((cid, row['order_timestamp'], row['weather']))
execute_values(cur, """
INSERT INTO weather_conditions (city_id, timestamp, weather)
VALUES %s
ON CONFLICT DO NOTHING;
""", weather_rows)
conn.commit()

# ---------------------------
# 6. BUILD & INSERT ORDERS
# ---------------------------
order_rows = []
for idx, row in df.iterrows():
    user_id = user_map.get(order_to_user[idx])
    rest_id = random.choice(REST_IDS)
    courier_id = random.choice(COURIER_IDS)
    cid = resolve_city_id(row['City']) or random.choice(list(city_map.values()))
    order_rows.append((
        user_id, rest_id, None, courier_id,
        row['order_timestamp'], row['pickup_time'],
        row['Delivery_location_latitude'], row['Delivery_location_longitude'],
        'Completed', round(random.uniform(5, 100), 2),
        int(row['time_taken']), cid
    ))
execute_values(cur, """
INSERT INTO orders
  (user_id, restaurant_id, post_id, delivery_person_id,
   order_timestamp, pickup_time, delivery_latitude,
   delivery_longitude, status, total_price,
   time_taken_minutes, city_id)
VALUES %s
ON CONFLICT DO NOTHING;
""", order_rows)
conn.commit()

# ---------------------------
# CLEANUP
# ---------------------------
cur.close()
conn.close()
print("✅ ETL complete: users, weather_conditions, and orders loaded.")