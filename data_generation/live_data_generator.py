# import psycopg2
# import random
# import time
# import threading
# from datetime import datetime, timedelta
# from faker import Faker
#
# # Setup Faker for realistic fake data
# fake = Faker()
#
# # PostgreSQL connection settings (matches your Docker mapping: 5435:5432)
# DB_HOST = "localhost"
# DB_PORT = 5435  # External port mapped to internal 5432
# DB_NAME = "airflow"
# DB_USER = "airflow"
# DB_PASSWORD = "airflow"
#
# def get_connection():
#     return psycopg2.connect(
#         host=DB_HOST,
#         port=DB_PORT,
#         database=DB_NAME,
#         user=DB_USER,
#         password=DB_PASSWORD
#     )
#
# # Global sets and locks for uniqueness
# unique_usernames = set()
# unique_post_descriptions = set()
# username_lock = threading.Lock()
# post_desc_lock = threading.Lock()
#
# def load_existing_usernames():
#     """
#     Loads existing usernames from the 'users' table in the database into the global set.
#     """
#     try:
#         conn = get_connection()
#         cursor = conn.cursor()
#         cursor.execute("SELECT username FROM users")
#         rows = cursor.fetchall()
#         with username_lock:
#             for row in rows:
#                 unique_usernames.add(row[0])
#         cursor.close()
#         conn.close()
#         print(f"Loaded {len(unique_usernames)} existing usernames.")
#     except Exception as e:
#         print("Error loading existing usernames:", e)
#
# def generate_post_description(sentiment):
#     """
#     Generates a meaningful post description using templates.
#     """
#     if sentiment == 'positive':
#         templates = [
#             "Absolutely {} and {}! Highly recommended.",
#             "The {} taste and {} presentation exceeded expectations.",
#             "A truly {} experience with {} flavors.",
#             "Delicious, {} dish with {} service."
#         ]
#         adjectives1 = ["delightful", "amazing", "exceptional", "incredible", "fantastic", "remarkable"]
#         adjectives2 = ["vibrant", "fresh", "satisfying", "memorable", "outstanding", "exquisite"]
#     else:
#         templates = [
#             "Unfortunately, the dish was {} and {}.",
#             "A {} experience with {} flavors.",
#             "The {} presentation and {} taste left much to desire.",
#             "Disappointing, {} dish with {} quality."
#         ]
#         adjectives1 = ["mediocre", "bland", "disappointing", "lackluster", "subpar", "unimpressive"]
#         adjectives2 = ["poor", "unsatisfactory", "dull", "underwhelming", "off", "bad"]
#
#     template = random.choice(templates)
#     return template.format(random.choice(adjectives1), random.choice(adjectives2))
#
# # -------------------------
# # Orders Insertion Function
# # -------------------------
# def insert_order():
#     conn = get_connection()
#     cursor = conn.cursor()
#     while True:
#         now = datetime.now()
#         user_id = random.randint(1, 5000)
#         restaurant_id = random.randint(1, 200)
#         # 30% chance to have a related post; otherwise, set to NULL
#         post_id = random.randint(1, 5000) if random.random() < 0.3 else None
#         delivery_person_id = random.randint(1, 100)
#         city_id = random.randint(1, 24)
#
#         order_timestamp = now
#         pickup_time = now + timedelta(minutes=random.randint(10, 20))
#         delivery_latitude = round(random.uniform(30.0, 40.0), 6)
#         delivery_longitude = round(random.uniform(8.0, 12.0), 6)
#         status = random.choices(["Completed", "Cancelled"], weights=[0.9, 0.1])[0]
#         total_price = round(random.uniform(10, 50), 2)
#         time_taken_minutes = random.randint(15, 45)
#
#         try:
#             cursor.execute("""
#                 INSERT INTO orders
#                 (user_id, restaurant_id, post_id, delivery_person_id, order_timestamp, pickup_time,
#                  delivery_latitude, delivery_longitude, status, total_price, time_taken_minutes, city_id)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#             """, (user_id, restaurant_id, post_id, delivery_person_id, order_timestamp,
#                   pickup_time, delivery_latitude, delivery_longitude, status, total_price, time_taken_minutes, city_id))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted order.")
#         except Exception as e:
#             print("Error inserting order:", e)
#             conn.rollback()
#         time.sleep(2)  # Insert a new order every 2 seconds
#
# # -------------------------
# # Posts Insertion Function
# # -------------------------
# def insert_post():
#     conn = get_connection()
#     cursor = conn.cursor()
#     while True:
#         now = datetime.now()
#         restaurant_id = random.randint(1, 200)
#         # Choose sentiment for generating description
#         sentiment = random.choices(['positive', 'negative'], weights=[0.8, 0.2])[0]
#         # Generate a unique post description
#         description = None
#         attempt = 0
#         while attempt < 100:
#             candidate = generate_post_description(sentiment)
#             with post_desc_lock:
#                 if candidate not in unique_post_descriptions:
#                     unique_post_descriptions.add(candidate)
#                     description = candidate
#                     break
#             attempt += 1
#         if description is None:
#             description = candidate  # Fallback if a unique description isn't found
#
#         image_url = f"https://via.placeholder.com/150?text=Food+{random.randint(1, 10000)}"
#         posted_at = now
#         try:
#             cursor.execute("""
#                 INSERT INTO posts
#                 (restaurant_id, image_url, description, posted_at)
#                 VALUES (%s, %s, %s, %s)
#             """, (restaurant_id, image_url, description, posted_at))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted post.")
#         except Exception as e:
#             print("Error inserting post:", e)
#             conn.rollback()
#         time.sleep(10)  # Insert a new post every 10 seconds
#
# # ------------------------------
# # New User Registration Function
# # ------------------------------
# def insert_user():
#     conn = get_connection()
#     cursor = conn.cursor()
#     while True:
#         now = datetime.now()
#         # Generate a unique username using a loop guarded by a lock
#         username = None
#         while True:
#             candidate = f"{fake.user_name()}{int(time.time()*1000)%10000}"
#             with username_lock:
#                 if candidate not in unique_usernames:
#                     unique_usernames.add(candidate)
#                     username = candidate
#                     break
#
#         email = f"{username.lower()}@example.tn"
#         password = fake.password(length=10)
#         address = fake.address().replace("\n", ", ")
#         city_id = random.randint(1, 24)
#         registration_date = now
#         latitude = round(random.uniform(30.0, 40.0), 6)
#         longitude = round(random.uniform(8.0, 12.0), 6)
#         try:
#             cursor.execute("""
#                 INSERT INTO users
#                 (username, email, password, address, city_id, registration_date, latitude, longitude)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
#             """, (username, email, password, address, city_id, registration_date, latitude, longitude))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted user: {username}")
#         except Exception as e:
#             print("Error inserting user:", e)
#             conn.rollback()
#         time.sleep(15)  # Insert a new user every 15 seconds
#
# # ------------------------------
# # Weather Conditions Insertion Function
# # ------------------------------
# def insert_weather():
#     conn = get_connection()
#     cursor = conn.cursor()
#     weather_options = ["Sunny", "Cloudy", "Rainy", "Hot", "Windy"]
#     while True:
#         now = datetime.now()
#         city_id = random.randint(1, 24)
#         timestamp = now  # Current time as timestamp
#         weather = random.choice(weather_options)
#         try:
#             cursor.execute("""
#                 INSERT INTO weather_conditions
#                 (city_id, timestamp, weather)
#                 VALUES (%s, %s, %s)
#             """, (city_id, timestamp, weather))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted weather: {weather} for city_id {city_id}")
#         except Exception as e:
#             print("Error inserting weather:", e)
#             conn.rollback()
#         time.sleep(20)  # Insert a new weather update every 20 seconds
#
# # ------------------------------
# # Main Function: Start Live Data Generation
# # ------------------------------
# if __name__ == "__main__":
#     # Load existing usernames from the database to avoid duplicates
#     load_existing_usernames()
#
#     threads = []
#     functions = [insert_order, insert_post, insert_user, insert_weather]
#
#     for func in functions:
#         thread = threading.Thread(target=func, daemon=True)
#         threads.append(thread)
#         thread.start()
#
#     print("Live data generation started. Press Ctrl+C to stop.")
#
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("Live data generation stopped.")
#
# import psycopg2
# import random
# import time
# import threading
# from datetime import datetime, timedelta
# from faker import Faker
# import numpy as np
#
# # Setup Faker
# fake = Faker()
#
# # PostgreSQL connection settings
# DB_HOST = "localhost"
# DB_PORT = 5435
# DB_NAME = "airflow"
# DB_USER = "airflow"
# DB_PASSWORD = "airflow"
#
# def get_connection():
#     return psycopg2.connect(
#         host=DB_HOST, port=DB_PORT,
#         database=DB_NAME, user=DB_USER, password=DB_PASSWORD
#     )
#
# def load_id_list(table, column):
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute(f"SELECT {column} FROM {table}")
#     ids = [row[0] for row in cur.fetchall()]
#     cur.close(); conn.close()
#     return ids
#
# # Load FK lists
# RESTAURANT_IDS = load_id_list("restaurants", "restaurant_id")
# USER_IDS       = load_id_list("users", "user_id")
# CITY_IDS       = load_id_list("cities", "city_id")
# COURIER_IDS    = load_id_list("delivery_personnel", "delivery_person_id")
# POST_IDS       = load_id_list("posts", "post_id")
#
# # Uniqueness
# unique_usernames = set()
# unique_post_descriptions = set()
# username_lock = threading.Lock()
# post_desc_lock = threading.Lock()
#
# def load_existing_usernames():
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("SELECT username FROM users")
#     for row in cur.fetchall(): unique_usernames.add(row[0])
#     cur.close(); conn.close()
#
# # Diurnal + holiday
# lunch_curve = {h: 0.1 for h in range(24)}
# for h in range(12,15): lunch_curve[h] = 1.2
# for h in range(18,23): lunch_curve[h] = 1.4
#
# def load_holidays():
#     conn = get_connection(); cur = conn.cursor()
#     cur.execute("SELECT date FROM festivals_holidays")
#     days = {row[0] for row in cur.fetchall()}
#     cur.close(); conn.close()
#     return days
#
# HOLIDAYS = load_holidays()
#
# def generate_post_description(sentiment):
#     if sentiment == 'positive':
#         templates = ["Absolutely {} and {}! Highly recommended.",
#                      "The {} taste and {} presentation exceeded expectations.",
#                      "A truly {} experience with {} flavors.",
#                      "Delicious, {} dish with {} service."]
#         adj1 = ["delightful", "amazing", "exceptional", "incredible"]
#         adj2 = ["vibrant", "fresh", "satisfying", "memorable"]
#     else:
#         templates = ["Unfortunately, the dish was {} and {}.",
#                      "A {} experience with {} flavors.",
#                      "The {} presentation and {} taste left much to desire.",
#                      "Disappointing, {} dish with {} quality."]
#         adj1 = ["mediocre", "bland", "disappointing", "lackluster"]
#         adj2 = ["poor", "unsatisfactory", "dull", "underwhelming"]
#     return random.choice(templates).format(random.choice(adj1), random.choice(adj2))
#
# def insert_order():
#     conn = get_connection(); cur = conn.cursor()
#     while True:
#         now = datetime.now()
#         rate = lunch_curve[now.hour] * (1.5 if now.date() in HOLIDAYS else 1)
#         if random.random() > rate:
#             time.sleep(2); continue
#
#         user_id = random.choice(USER_IDS)
#         restaurant_id = random.choice(RESTAURANT_IDS)
#         post_id = random.choice(POST_IDS) if random.random()<0.3 else None
#
#         # zipf index → actual courier_id
#         idx = np.random.zipf(1.4) - 1
#         courier_id = COURIER_IDS[idx % len(COURIER_IDS)]
#
#         city_id = random.choice(CITY_IDS)
#         order_timestamp = now
#         pickup_time = now + timedelta(minutes=random.randint(10,20))
#         delivery_lat = round(random.uniform(30.0,40.0),6)
#         delivery_lon = round(random.uniform(8.0,12.0),6)
#         time_taken_minutes = random.randint(15,45)
#         total_price = round(random.uniform(10,50),2)
#
#         weather = random.choice(["Sunny","Cloudy","Rainy","Hot","Windy","Fog","Stormy"])
#         status = random.choices(["Completed","Cancelled"], weights=[0.9,0.1])[0]
#         if weather in ("Rainy","Windy","Fog","Stormy","Sandstorms"):
#             time_taken_minutes += random.randint(10,15)
#             if random.random() < 0.2:
#                 status = "Cancelled"
#
#         try:
#             cur.execute("""
#                 INSERT INTO orders
#                 (user_id,restaurant_id,post_id,delivery_person_id,
#                  order_timestamp,pickup_time,delivery_latitude,
#                  delivery_longitude,status,total_price,
#                  time_taken_minutes,city_id)
#                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#             """, (
#                 user_id, restaurant_id, post_id, courier_id,
#                 order_timestamp, pickup_time,
#                 delivery_lat, delivery_lon,
#                 status, total_price,
#                 time_taken_minutes, city_id
#             ))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted order.")
#         except Exception as e:
#             print("Error inserting order:", e)
#             conn.rollback()
#
#         time.sleep(2)
#
# def insert_post():
#     conn = get_connection(); cur = conn.cursor()
#     while True:
#         now = datetime.now()
#         rid = random.choice(RESTAURANT_IDS)
#         sentiment = random.choices(['positive','negative'], weights=[0.8,0.2])[0]
#         description = None
#         for _ in range(100):
#             cand = generate_post_description(sentiment)
#             with post_desc_lock:
#                 if cand not in unique_post_descriptions:
#                     unique_post_descriptions.add(cand)
#                     description = cand; break
#         description = description or cand
#         try:
#             cur.execute("""
#                 INSERT INTO posts
#                 (restaurant_id,image_url,description,posted_at)
#                 VALUES (%s,%s,%s,%s)
#             """, (
#                 rid,
#                 f"https://via.placeholder.com/150?text=Food+{random.randint(1,10000)}",
#                 description, now
#             ))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted post.")
#         except Exception as e:
#             print("Error inserting post:", e)
#             conn.rollback()
#
#         time.sleep(10)
#
# def insert_user():
#     conn = get_connection(); cur = conn.cursor()
#     while True:
#         now = datetime.now()
#         with username_lock:
#             username = None
#             while True:
#                 cand = f"{fake.user_name()}{int(time.time()*1000)%10000}"
#                 if cand not in unique_usernames:
#                     unique_usernames.add(cand)
#                     username = cand; break
#         try:
#             cur.execute("""
#                 INSERT INTO users
#                 (username,email,password,address,city_id,registration_date,latitude,longitude)
#                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
#             """, (
#                 username, f"{username.lower()}@example.tn",
#                 fake.password(10), fake.address().replace("\n",", "),
#                 random.choice(CITY_IDS), now,
#                 round(random.uniform(30.0,40.0),6),
#                 round(random.uniform(8.0,12.0),6)
#             ))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted user: {username}")
#         except Exception as e:
#             print("Error inserting user:", e)
#             conn.rollback()
#         time.sleep(15)
#
# def insert_weather():
#     conn = get_connection(); cur = conn.cursor()
#     opts = ["Sunny","Cloudy","Rainy","Hot","Windy","Fog","Stormy"]
#     while True:
#         now = datetime.now()
#         try:
#             cur.execute("""
#                 INSERT INTO weather_conditions
#                 (city_id,timestamp,weather)
#                 VALUES (%s,%s,%s)
#             """, (
#                 random.choice(CITY_IDS), now, random.choice(opts)
#             ))
#             conn.commit()
#             print(f"[{datetime.now().isoformat()}] Inserted weather.")
#         except Exception as e:
#             print("Error inserting weather:", e)
#             conn.rollback()
#         time.sleep(20)
#
# if __name__ == "__main__":
#     load_existing_usernames()
#     threads = []
#     for fn in (insert_order, insert_post, insert_user, insert_weather):
#         t = threading.Thread(target=fn, daemon=True)
#         threads.append(t); t.start()
#     print("Live data generation started. Press Ctrl+C to stop.")
#     try:
#         while True: time.sleep(1)
#     except KeyboardInterrupt:
#         print("Live data generation stopped.")


