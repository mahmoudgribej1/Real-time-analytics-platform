import os
import random
import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
from sklearn.neighbors import BallTree
import math

# Setup Faker and seeds for reproducibility
fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)

# -----------------------------
# Helper Functions
# -----------------------------

def generate_restaurant_description():
    templates = [
        "A {} spot offering {} cuisine.",
        "Known for its {} atmosphere and {} dishes.",
        "A {} restaurant with an extensive menu of {} specialties.",
        "A {} eatery with a {} twist on classic dishes.",
        "Serving {} flavors with a {} touch.",
        "A popular destination for {} and {} meals.",
        "An inviting space with a focus on {} ingredients.",
        "A hidden gem known for its {} and {} service."
    ]
    adjectives = ["cozy", "elegant", "modern", "traditional", "vibrant", "charming", "inviting", "rustic", "trendy", "intimate", "lively", "artistic"]
    descriptors = ["fusion", "authentic", "local", "innovative", "exquisite", "classic", "seasonal", "organic", "fresh", "delicious"]
    template = random.choice(templates)
    num_placeholders = template.count("{}")
    values = []
    for i in range(num_placeholders):
        if i % 2 == 0:
            values.append(random.choice(adjectives))
        else:
            values.append(random.choice(descriptors))
    return template.format(*values)

restaurant_desc_counts = {}

def get_unique_restaurant_description(max_repeats=2):
    for _ in range(100):
        desc = generate_restaurant_description()
        count = restaurant_desc_counts.get(desc, 0)
        if count < max_repeats:
            restaurant_desc_counts[desc] = count + 1
            return desc
    return generate_restaurant_description()

def generate_post_description(sentiment):
    if sentiment == 'positive':
        templates = [
            "Absolutely {} and {}! Highly recommended.",
            "The {} taste and {} presentation exceeded expectations.",
            "A truly {} experience with {} flavors.",
            "Delicious, {} dish with {} service."
        ]
        adjectives1 = ["delightful", "amazing", "exceptional", "incredible", "fantastic", "remarkable"]
        adjectives2 = ["vibrant", "fresh", "satisfying", "memorable", "outstanding", "exquisite"]
    else:
        templates = [
            "Unfortunately, the dish was {} and {}.",
            "A {} experience with {} flavors.",
            "The {} presentation and {} taste left much to desire.",
            "Disappointing, {} dish with {} quality."
        ]
        adjectives1 = ["mediocre", "bland", "disappointing", "lackluster", "subpar", "unimpressive"]
        adjectives2 = ["poor", "unsatisfactory", "dull", "underwhelming", "off", "bad"]
    template = random.choice(templates)
    num_placeholders = template.count("{}")
    values = []
    for i in range(num_placeholders):
        if i % 2 == 0:
            values.append(random.choice(adjectives1))
        else:
            values.append(random.choice(adjectives2))
    return template.format(*values)

post_desc_counts = {}

def get_unique_post_description(sentiment, max_repeats=2):
    for _ in range(100):
        desc = generate_post_description(sentiment)
        count = post_desc_counts.get(desc, 0)
        if count < max_repeats:
            post_desc_counts[desc] = count + 1
            return desc
    return generate_post_description(sentiment)

def generate_realistic_order_time():
    peak_hours = [12, 13, 18, 19]
    off_peak = [8, 9, 10, 11, 14, 15, 16, 17, 20, 21]
    hour = random.choices(
        peak_hours + off_peak,
        weights=[15]*len(peak_hours) + [5]*len(off_peak),
        k=1
    )[0]
    return fake.date_time_this_year().replace(hour=hour)

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# -----------------------------
# Data Generation
# -----------------------------

project_root = os.getcwd()
output_dir = os.path.join(project_root, 'data', 'synthetic')
os.makedirs(output_dir, exist_ok=True)

