import pandas as pd
from geopy.geocoders import Nominatim
from time import sleep
import pandas as pd
import folium
from folium import Element
import sqlite3
import webbrowser
from user_checker import get_date, get_last_accepted_players


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
    df['city'] = df['city'].replace("BAGNOLES DE LORNE', 'BAGNOLES DE L'ORNE")
    df['city'] = df['city'].replace("CAP DAGDE', 'CAP D'AGDE")

    df['city'] = df['city'].replace(r'\s*\(.*?\)', '', regex=True)
    df['country'] = df['country'].replace('GREAT BRITAIN', 'UK')
    df['country'] = df['country'].replace('CHINA, P.R.', 'CHINA')
    df['country'] = df['country'].replace('KOREA, REP.', 'SOUTH KOREA')
    

    # Add comma before state abbreviations (e.g. "Boca Raton FL" to "Boca Raton, FL")
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

def clean_city_names_df(df):
    """
    Cleans and standardizes city and country names while preserving
    the original values for accurate database matching later.

    Returns a DataFrame with:
    ['original_city', 'original_country', 'clean_city', 'clean_country']
    """

    df = df.copy()  # avoid modifying original

    # Preserve originals
    df['original_city'] = df['city']
    df['original_country'] = df['country']

    # Fix known naming inconsistencies
    df['city'] = df['city'].replace('SHARM ELSHEIKH', 'SHARM EL SHEIKH')
    df['city'] = df['city'].replace('QIAN DAOHU', 'QIANDAOHU')
    df['city'] = df['city'].replace('VALE DO LOBO', 'VALE DE LOBO')
    df['city'] = df['city'].replace("BAGNOLES DE LORNE", "BAGNOLES DE L'ORNE")
    df['city'] = df['city'].replace("BAGNOLES DE LORNE PLUSH", "BAGNOLES DE L'ORNE")

    df['city'] = df['city'].replace("CAP DAGDE", "CAP D'AGDE")


    df['city'] = df['city'].replace(r'\s*\(.*?\)', '', regex=True)

    df['country'] = df['country'].replace('GREAT BRITAIN', 'UK')
    df['country'] = df['country'].replace('CHINA, P.R.', 'CHINA')
    df['country'] = df['country'].replace('KOREA, REP.', 'SOUTH KOREA')

    # US specific formatting
    def format_us_city(city, country):
        if country == 'USA' and isinstance(city, str) and len(city) >= 3 and city[-3] == ' ':
            return city[:-3] + ',' + city[-3:]
        return city

    df['city'] = df.apply(lambda row: format_us_city(row['city'], row['country']), axis=1)

    df['clean_city'] = df['city'].str.strip()
    df['clean_country'] = df['country'].str.strip()

    # Drop duplicates so we only geocode unique clean pairs
    df_unique = df[['original_city', 'original_country', 'clean_city', 'clean_country']].drop_duplicates().reset_index(drop=True)

    return df_unique



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
        output_file (str): File path to save the HTML map.
    """
    # Join tLocations with coords_df on city and country to get lat/lon
    coords_df.to_sql("temp_cleaned_cities", conn, if_exists="replace", index=False)

    # Perform the SQL join
    query = """
    SELECT 
        c.clean_city AS city,
        c.clean_country AS country,
        c.original_city AS og_city,
        c.original_country AS og_country,
        t.latitude,
        t.longitude
    FROM temp_cleaned_cities AS c
    LEFT JOIN tLocations AS t
        ON UPPER(c.original_city) = UPPER(t.city)
        AND UPPER(c.original_country) = UPPER(t.country);
    """
    # Read results back into pandas
    coords_df = pd.read_sql(query, conn)

    # Drop temp table if not needed anymore
    conn.execute("DROP TABLE IF EXISTS temp_cleaned_cities;")

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
    if num_points > 2:
        m.fit_bounds(bounds, padding=(120, 120))

    # Add markers for each city

    if choice == "country":
        for _, row in coords_df.dropna(subset=['latitude', 'longitude']).iterrows():
            # Count all the instances of og city, country pairs that exist in the database
            count_result = pd.read_sql("""
                SELECT COUNT(*) as tournament_count
                FROM tTournaments
                WHERE UPPER(city) = UPPER(?)
                AND UPPER(country) = UPPER(?);
            """, conn, params=(row['og_city'], row['og_country']))
            tooltip_html = f"""
            <b>{row['city']}</b><br>
            {row['country']}</b><br>
            Number of Tournaments: {count_result['tournament_count'].iloc[0]}
            """
            folium.Marker(
                [row['latitude'], row['longitude']],
                tooltip=folium.Tooltip(tooltip_html, sticky=True),
            ).add_to(m)
    else:
        last_player = get_last_accepted_players(week, conn)
        for _, row in coords_df.dropna(subset=['latitude', 'longitude']).iterrows():

            # Query database for additional info about the tournament in that city/country for that week
            popup_info = pd.read_sql("""
                SELECT tournament_key, qualysize, qualybyes
                FROM tTournaments
                WHERE UPPER(city) = UPPER(?)
                AND UPPER(country) = UPPER(?)
                AND date_started = ?;
            """, conn, params=(row['og_city'], row['og_country'], week))    

            # Use tournament key in popup_info to find last accepted player
            last_accepted = last_player[last_player['tournament_key'] == popup_info['tournament_key'].iloc[0]]
            # if dataframe is empty, there were byes so empty spots!
            if last_accepted.empty:
                last_accepted_name = "N/A (Byes present)"
            else:
                last_accepted_name = last_accepted['player_name'].iloc[0]
                last_accepted_name = f"{last_accepted['player_name'].iloc[0]} : {last_accepted['rank_type'].iloc[0]} {last_accepted['rank_value'].iloc[0]}"
            # Detailed info (click)
            tooltip_html = f"""
            <b>{row['city']}, {row['country']}</b><br>
            Qualifying Size: {popup_info['qualysize'].iloc[0]}<br>
            Byes: {popup_info['qualybyes'].iloc[0]}<br>
            Last Accepted Player: {last_accepted_name}
            """

            folium.Marker(
                [row['latitude'], row['longitude']],
                tooltip=folium.Tooltip(tooltip_html, sticky=True)
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
            country = parts[1] if len(parts) > 1 else None

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


def insert_new_locs():
    missing_coords = pd.read_sql("""
    SELECT *
    FROM tLocations
    WHERE (latitude IS NULL OR longitude IS NULL);
    """, conn)

    # Handle case where there are no missing coordinates
    if missing_coords.empty:
        print("✅ All locations already have coordinates! Nothing to update.")
    else:
        # Step 2: Clean names — now keeps both clean and original names
        try:
            city_map = clean_city_names_df(missing_coords)
        except Exception as e:
            print(f"❌ Error cleaning city names: {e}")
            raise

        if city_map.empty:
            print("✅ All cleaned locations already have coordinates!")
        else:
            print(f"🗺️ Found {len(city_map)} locations missing coordinates.")
            
            try:
                # Step 3: Fetch coordinates using the cleaned city+country
                coords_df = get_city_coordinates(
                    [f"{row.clean_city}, {row.clean_country}" for _, row in city_map.iterrows()]
                )
            except Exception as e:
                print(f"❌ Error fetching coordinates: {e}")
                raise

            # Step 4: Merge coordinates back with original names
            merged = city_map.merge(
                coords_df,
                left_on=["clean_city", "clean_country"],
                right_on=["city", "country"],
                how="left"
            )

            # Step 5: Update the database using the ORIGINAL city+country
            updated_count = 0
            skipped_count = 0

            for _, row in merged.iterrows():
                if pd.notnull(row["latitude"]) and pd.notnull(row["longitude"]):
                    conn.execute("""
                        UPDATE tLocations
                        SET latitude = ?, longitude = ?
                        WHERE city = ? AND country = ?;
                    """, (
                        row["latitude"],
                        row["longitude"],
                        row["original_city"],
                        row["original_country"]
                    ))
                    print(f"✅ Updated: {row['original_city']}, {row['original_country']}")
                    updated_count += 1
                else:
                    print(f"⚠️ Skipped: {row['original_city']}, {row['original_country']} (no coordinates found)")
                    skipped_count += 1

            conn.commit()
            print(f"🎯 Done! {updated_count} updated, {skipped_count} skipped.")

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

    city_country_df = clean_city_names_df(initialq)

    create_country_map(city_country_df)
