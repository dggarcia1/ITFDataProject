import pandas as pd
from geopy.geocoders import Nominatim
from time import sleep
import pandas as pd
import folium
from folium.features import DivIcon
from folium import Element
import sqlite3
import webbrowser

pd.set_option('display.max_rows', None)
conn = sqlite3.connect('itf_tournaments.db')
curs = conn.cursor()
curs.execute("PRAGMA foreign_keys=ON;")

def clean_city_names(df):
    """
    Cleans and standardizes city and country names, and
    returns both the cleaned DataFrame and a list of unique 'city, country' pairs.
    """

    # Fix known naming inconsistencies
    df['city'] = df['city'].replace('SHARM ELSHEIKH', 'SHARM EL SHEIKH')
    df['country'] = df['country'].replace('GREAT BRITAIN', 'UK')

    # Add comma before state abbreviations (e.g. "Boca Raton FL" → "Boca Raton, FL")
    def format_us_city(city, country):
        if country == 'USA' and isinstance(city, str) and len(city) >= 3 and city[-3] == ' ':
            return city[:-3] + ',' + city[-3:]
        return city
    df['city'] = df.apply(lambda row: format_us_city(row['city'], row['country']), axis=1)

    # Create city-country combined strings for geocoding
    cities = df['city'].dropna().tolist()
    countries = df['country'].dropna().tolist()
    city_country = [f"{city}, {country}" for city, country in zip(cities, countries)]

    # Remove duplicates while preserving order
    city_country = list(dict.fromkeys(city_country))

    return city_country

def get_valid_country():
    """
    Prompts user for a country name, capitalizes it,
    and checks if it exists in the provided list of valid_countries.
    """

    valid_countries = pd.read_sql("""
            SELECT DISTINCT country
            FROM tTournaments
    ;""", conn)['country'].tolist()

    country = input("What country would you like to create a map for? ").strip().upper()

    if country in [c.upper() for c in valid_countries]:
        print(f"✅ Creating map for {country}...")
        return country
    else:
        print(f"❌ There haven't been any tournaments in {country}.")
        return None

country = get_valid_country()

initialq = pd.read_sql("""
        SELECT *
        FROM tTournaments
        WHERE country == ?
;""", conn, params=(country,))

city_country = clean_city_names(initialq)

# Initialize the geolocator
geolocator = Nominatim(user_agent="city_to_coordinates_converter", timeout=10)

# List of cities (e.g. city_country = ["Paris, France", "Tokyo, Japan"])
cities = city_country

# Empty list to collect results
results = []

# Loop through each city and get coordinates
for city in cities:
    try:
        location = geolocator.geocode(city)
        if location:
            print(f"{city}: {location.latitude}, {location.longitude}")
            results.append({
                'city': city,
                'latitude': location.latitude,
                'longitude': location.longitude
            })
        else:
            print(f"Could not find coordinates for {city}.")
            results.append({
                'city': city,
                'latitude': None,
                'longitude': None
            })
    except Exception as e:
        print(f"Error processing {city}: {e}")
        results.append({
            'city': city,
            'latitude': None,
            'longitude': None
        })
    
    # Delay to respect Nominatim rate limits
    sleep(1.2)

# Convert results to DataFrame
coords_df = pd.DataFrame(results)

# Create base map
m = folium.Map(location=[20, 0], zoom_start=5)

# Example markers (your coords_df loop goes here)
for _, row in coords_df.dropna(subset=['latitude', 'longitude']).iterrows():
    folium.Marker(
        [row['latitude'], row['longitude']],
        tooltip=row['city']
    ).add_to(m)

# Automatically adjust map to fit all markers
bounds = coords_df[['latitude', 'longitude']].dropna().values.tolist()
m.fit_bounds(bounds)

# Add a title at the top
title_html = f"""<h3 align="center" style="font-size:20px"><b>ITF Tournaments in {country}</b></h3>"""
     
m.get_root().html.add_child(Element(title_html))

# Save map
m.save("world_map.html")
print("✅ Map with title saved as world_map.html")
webbrowser.open("world_map.html")