# 1. CITIES with Population
governorates_data = [
    {"city_id": 1,  "city_name": "Ariana",      "governorate": "Ariana",      "latitude": 36.8665, "longitude": 10.1667, "population": 600000},
    {"city_id": 2,  "city_name": "Beja",        "governorate": "Beja",        "latitude": 36.7253, "longitude": 9.1817,  "population": 200000},
    {"city_id": 3,  "city_name": "Ben Arous",   "governorate": "Ben Arous",   "latitude": 36.7538, "longitude": 10.2182, "population": 800000},
    {"city_id": 4,  "city_name": "Bizerte",     "governorate": "Bizerte",     "latitude": 37.2744, "longitude": 9.8739,  "population": 150000},
    {"city_id": 5,  "city_name": "Gabes",       "governorate": "Gabes",       "latitude": 33.8815, "longitude": 10.0980, "population": 350000},
    {"city_id": 6,  "city_name": "Gafsa",       "governorate": "Gafsa",       "latitude": 34.4167, "longitude": 8.7833,  "population": 130000},
    {"city_id": 7,  "city_name": "Jendouba",    "governorate": "Jendouba",    "latitude": 36.5000, "longitude": 8.7833,  "population": 100000},
    {"city_id": 8,  "city_name": "Kairouan",    "governorate": "Kairouan",    "latitude": 35.6781, "longitude": 10.0968, "population": 180000},
    {"city_id": 9,  "city_name": "Kasserine",   "governorate": "Kasserine",   "latitude": 35.1675, "longitude": 8.8369,  "population": 90000},
    {"city_id": 10, "city_name": "Kebili",      "governorate": "Kebili",      "latitude": 33.7038, "longitude": 8.9700,  "population": 70000},
    {"city_id": 11, "city_name": "Kef",         "governorate": "Kef",         "latitude": 36.1811, "longitude": 8.7147,  "population": 120000},
    {"city_id": 12, "city_name": "Mahdia",      "governorate": "Mahdia",      "latitude": 35.5043, "longitude": 10.0968, "population": 140000},
    {"city_id": 13, "city_name": "Manouba",     "governorate": "Manouba",     "latitude": 36.8000, "longitude": 10.1667, "population": 250000},
    {"city_id": 14, "city_name": "Medenine",    "governorate": "Medenine",    "latitude": 33.3541, "longitude": 10.5275, "population": 110000},
    {"city_id": 15, "city_name": "Monastir",    "governorate": "Monastir",    "latitude": 35.7673, "longitude": 10.8110, "population": 220000},
    {"city_id": 16, "city_name": "Nabeul",      "governorate": "Nabeul",      "latitude": 36.4667, "longitude": 10.7333, "population": 700000},
    {"city_id": 17, "city_name": "Sfax",        "governorate": "Sfax",        "latitude": 34.7406, "longitude": 10.7600, "population": 350000},
    {"city_id": 18, "city_name": "Sidi Bouzid", "governorate": "Sidi Bouzid", "latitude": 35.0960, "longitude": 9.4825,  "population": 200000},
    {"city_id": 19, "city_name": "Siliana",     "governorate": "Siliana",     "latitude": 36.0833, "longitude": 9.3667,  "population": 280000},
    {"city_id": 20, "city_name": "Sousse",      "governorate": "Sousse",      "latitude": 35.8256, "longitude": 10.6084, "population": 650000},
    {"city_id": 21, "city_name": "Tataouine",   "governorate": "Tataouine",   "latitude": 32.9296, "longitude": 10.4517, "population": 45000},
    {"city_id": 22, "city_name": "Tozeur",      "governorate": "Tozeur",      "latitude": 33.9199, "longitude": 8.1337,  "population": 110000},
    {"city_id": 23, "city_name": "Tunis",       "governorate": "Tunis",       "latitude": 36.8065, "longitude": 10.1815, "population": 2700000},
    {"city_id": 24, "city_name": "Zaghouan",    "governorate": "Zaghouan",    "latitude": 36.4022, "longitude": 10.1445, "population": 190000}
]

cities_df = pd.DataFrame(governorates_data)
cities_df.to_csv(os.path.join(output_dir, 'cities.csv'), index=False)
print("Cities data generated.")