import psycopg2
import random
import time
import threading
import os
from datetime import datetime, timedelta
from faker import Faker
import numpy as np

# ---------------------------
# CONFIGURATION
# ---------------------------
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 5435))
DB_NAME = os.getenv('DB_NAME', 'airflow')
DB_USER = os.getenv('DB_USER', 'airflow')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'airflow')

POSITIVE_RATE = float(os.getenv('POSITIVE_RATE', '0.6'))
WEEKEND_RATE = float(os.getenv('WEEKEND_RATE', '1.1'))

# Faker setup
dummy_fake = Faker()

# ---------------------------
# DB CONNECTION
# ---------------------------
def get_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

# Load dimension lists
def load_list(query):
    conn = get_connection(); cur = conn.cursor()
    cur.execute(query)
    vals = [r[0] for r in cur.fetchall()]
    cur.close(); conn.close()
    return vals

RESTAURANT_IDS    = load_list("SELECT restaurant_id FROM restaurants;")
POST_IDS          = load_list("SELECT post_id FROM posts;")
USER_IDS          = load_list("SELECT user_id FROM users;")

# ---------------------------
# NEW: Load couriers *by* city for consistent assignment
# ---------------------------
def load_couriers_by_city():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT delivery_person_id, city_id FROM delivery_personnel;")
    cb = {}
    for courier_id, city_id in cur.fetchall():
        cb.setdefault(city_id, []).append(courier_id)
    cur.close(); conn.close()
    return cb

