import os
import random
import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime

# Setup
fake = Faker()
Faker.seed(42)
np.random.seed(42)
random.seed(42)

output_dir = os.path.join(os.getcwd(), 'data', 'synthetic')
os.makedirs(output_dir, exist_ok=True)

# Reuse the same governorates data you had
governorates_data = [{"city_id": 1,  "city_name": "Ariana",      "governorate": "Ariana",      "latitude": 36.8665, "longitude": 10.1667, "country": "Tunisia"},
                     {"city_id": 2,  "city_name": "Beja",        "governorate": "Beja",        "latitude": 36.7253, "longitude": 9.1817,  "country": "Tunisia"},
                     {"city_id": 3,  "city_name": "Ben Arous",   "governorate": "Ben Arous",   "latitude": 36.7538, "longitude": 10.2182, "country": "Tunisia"},
                     {"city_id": 4,  "city_name": "Bizerte",     "governorate": "Bizerte",     "latitude": 37.2744, "longitude": 9.8739,  "country": "Tunisia"},
                     {"city_id": 5,  "city_name": "Gabes",       "governorate": "Gabes",       "latitude": 33.8815, "longitude": 10.0980, "country": "Tunisia"},
                     {"city_id": 6,  "city_name": "Gafsa",       "governorate": "Gafsa",       "latitude": 34.4167, "longitude": 8.7833,  "country": "Tunisia"},
                     {"city_id": 7,  "city_name": "Jendouba",    "governorate": "Jendouba",    "latitude": 36.5000, "longitude": 8.7833,  "country": "Tunisia"},
                     {"city_id": 8,  "city_name": "Kairouan",    "governorate": "Kairouan",    "latitude": 35.6781, "longitude": 10.0968, "country": "Tunisia"},
                     {"city_id": 9,  "city_name": "Kasserine",   "governorate": "Kasserine",   "latitude": 35.1675, "longitude": 8.8369,  "country": "Tunisia"},
                     {"city_id": 10, "city_name": "Kebili",      "governorate": "Kebili",      "latitude": 33.7038, "longitude": 8.9700,  "country": "Tunisia"},
                     {"city_id": 11, "city_name": "Kef",         "governorate": "Kef",         "latitude": 36.1811, "longitude": 8.7147,  "country": "Tunisia"},
                     {"city_id": 12, "city_name": "Mahdia",      "governorate": "Mahdia",      "latitude": 35.5043, "longitude": 10.0968, "country": "Tunisia"},
                     {"city_id": 13, "city_name": "Manouba",     "governorate": "Manouba",     "latitude": 36.8000, "longitude": 10.1667, "country": "Tunisia"},
                     {"city_id": 14, "city_name": "Medenine",    "governorate": "Medenine",    "latitude": 33.3541, "longitude": 10.5275, "country": "Tunisia"},
                     {"city_id": 15, "city_name": "Monastir",    "governorate": "Monastir",    "latitude": 35.7673, "longitude": 10.8110, "country": "Tunisia"},
                     {"city_id": 16, "city_name": "Nabeul",      "governorate": "Nabeul",      "latitude": 36.4667, "longitude": 10.7333, "country": "Tunisia"},
                     {"city_id": 17, "city_name": "Sfax",        "governorate": "Sfax",        "latitude": 34.7406, "longitude": 10.7600, "country": "Tunisia"},
                     {"city_id": 18, "city_name": "Sidi Bouzid", "governorate": "Sidi Bouzid", "latitude": 35.0960, "longitude": 9.4825,  "country": "Tunisia"},
                     {"city_id": 19, "city_name": "Siliana",     "governorate": "Siliana",     "latitude": 36.0833, "longitude": 9.3667,  "country": "Tunisia"},
                     {"city_id": 20, "city_name": "Sousse",      "governorate": "Sousse",      "latitude": 35.8256, "longitude": 10.6084, "country": "Tunisia"},
                     {"city_id": 21, "city_name": "Tataouine",   "governorate": "Tataouine",   "latitude": 32.9296, "longitude": 10.4517, "country": "Tunisia"},
                     {"city_id": 22, "city_name": "Tozeur",      "governorate": "Tozeur",      "latitude": 33.9199, "longitude": 8.1337,  "country": "Tunisia"},
                     {"city_id": 23, "city_name": "Tunis",       "governorate": "Tunis",       "latitude": 36.8065, "longitude": 10.1815, "country": "Tunisia"},
                     {"city_id": 24, "city_name": "Zaghouan",    "governorate": "Zaghouan",    "latitude": 36.4022, "longitude": 10.1445, "country": "Tunisia"}]  # <--- paste the same list from your original script here

# Tunisian names and addresses (same as before)
tunisian_first_names = ["Mohamed", "Ahmed", "Sami", "Houssem", "Yassine", "Ilyes", "Omar", "Karim", "Rami", "Tarek", "Salah", "Imen", "Amina", "Fatma", "Sana", "Lamia", "Meriem", "Rania", "Jawher", "Rim"]
tunisian_last_names = ["Trabelsi", "BenAli", "Zouari", "Bouazizi", "Ghannouchi", "Jaziri", "Mekki", "Sassi", "Cherif", "Hamdi"]
addresses_by_governorate = {"Tunis": [
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
    ]}  # <--- paste the same dict from your original script here

num_users = 5000
usernames_set = set()
emails_set = set()
users = []

i = 1
while len(users) < num_users:
    governorate = random.choice(governorates_data)
    city_id = governorate["city_id"]
    gov_name = governorate["city_name"]

    base_username = f"{random.choice(tunisian_first_names)}{random.choice(tunisian_last_names)}"
    suffix = random.randint(1, 1000)
    username = f"{base_username}{suffix}"
    email = f"{username.lower()}@example.tn"

    if username in usernames_set or email in emails_set:
        continue  # regenerate if not unique

    address_list = addresses_by_governorate.get(gov_name, [fake.address().replace("\n", ", ")])
    address = random.choice(address_list)

    users.append({
        "user_id": i,
        "username": username,
        "email": email,
        "password": fake.password(length=10),
        "address": address,
        "city_id": city_id,
        "registration_date": fake.date_time_between(start_date="-2y", end_date="now")
    })

    usernames_set.add(username)
    emails_set.add(email)
    i += 1

# Save to CSV
users_df = pd.DataFrame(users)
users_df.to_csv(os.path.join(output_dir, 'users.csv'), index=False)
print(f"Generated {len(users)} unique users in users.csv")