# 2. USERS with Registration Trends (fixed username uniqueness)
num_users = 5000
tunisian_first_names = [
    "Mohamed", "Ahmed", "Sami", "Houssem", "Yassine", "Ilyes", "Omar",
    "Karim", "Rami", "Tarek", "Salah", "Imen", "Amina", "Fatma", "Sana",
    "Lamia", "Meriem", "Rania", "Jawher", "Rim"
]
tunisian_last_names = [
    "Trabelsi", "BenAli", "Zouari", "Bouazizi", "Ghannouchi", "Jaziri",
    "Mekki", "Sassi", "Cherif", "Hamdi"
]

addresses_by_governorate = {
    "Tunis": [
        "130 Rue de Rafraf, Cite Medjerda, Tunis",
        "148 Rue des Pyramides, Cite Essalama, Tunis",
        "100 Rue de Tunis, Tunis"
    ],
    "Sfax": [
        "79 Rue de Damas, Merkez Chaker, Sfax",
        "149 Rue Mohammed Slim, Rabta, Sfax",
        "129 Ane Habib Bourguiba, Cite El Fateh, Sfax"
    ],
    "Sousse": [
        "62 Avenue Aghlabité, El Kantaoui, Sousse",
        "100 Avenue Aghlabité, M'saken El Gueblia, Sousse"
    ],
    "Nabeul": [
        "125 Rue de Marrakech, Cite El Bassatine, Nabeul",
        "48 Rue de Tanger, Cite Jemmali, Nabeul",
        "9 Rue des Pléiades, El Halfa, Nabeul"
    ],
    "Monastir": [
        "25 Rue du Maroc, Cite Nouvelle, Monastir",
        "27 Rue Sidi Bou Said, Cite Nouvelle, Monastir"
    ],
    "Bizerte": [
        "103 Rue Mohamed Mestiri, Mateur Hached, Bizerte",
        "62 Rue Mohamed Mestiri, El Mabtouh, Bizerte"
    ],
    "Kef": [
        "34 Rue Ali Ben Bechir Ibn Salem, Cite El Izdihar, Kef",
        "24 Rue Galboun Ibn Al Hassen, Cite Des Enseignants, Kef",
        "114 Rue Ali Ben Bechir Ibn Salem, Ouljet Essedra, Kef"
    ],
    "Jendouba": [
        "27 Rue Sidi Bou said, Tabarka Aeroport, Jendouba",
        "140 Rue Sidi Bou said, Cite Zone Industrielle, Jendouba"
    ],
    "Siliana": [
        "93 Rue Platon, Cite El Bassatine, Siliana",
        "77 Avenue Teboulbi, Merkez Ben Njah, Siliana",
        "59 Rue Platon, Fidh Arous, Siliana"
    ],
    "Sidi Bouzid": [
        "88 Rue de Kairouan, El Aatizez, Sidi Bouzid",
        "17 Rue Abdelkader, Cite Ezzouhour, Sidi Bouzid"
    ],
    "Manouba": [
        "96 Rue des Mimosas, Bou Regba, Manouba"
    ],
    "Tataouine": [
        "100 Rue Moftah Jguirim, Cite Du Bain Maure, Tataouine",
        "111 Rue Moftah Jguirim, El Farech, Tataouine"
    ],
    "Gafsa": [
        "98 Rue du Koweit, El Guettar, Gafsa",
        "104 Rue Al Imam Al Bakri, Alim, Gafsa"
    ],
    "Medenine": [
        "22 Rue Gabes, Tlet, Medenine",
        "111 Rue Elitha, Dar Jerba, Medenine"
    ],
    "Beja": [
        "27 Rue Andalousie, Nagachia, Beja",
        "140 Rue Elitha, Gueriche El Oued, Beja",
        "131 Rue Al Maari, Bouris, Beja",
        "46 Rue Al Maari, Cite Hached, Beja"
    ],
    "Ben Arous": [
        "74 Rue Aerobic, Cite El Misk, Ben Arous",
        "108 Rue Galboun Ibn Al Hassen, Residence El Ferdaous, Ben Arous"
    ],
    "Kairouan": [
        "24 Rue tachkent, Cherarda, Kairouan",
        "4 Rue de fes, Gragaya, Kairouan"
    ],
    "Kasserine": [
        "54 Rue Ali Ben Bechir Ibn Salem, Ouled Marzoug, Kasserine"
    ],
    "Gabes": [
        "134 Rue Jalel Eddine Nakache, El Hamma, Gabes"
    ],
    "Ariana": [
        "10 Avenue de la Liberté, Ariana"
    ],
    "Jendouba": [
        "Rue de la République, Jendouba"
    ],
    "Kebili": [
        "15 Rue de l'Indépendance, Kebili"
    ],
    "Mahdia": [
        "20 Rue de la Mer, Mahdia"
    ],
    "Medenine": [
        "Rue de la Méditerranée, Medenine"
    ],
    "Sidi Bouzid": [
        "Avenue des Martyrs, Sidi Bouzid"
    ],
    "Tozeur": [
        "5 Rue des Oasis, Tozeur"
    ],
    "Zaghouan": [
        "8 Rue de l'Industrie, Zaghouan"
    ]
}