COURIERS_BY_CITY = load_couriers_by_city()

# Load restaurant metadata (lat, lon, city)
conn = get_connection(); cur = conn.cursor()
cur.execute("SELECT restaurant_id, latitude, longitude, city_id FROM restaurants;")
RESTAURANT_META = {r[0]: {'lat': r[1], 'lon': r[2], 'city': r[3]} for r in cur.fetchall()}
cur.close(); conn.close()

# ---------------------------
# Realism configurations
# ---------------------------
# Diurnal shape
lunch_curve = {h: 0.1 for h in range(24)}
for h in range(12, 15): lunch_curve[h] = 1.2
for h in range(18, 23): lunch_curve[h] = 1.4
# Holidays
def load_holidays():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT date FROM festivals_holidays;")
    days = {r[0] for r in cur.fetchall()}
    cur.close(); conn.close()
    return days
HOLIDAYS = load_holidays()

# Post templates
POS_TEMPLATES = [
    "Absolutely {} and {}! Highly recommended.",
    "The {} taste and {} presentation exceeded expectations.",
    "A truly {} experience with {} flavors.",
    "Delicious, {} dish with {} service.",
    "This was a {} adventure with {} vibes!",
    "Marvelously {} and wonderfully {}!"
]
NEG_TEMPLATES = [
    "Unfortunately, the dish was {} and {}.",
    "A {} experience with {} flavors.",
    "The {} presentation and {} taste left much to desire.",
    "Disappointing, {} dish with {} quality.",
    "Sadly, it felt {} and {}.",
    "Regrettably {} and painfully {}."
]

