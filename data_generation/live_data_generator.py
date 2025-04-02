import psycopg2
import random
import time
import threading
from datetime import datetime, timedelta
from faker import Faker

# Setup Faker for realistic fake data
fake = Faker()

# PostgreSQL connection settings (matches your Docker mapping: 5435:5432)
DB_HOST = "localhost"
DB_PORT = 5435  # External port mapped to internal 5432
DB_NAME = "airflow"
DB_USER = "airflow"
DB_PASSWORD = "airflow"

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

# -------------------------
# Orders Insertion Function
# -------------------------
def insert_order():
    conn = get_connection()
    cursor = conn.cursor()
    while True:
        now = datetime.now()
        user_id = random.randint(1, 5000)
        restaurant_id = random.randint(1, 200)
        # 30% chance to have a related post; otherwise, set to NULL
        post_id = random.randint(1, 5000) if random.random() < 0.3 else None
        delivery_person_id = random.randint(1, 100)
        city_id = random.randint(1, 24)

        order_timestamp = now
        pickup_time = now + timedelta(minutes=random.randint(10, 20))
        delivery_latitude = round(random.uniform(30.0, 40.0), 6)
        delivery_longitude = round(random.uniform(8.0, 12.0), 6)
        status = random.choices(["Completed", "Cancelled"], weights=[0.9, 0.1])[0]
        total_price = round(random.uniform(10, 50), 2)
        time_taken_minutes = random.randint(15, 45)

        try:
            cursor.execute("""
                INSERT INTO orders 
                (user_id, restaurant_id, post_id, delivery_person_id, order_timestamp, pickup_time,
                 delivery_latitude, delivery_longitude, status, total_price, time_taken_minutes, city_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, restaurant_id, post_id, delivery_person_id, order_timestamp,
                  pickup_time, delivery_latitude, delivery_longitude, status, total_price, time_taken_minutes, city_id))
            conn.commit()
            print(f"[{datetime.now().isoformat()}] Inserted order.")
        except Exception as e:
            print("Error inserting order:", e)
            conn.rollback()
        time.sleep(2)  # Insert a new order every 2 seconds

# -------------------------
# Posts Insertion Function
# -------------------------
def insert_post():
    conn = get_connection()
    cursor = conn.cursor()
    while True:
        now = datetime.now()
        restaurant_id = random.randint(1, 200)
        description = fake.sentence(nb_words=10)
        image_url = f"https://via.placeholder.com/150?text=Food+{random.randint(1, 10000)}"
        posted_at = now
        try:
            cursor.execute("""
                INSERT INTO posts 
                (restaurant_id, image_url, description, posted_at)
                VALUES (%s, %s, %s, %s)
            """, (restaurant_id, image_url, description, posted_at))
            conn.commit()
            print(f"[{datetime.now().isoformat()}] Inserted post.")
        except Exception as e:
            print("Error inserting post:", e)
            conn.rollback()
        time.sleep(10)  # Insert a new post every 10 seconds

# ------------------------------
# New User Registration Function
# ------------------------------
def insert_user():
    conn = get_connection()
    cursor = conn.cursor()
    while True:
        now = datetime.now()
        # Create a unique username by appending a short timestamp snippet
        username = f"{fake.user_name()}{int(time.time()*1000)%10000}"
        email = f"{username.lower()}@example.tn"
        password = fake.password(length=10)
        address = fake.address().replace("\n", ", ")
        city_id = random.randint(1, 24)
        registration_date = now
        latitude = round(random.uniform(30.0, 40.0), 6)
        longitude = round(random.uniform(8.0, 12.0), 6)
        try:
            cursor.execute("""
                INSERT INTO users 
                (username, email, password, address, city_id, registration_date, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, email, password, address, city_id, registration_date, latitude, longitude))
            conn.commit()
            print(f"[{datetime.now().isoformat()}] Inserted user: {username}")
        except Exception as e:
            print("Error inserting user:", e)
            conn.rollback()
        time.sleep(15)  # Insert a new user every 15 seconds

# ------------------------------
# Weather Conditions Insertion Function
# ------------------------------
def insert_weather():
    conn = get_connection()
    cursor = conn.cursor()
    weather_options = ["Sunny", "Cloudy", "Rainy", "Hot", "Windy"]
    while True:
        now = datetime.now()
        city_id = random.randint(1, 24)
        timestamp = now  # Current time as timestamp
        weather = random.choice(weather_options)
        try:
            cursor.execute("""
                INSERT INTO weather_conditions 
                (city_id, timestamp, weather)
                VALUES (%s, %s, %s)
            """, (city_id, timestamp, weather))
            conn.commit()
            print(f"[{datetime.now().isoformat()}] Inserted weather: {weather} for city_id {city_id}")
        except Exception as e:
            print("Error inserting weather:", e)
            conn.rollback()
        time.sleep(20)  # Insert a new weather update every 20 seconds

# ------------------------------
# Main Function: Start Live Data Generation
# ------------------------------
if __name__ == "__main__":
    threads = []
    functions = [insert_order, insert_post, insert_user, insert_weather]

    for func in functions:
        thread = threading.Thread(target=func, daemon=True)
        threads.append(thread)
        thread.start()

    print("Live data generation started. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Live data generation stopped.")