users = []
for i in range(1, num_users + 1):
    governorate = random.choices(governorates_data, weights=[g['population'] for g in governorates_data])[0]
    # Use the user id (i) to guarantee username uniqueness
    username = f"{random.choice(tunisian_first_names)}{random.choice(tunisian_last_names)}{i}"
    gov_name = governorate["city_name"]
    address = random.choice(addresses_by_governorate.get(gov_name, [fake.address().replace("\n", ", ")]))
    email = f"{username.lower()}@example.tn"
    user_latitude = governorate["latitude"] + random.uniform(-0.05, 0.05)
    user_longitude = governorate["longitude"] + random.uniform(-0.05, 0.05)
    if random.random() < 0.6:
        registration_date = fake.date_time_between(start_date="-6M", end_date="now")
    else:
        registration_date = fake.date_time_between(start_date="-2y", end_date="now")
    users.append({
        "user_id": i,
        "username": username,
        "email": email,
        "password": fake.password(length=10),
        "address": address,
        "city_id": governorate["city_id"],
        "registration_date": registration_date,
        "latitude": user_latitude,
        "longitude": user_longitude
    })

users_df = pd.DataFrame(users)
users_df.to_csv(os.path.join(output_dir, 'users.csv'), index=False)
print("Users data generated.")

# 3. RESTAURANTS with Age-Based Ratings
num_restaurants = 200
french_base_names = ["Dupont", "Lefevre", "Durand", "Moreau", "Girard", "Lambert", "Bertrand", "Roux", "Faure", "Gauthier", "Belhaj", "BenYoussef", "Chaabane", "Marzouki", "BenAli", "Bouraoui", "Mejri", "Trabelsi"]
american_base_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
french_formats = [
    "Chez {}",
    "Le Petit {}",
    "La Rue de {}",
    "Au Coin de {}",
    "La Cantine {}",
    "{} du Coin"
]
american_formats = [
    "{} Burger Joint",
    "{} Diner",
    "{} Eatery",
    "{} Grill",
    "{} Pizza Hub"
]
bistro_format = "{} Bistro"

restaurants = []
for i in range(1, num_restaurants + 1):
    governorate = random.choices(governorates_data, weights=[g['population'] for g in governorates_data])[0]
    if random.random() < 0.7:
        base_name = random.choice(french_base_names)
        fmt = bistro_format if random.random() < 0.3 else random.choice(french_formats)
    else:
        base_name = random.choice(american_base_names)
        fmt = bistro_format if random.random() < 0.3 else random.choice(american_formats)
    restaurant_name = fmt.format(base_name)
    description = get_unique_restaurant_description()
    opening_date = fake.date_time_between(start_date="-5y", end_date="now")
    age_years = (datetime.now() - opening_date).days / 365
    base_rating = 3.0 + (min(age_years, 5)/5)*2
    rating = round(np.clip(np.random.normal(base_rating, 0.5), 3.0, 5.0), 1)
    restaurants.append({
        "restaurant_id": i,
        "name": restaurant_name,
        "description": description,
        "latitude": governorate["latitude"] + random.uniform(-0.05, 0.05),
        "longitude": governorate["longitude"] + random.uniform(-0.05, 0.05),
        "city_id": governorate["city_id"],
        "rating": rating,
        "opening_date": opening_date
    })