# Weather effects
WEATHER_OPTIONS = ["Sunny","Cloudy","Rainy","Hot","Windy","Fog","Stormy","Sandstorms"]
WEATHER_EFFECTS = {
    "Rainy": {"delay": (10,15), "cancel": 0.20},
    "Windy": {"delay": (8,12),  "cancel": 0.15},
    "Fog":   {"delay": (5,10),  "cancel": 0.10},
    "Stormy": {"delay": (15,20),"cancel":0.25},
    "Sandstorms": {"delay": (12,18),"cancel":0.18}
}

# Uniqueness guards
unique_usernames = set()
unique_posts = set()
username_lock = threading.Lock()
post_lock = threading.Lock()

# Load existing usernames
def load_usernames():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT username FROM users;")
    for (u,) in cur.fetchall(): unique_usernames.add(u)
    cur.close(); conn.close()

# Post description generator
def gen_desc(sent):
    """
    Generate a post description based on sentiment with appropriate adjective pools.
    """
    if sent == 'positive':
        templates = POS_TEMPLATES
        adj1 = ["delightful", "amazing", "exceptional", "incredible", "fantastic", "remarkable"]
        adj2 = ["vibrant", "fresh", "satisfying", "memorable", "outstanding", "exquisite"]
    else:
        templates = NEG_TEMPLATES
        adj1 = ["mediocre", "bland", "disappointing", "lackluster", "subpar", "unimpressive"]
        adj2 = ["poor", "unsatisfactory", "dull", "underwhelming", "off", "bad"]

    t = random.choice(templates)
    return t.format(random.choice(adj1), random.choice(adj2))

