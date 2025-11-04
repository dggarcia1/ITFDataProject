import pandas as pd
from geopy.geocoders import Nominatim
from time import sleep
import pandas as pd
import folium
from folium import Element
import sqlite3
import webbrowser
from user_checker import get_date


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
    df['city'] = df['city'].replace('QIAN DAOHU', 'QIANDAOHU')
    df['city'] = df['city'].replace('VALE DO LOBO', 'VALE DE LOBO')
    df['city'] = df['city'].replace(r'\s*\(.*?\)', '', regex=True)
    df['country'] = df['country'].replace('GREAT BRITAIN', 'UK')
    df['country'] = df['country'].replace('CHINA, P.R.', 'CHINA')
    df['country'] = df['country'].replace('KOREA, REP.', 'SOUTH KOREA')
    

    # Add comma before state abbreviations (e.g. "Boca Raton FL" → "Boca Raton, FL")
    def format_us_city(city, country):
        if country == 'USA' and isinstance(city, str) and len(city) >= 3 and city[-3] == ' ':
            return city[:-3] + ',' + city[-3:]
        return city
    df['city'] = df.apply(lambda row: format_us_city(row['city'], row['country']), axis=1)

    # Create city-country combined strings for geocoding
    cities = df['city'].dropna().tolist()
    cities = [city.strip() for city in cities]

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

    while True:
        country_input = input("What country would you like to create a map for? ")
        country = country_input.strip().upper()
        try:
            if country in [c.upper() for c in valid_countries]:
                print(f"✅ Creating map for {country}...")
                return country
            else:
                # Country not found: ask again
                print(f"❌ There haven't been any tournaments in {country_input}. Please try again.")
        except Exception as e:
            # Catch unexpected errors and prompt again
            print(f"❌ Error checking the country: {e}. Please try again.")



def create_country_map(coords_df, output_file="world_map.html"):
    """
    Creates a folium map centered on the coordinates in coords_df,
    adds markers for each city, includes a title with the country,
    saves the map to an HTML file, and opens it in the default browser.

    Parameters:
        coords_df (pd.DataFrame): DataFrame with 'city', 'latitude', 'longitude' columns.
        country (str): Name of the country for the map title.
        output_file (str): File path to save the HTML map.
    """
    
    # Make sure there are valid coordinates
    bounds = coords_df[['latitude', 'longitude']].dropna().values.tolist()
    if not bounds:
        raise ValueError("No valid coordinates found in coords_df.")

    # Compute average lat/lon for initial map center
    avg_lat = sum(lat for lat, lon in bounds) / len(bounds)
    avg_lon = sum(lon for lat, lon in bounds) / len(bounds)

    num_points = len(bounds)

    # Initialize the map
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=8)
    if num_points > 1:
        m.fit_bounds(bounds, padding=(120, 120))

    # Add markers for each city
    for _, row in coords_df.dropna(subset=['latitude', 'longitude']).iterrows():
        folium.Marker(
            [row['latitude'], row['longitude']],
            tooltip=row['city']
        ).add_to(m)

    # Change title based on if they chose country or week
    if choice == "country":
        title_html = f"""<h3 align="center" style="font-size:20px"><b>ITF Tournaments in {country}</b></h3>"""
    else:
        title_html = f"""<h3 align="center" style="font-size:20px"><b>ITF Tournaments in the week starting {week}</b></h3>"""
    m.get_root().html.add_child(Element(title_html))

    # Save and open map
    m.save(output_file)
    print(f"✅ Map with title saved as {output_file}")
    webbrowser.open(output_file)
    
    return m


def get_city_coordinates(city_country_list, delay=1.2):
    """
    Given a list like ["Paris, France", "Tokyo, Japan"],
    fetch latitude and longitude for each using Nominatim (OpenStreetMap).

    Returns columns: ['city', 'country', 'latitude', 'longitude']
    """
    geolocator = Nominatim(user_agent="city_to_coordinates_converter", timeout=10)
    results = []

    for city_country in city_country_list:
        try:
            # Split "City, Country" into two parts
            parts = [x.strip() for x in city_country.rsplit(",", 1)]
            city = parts[0]
            print(city)
            country = parts[1] if len(parts) > 1 else None
            print(country)

            location = geolocator.geocode(city_country)
            if location:
                print(f"{city_country}: {location.latitude}, {location.longitude}")
                results.append({
                    'city': city,
                    'country': country,
                    'latitude': location.latitude,
                    'longitude': location.longitude
                })
            else:
                print(f"Could not find coordinates for {city_country}.")
                results.append({
                    'city': city,
                    'country': country,
                    'latitude': None,
                    'longitude': None
                })
        except Exception as e:
            print(f"Error processing {city_country}: {e}")
            results.append({
                'city': city,
                'country': country,
                'latitude': None,
                'longitude': None
            })

        sleep(delay)

    return pd.DataFrame(results)


if __name__ == "__main__":
    choice = input("Do you want to create the map based on country or week? (country/week): ").strip().lower()

    if choice == "country":
        country = get_valid_country()
        initialq = pd.read_sql("""
            SELECT *
            FROM tTournaments
            WHERE country = ?
        ;""", conn, params=(country,))
    else:
        week = get_date()
        initialq = pd.read_sql("""
            SELECT *
            FROM tTournaments
            WHERE date_started = ?
        ;""", conn, params=(week,))

    city_country = clean_city_names(initialq)

    results = get_city_coordinates(city_country)

    create_country_map(results)

# Initialize the geolocator
#geolocator = Nominatim(user_agent="city_to_coordinates_converter", timeout=10)

# List of cities (e.g. city_country = ["Paris, France", "Tokyo, Japan"])
#cities = city_country

# Empty list to collect results
#results = []

# Loop through each city and get coordinates
#for city in cities:
#    try:
#        location = geolocator.geocode(city)
#        if location:
#            print(f"{city}: {location.latitude}, {location.longitude}")
#            results.append({
#                'city': city,
#                'latitude': location.latitude,
#                'longitude': location.longitude
#            })
#        else:
#            print(f"Could not find coordinates for {city}.")
#            results.append({
#                'city': city,
#                'latitude': None,
#                'longitude': None
#            })
#    except Exception as e:
#        print(f"Error processing {city}: {e}")
#      results.append({
#            'city': city,
#            'latitude': None,
#            'longitude': None
#        })
#    
    # Delay to respect Nominatim rate limits
#    sleep(1.2)


#create_country_map(pd.DataFrame(results))