restaurants_df = pd.DataFrame(restaurants)
restaurants_df.to_csv(os.path.join(output_dir, 'restaurants.csv'), index=False)
print("Restaurants data generated.")

# 4. MENU ITEMS with Category Pricing
menu_item_names = {
    "Fast Food": {"price_range": (5, 15), "items": [
        "Classic Burger", "Cheese Burger", "Chicken Burger", "Veggie Burger",
        "Makloub", "Libanais", "Chawarma", "Tacos", "Kebab"
    ]},
    "Casual": {"price_range": (15, 30), "items": [
        "Margherita Pizza", "Pepperoni Pizza", "Veggie Pizza", "BBQ Chicken Pizza"
    ]},
    "Dessert": {"price_range": (5, 10), "items": [
        "Chocolate Cake", "Cheesecake", "Ice Cream Sundae", "Fruit Tart"
    ]},
    "Drinks": {"price_range": (2, 8), "items": [
        "Fresh Juice", "Iced Tea", "Smoothie", "Lemonade"
    ]}
}

menu_items = []
menu_item_id = 1
for rest in restaurants:
    num_items = random.randint(5, 15)
    for _ in range(num_items):
        category = random.choice(list(menu_item_names.keys()))
        price_range = menu_item_names[category]["price_range"]
        item_name = random.choice(menu_item_names[category]["items"])
        if random.random() < 0.05:
            item_price = None
        else:
            item_price = round(random.uniform(*price_range), 2)
        menu_items.append({
            "item_id": menu_item_id,
            "restaurant_id": rest["restaurant_id"],
            "item_name": item_name,
            "item_category": category,
            "item_price": item_price,
            "available_quantity": random.randint(10, 100)
        })
        menu_item_id += 1

menu_items_df = pd.DataFrame(menu_items)
menu_items_df.to_csv(os.path.join(output_dir, 'menu_items.csv'), index=False)
print("Menu items data generated.")

# 5. DELIVERY PERSONNEL with Vehicle Impact
num_delivery = 100
tunisian_first_names_expanded = [
    "Mohamed", "Ahmed", "Sami", "Houssem", "Yassine", "Ilyes", "Omar", "Karim", "Rami", "Tarek",
    "Salah", "Imen", "Amina", "Fatma", "Sana", "Lamia", "Meriem", "Rania", "Jawher", "Rim",
    "Fares", "Nabil", "Sofiene", "Amine", "Mahdi", "Selim", "Youssef", "Hichem", "Bassem", "Anis",
    "Ridha", "Taha", "Marwen", "Badr", "Adel", "Mounir", "Zied", "Khalil", "Hassen", "Mohcine",
    "Issam", "Habib", "Aziz", "Zaki", "Ibrahim", "Noureddine", "Kamel", "Sami", "Slim"
]
tunisian_last_names_expanded = [
    "Trabelsi", "BenAli", "Zouari", "Bouazizi", "Ghannouchi", "Jaziri", "Mekki", "Sassi", "Cherif", "Hamdi",
    "Belhaj", "BenYoussef", "Chaabane", "Marzouki", "BenAli", "Bouraoui", "Mejri", "Trabelsi", "Fakhfakh", "Dhouib",
    "Gharbi", "Zayani", "Khelifi", "Mekki", "Ayadi", "Amri", "Ouertani", "Masmoudi", "Dhaouadi", "Ben Rejeb",
    "Gharsallah", "Ben Miled", "Jouini", "Smail", "Boukhris", "Hamdoun", "Fendri", "Mekki", "Bouzid", "Hamzaoui",
    "Ben Cheikh", "Boujelbene", "Karkouch", "Boukhris", "Fakhfakh", "Dalli", "El Ghazali", "Khelifa", "Ben Amor", "Hajri"
]