# ---------------------------
# Insertion functions
# ---------------------------
def insert_order():
    conn = get_connection(); cur = conn.cursor()
    while True:
        now = datetime.now()
        rate = lunch_curve[now.hour] * (1.5 if now.date() in HOLIDAYS else 1) * (WEEKEND_RATE if now.weekday()>=5 else 1)
        if random.random() > rate:
            time.sleep(2); continue

        # pick FKs
        uid = random.choice(USER_IDS)
        rid = random.choice(RESTAURANT_IDS)
        pid = random.choice(POST_IDS) if random.random() < POSITIVE_RATE else None
        # ── CHANGE ── pick only couriers from this restaurant's city ─────────
        meta = RESTAURANT_META[rid]
        city_id = meta['city']
        city_couriers = COURIERS_BY_CITY.get(city_id)
        if not city_couriers:
            # no couriers in this city; skip
            time.sleep(2)
            continue
        cid = random.choice(city_couriers)
        # ────────────────────────────────────────────────────────────────────
        # timestamps
        order_ts = now
        pickup_ts = now + timedelta(minutes=random.randint(10,20))
        # geo jitter around restaurant
        lat = round(meta['lat'] + random.uniform(-0.005,0.005), 6)
        lon = round(meta['lon'] + random.uniform(-0.005,0.005), 6)
        # logic
        # ORIGINAL:
        # time_min = random.randint(15,45)

        # ← CHANGED: use a normal distribution for more realistic delivery times
        #   • mean = 30 min, sd = 15 min
        #   • clipped to [5,90] to avoid nonsensical extremes
        time_min = int(np.clip(np.random.normal(loc=30, scale=15), 5, 90))
        total = round(random.uniform(10,50),2)
        weather = random.choice(WEATHER_OPTIONS)
        status = random.choices(["Completed","Cancelled"], weights=[0.9,0.1])[0]
        if weather in WEATHER_EFFECTS:
            d_min,d_max = WEATHER_EFFECTS[weather]['delay']
            time_min += random.randint(d_min,d_max)
            if random.random() < WEATHER_EFFECTS[weather]['cancel']:
                status = 'Cancelled'

        try:
            cur.execute("""
INSERT INTO orders
(user_id, restaurant_id, post_id, delivery_person_id,
 order_timestamp, pickup_time, delivery_latitude,
 delivery_longitude, status, total_price,
 time_taken_minutes, city_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", (
                uid, rid, pid, cid,
                order_ts, pickup_ts, lat, lon,
                status, total, time_min, meta['city']
            ))
            conn.commit()
            print(f"[{order_ts.isoformat()}] Order uid={uid} rid={rid} cid={cid} status={status} t={time_min}m")
        except Exception as e:
            print("Error inserting order:", e); conn.rollback()

        time.sleep(2)


def insert_post():
    conn = get_connection(); cur = conn.cursor()
    while True:
        now = datetime.now()
        rid = random.choice(RESTAURANT_IDS)
        sent = 'positive' if random.random()<POSITIVE_RATE else 'negative'
        desc = None
        for _ in range(50):
            d = gen_desc(sent)
            with post_lock:
                if d not in unique_posts:
                    unique_posts.add(d); desc = d; break
        desc = desc or d
        try:
            cur.execute("""
INSERT INTO posts (restaurant_id, image_url, description, posted_at)
VALUES (%s,%s,%s,%s)
""", (
                rid,
                f"https://via.placeholder.com/150?text=Food+{random.randint(1,10000)}",
                desc, now
            ))
            conn.commit()
            print(f"[{now.isoformat()}] Post rid={rid} sent={sent}")
        except Exception as e:
            print("Error inserting post:", e); conn.rollback()
        time.sleep(10)


def insert_user():
    conn = get_connection(); cur = conn.cursor()
    while True:
        now = datetime.now()
        with username_lock:
            uname = None
            while True:
                u = f"{dummy_fake.user_name()}{int(time.time()*1000)%10000}"
                if u not in unique_usernames:
                    unique_usernames.add(u); uname = u; break
        try:
            cur.execute("""
INSERT INTO users (username,email,password,address,city_id,registration_date,latitude,longitude)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
""", (
                uname, f"{uname}@example.tn", dummy_fake.password(10),
                dummy_fake.address().replace("\n", ", "),
                random.choice(list(RESTAURANT_META.values()))['city'],
                now,
                round(random.uniform(30.0,40.0),6),
                round(random.uniform(8.0,12.0),6)
            ))
            conn.commit()
            print(f"[{now.isoformat()}] User uname={uname}")
        except Exception as e:
            print("Error inserting user:", e); conn.rollback()
        time.sleep(15)


def insert_weather():
    conn = get_connection(); cur = conn.cursor()
    while True:
        now = datetime.now()
        w = random.choice(WEATHER_OPTIONS)
        # pick a real restaurant city
        city = random.choice(list(RESTAURANT_META.values()))['city']
        try:
            cur.execute("""
INSERT INTO weather_conditions (city_id, timestamp, weather)
VALUES (%s,%s,%s)
""", (city, now, w))
            conn.commit()
            print(f"[{now.isoformat()}] Weather city={city} {w}")
        except Exception as e:
            print("Error inserting weather:", e); conn.rollback()
        time.sleep(20)

if __name__ == "__main__":
    load_usernames()
    threads = []
    for fn in (insert_order, insert_post, insert_user, insert_weather):
        t = threading.Thread(target=fn, daemon=True)
        threads.append(t); t.start()
    print("Live data generation started.")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("Live data generation stopped.")
