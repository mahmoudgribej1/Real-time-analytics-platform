-- =======================
-- 1. Create Database
-- =======================
-- CREATE DATABASE food_delivery;
-- \connect airflow;

-- =======================
-- 2. Cities Table
-- =======================
CREATE TABLE IF NOT EXISTS cities (
                                      city_id SERIAL PRIMARY KEY,
                                      city_name VARCHAR(255) NOT NULL,
    governorate VARCHAR(255) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    population INT NOT NULL  -- Added population, removed country
    );

-- =======================
-- 3. Users Table
-- =======================
CREATE TABLE IF NOT EXISTS users (
                                     user_id SERIAL PRIMARY KEY,
                                     username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    city_id INT NOT NULL,
    registration_date TIMESTAMP NOT NULL,
    latitude FLOAT NOT NULL,   -- Added latitude
    longitude FLOAT NOT NULL,  -- Added longitude
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
    );

-- =======================
-- 4. Restaurants Table
-- =======================
CREATE TABLE IF NOT EXISTS restaurants (
                                           restaurant_id SERIAL PRIMARY KEY,
                                           name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    city_id INT NOT NULL,
    rating DECIMAL(2,1) NOT NULL,
    opening_date TIMESTAMP NOT NULL,  -- Added opening_date
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
    );

-- =======================
-- 5. Menu Items Table
-- =======================
CREATE TABLE IF NOT EXISTS menu_items (
                                          item_id SERIAL PRIMARY KEY,
                                          restaurant_id INT NOT NULL,
                                          item_name VARCHAR(255) NOT NULL,
    item_category VARCHAR(100) NOT NULL,
    item_price FLOAT,  -- Changed to allow NULL values
    available_quantity INT NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
    );

-- =======================
-- 6. Delivery Personnel Table
-- =======================
CREATE TABLE IF NOT EXISTS delivery_personnel (
                                                  delivery_person_id SERIAL PRIMARY KEY,
                                                  name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    ratings FLOAT NOT NULL,
    vehicle_type VARCHAR(50) NOT NULL,
    vehicle_condition INT NOT NULL,
    speed_multiplier FLOAT NOT NULL,  -- Added speed_multiplier
    city_id INT NOT NULL,
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
    );

-- =======================
-- 7. Posts Table
-- =======================
CREATE TABLE IF NOT EXISTS posts (
                                     post_id SERIAL PRIMARY KEY,
                                     restaurant_id INT NOT NULL,
                                     image_url VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    posted_at TIMESTAMP NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
    );

-- =======================
-- 8. Weather Conditions Table
-- =======================
CREATE TABLE IF NOT EXISTS weather_conditions (
                                                  weather_id SERIAL PRIMARY KEY,
                                                  city_id INT NOT NULL,
                                                  timestamp TIMESTAMP NOT NULL,
                                                  weather VARCHAR(50) NOT NULL,
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
    );

-- =======================
-- 9. Festivals/Holidays Table
-- =======================
CREATE TABLE IF NOT EXISTS festivals_holidays (
                                                  festival_id SERIAL PRIMARY KEY,
                                                  city_id INT NOT NULL,
                                                  festival_name VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    type VARCHAR(50) NOT NULL,
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
    );
-- =======================
-- 10. Orders Table
-- =======================
CREATE TABLE IF NOT EXISTS orders (
                                      order_id SERIAL PRIMARY KEY,
                                      user_id INT NOT NULL,
                                      restaurant_id INT NOT NULL,
                                      post_id INT,
                                      delivery_person_id INT NOT NULL,
                                      order_timestamp TIMESTAMP NOT NULL,
                                      pickup_time TIMESTAMP NOT NULL,
                                      delivery_latitude FLOAT NOT NULL,
                                      delivery_longitude FLOAT NOT NULL,
                                      status VARCHAR(50) NOT NULL,
    total_price FLOAT NOT NULL,
    time_taken_minutes INT NOT NULL,  -- Changed from FLOAT to INT
    city_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id),
    FOREIGN KEY (post_id) REFERENCES posts(post_id),
    FOREIGN KEY (delivery_person_id) REFERENCES delivery_personnel(delivery_person_id),
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
    );