delivery_personnel = []
for i in range(1, num_delivery + 1):
    governorate = random.choices(governorates_data, weights=[g['population'] for g in governorates_data])[0]
    name = f"{random.choice(tunisian_first_names_expanded)} {random.choice(tunisian_last_names_expanded)}"
    condition = random.randint(1, 5)
    speed_multiplier = 1 + (5 - condition)*0.1
    delivery_personnel.append({
        "delivery_person_id": i,
        "name": name,
        "age": random.randint(20, 50),
        "ratings": round(random.uniform(3.0, 5.0), 1),
        "vehicle_type": random.choice(["motorcycle", "scooter", "car", "bicycle"]),
        "vehicle_condition": condition,
        "speed_multiplier": speed_multiplier,
        "city_id": governorate["city_id"]
    })

delivery_personnel_df = pd.DataFrame(delivery_personnel)
delivery_personnel_df.to_csv(os.path.join(output_dir, 'delivery_personnel.csv'), index=False)
print("Delivery personnel data generated.")

# 6. POSTS with Rating Correlation
post_count = 5000
posts = []
for i in range(1, post_count + 1):
    restaurant = random.choice(restaurants)
    if restaurant['rating'] < 3.5:
        sentiment_weights = [0.4, 0.6]
    else:
        sentiment_weights = [0.8, 0.2]
    sentiment = random.choices(['positive', 'negative'], weights=sentiment_weights)[0]
    description = get_unique_post_description(sentiment)
    posts.append({
        "post_id": i,
        "restaurant_id": restaurant["restaurant_id"],
        "image_url": f"https://via.placeholder.com/150?text=Food+{i}",
        "description": description,
        "posted_at": fake.date_time_between(start_date=datetime(2025, 1, 1), end_date=datetime(2025, 3, 31))
    })

posts_df = pd.DataFrame(posts)
posts_df.to_csv(os.path.join(output_dir, 'posts.csv'), index=False)
print("Posts data generated.")

# 7. WEATHER with Order Volume Impact (before orders generation)
start_date_orders = datetime(2025, 1, 1)
end_date_orders = datetime(2025, 3, 31)
weather_conditions = []
weather_options = ["Sunny", "Cloudy", "Rainy", "Hot", "Windy"]
for city in governorates_data:
    for single_date in pd.date_range(start_date_orders, end_date_orders):
        weather_choice = random.choices(weather_options, weights=[0.3, 0.2, 0.2, 0.15, 0.15])[0]
        weather_conditions.append({
            "weather_id": len(weather_conditions) + 1,
            "city_id": city["city_id"],
            "timestamp": single_date.strftime('%Y-%m-%d'),
            "weather": weather_choice
        })

weather_df = pd.DataFrame(weather_conditions)
weather_df.to_csv(os.path.join(output_dir, 'weather_conditions.csv'), index=False)
print("Weather data generated.")

# 8. ORDERS with Distance/Weather Logic
num_orders = 10000
user_coords = BallTree(np.deg2rad(users_df[['latitude', 'longitude']].values), metric='haversine')
orders = []
for i in range(1, num_orders + 1):
    order_timestamp = generate_realistic_order_time()
    user = users_df.sample(1).iloc[0]
    restaurant = restaurants_df.sample(1).iloc[0]
    city_delivery = delivery_personnel_df[delivery_personnel_df['city_id'] == restaurant['city_id']]
    delivery = city_delivery.sample(1).iloc[0] if not city_delivery.empty else delivery_personnel_df.sample(1).iloc[0]
    rest_coords = np.deg2rad([[restaurant['latitude'], restaurant['longitude']]])
    distance_km, _ = user_coords.query(rest_coords, k=1)
    distance_km = distance_km[0][0] * 6371
    base_time = 20 + (distance_km * 5)
    time_taken = max(15, base_time * delivery['speed_multiplier'] + np.random.normal(0, 5))
    weather = pd.read_csv(os.path.join(output_dir, 'weather_conditions.csv'))
    order_date_str = order_timestamp.strftime('%Y-%m-%d')
    weather_condition = weather[(weather['city_id'] == restaurant['city_id']) & (weather['timestamp'] == order_date_str)]
    if not weather_condition.empty and weather_condition['weather'].values[0] == 'Rainy':
        time_taken *= 1.3
    if random.random() < 0.02:
        total_price = round(random.uniform(100, 500), 2)
    else:
        total_price = round(random.uniform(10, 50), 2)
    orders.append({
        "order_id": i,
        "user_id": user['user_id'],
        "restaurant_id": restaurant['restaurant_id'],
        "post_id": random.choice(posts)['post_id'] if random.random() < 0.3 else None,
        "delivery_person_id": delivery['delivery_person_id'],
        "order_timestamp": order_timestamp,
        "pickup_time": order_timestamp + timedelta(minutes=random.randint(10, 20)),
        "delivery_latitude": restaurant['latitude'] + random.uniform(-0.01, 0.01),
        "delivery_longitude": restaurant['longitude'] + random.uniform(-0.01, 0.01),
        "status": random.choices(["Completed", "Cancelled"], weights=[0.9, 0.1])[0],
        "total_price": total_price,
        "time_taken_minutes": round(time_taken),
        "city_id": restaurant['city_id']
    })

orders_df = pd.DataFrame(orders)
orders_df['post_id'] = orders_df['post_id'].astype('Int64')
orders_df.to_csv(os.path.join(output_dir, 'orders.csv'), index=False)
print("Orders data generated.")

# 9. FESTIVALS Distributed
festivals_data = []
tunisian_holidays = [
    ("New Year", "2025-01-01", "Public Holiday"),
    ("Ramadan Start", "2025-03-01", "Observance"),
    ("Independence Day", "2025-03-20", "Public Holiday"),
    ("Eid al-Fitr", "2025-03-30", "Public Holiday"),
    ("Martyrs' Day", "2025-04-09", "Public Holiday"),
    ("Labour Day", "2025-05-01", "Public Holiday"),
    ("Eid al-Adha", "2025-06-06", "Public Holiday"),
    ("Muharram", "2025-06-26", "Public Holiday"),
    ("Republic Day", "2025-07-25", "Public Holiday"),
    ("Women’s Day", "2025-08-13", "Public Holiday"),
    ("The Prophet's Birthday", "2025-09-04", "Public Holiday"),
    ("Evacuation Day", "2025-10-15", "Public Holiday"),
    ("Revolution and Youth Day", "2025-12-17", "Public Holiday")
]

for idx, (name, date, type) in enumerate(tunisian_holidays):
    city = random.choice(governorates_data)
    festivals_data.append({
        "festival_id": idx+1,
        "city_id": city["city_id"],
        "festival_name": name,
        "date": date,
        "type": type
    })

festivals_df = pd.DataFrame(festivals_data)
festivals_df.to_csv(os.path.join(output_dir, 'festivals_holidays.csv'), index=False)
print("Festivals data generated.")

# 10. VALIDATION
# Define an explicit mapping from foreign key to (filename, expected column)
validation_mapping = {
    "user_id": ("users.csv", "user_id"),
    "city_id": ("cities.csv", "city_id"),
    "restaurant_id": ("restaurants.csv", "restaurant_id"),
    "delivery_person_id": ("delivery_personnel.csv", "delivery_person_id"),
    "post_id": ("posts.csv", "post_id")
}

def validate_data(df, primary_key, foreign_keys):
    if df.duplicated(primary_key).any():
        print(f"Warning: Duplicate {primary_key} found")
    for fk in foreign_keys:
        if fk not in validation_mapping:
            print(f"Warning: No validation mapping for {fk}")
            continue
        filename, key_name = validation_mapping[fk]
        try:
            valid_df = pd.read_csv(os.path.join(output_dir, filename))
        except FileNotFoundError:
            print(f"Critical Error: {filename} not found")
            raise
        valid_ids = valid_df[key_name]
        # Only check non-null foreign key values
        invalid = df[fk].notna() & ~df[fk].isin(valid_ids)
        if invalid.any():
            print(f"Warning: Invalid {fk} found: {df[invalid]}")

validate_data(users_df, ['user_id'], ['city_id'])
validate_data(restaurants_df, ['restaurant_id'], ['city_id'])
validate_data(orders_df, ['order_id'], ['user_id', 'restaurant_id', 'delivery_person_id', 'post_id', 'city_id'])
