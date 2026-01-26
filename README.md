# ITF Tournament Analysis & Mapping Tool

An interactive Python application that scrapes player data from qualifying of **ITF tennis
tournaments**. The data is stored in a SQLite database and can be used to compare entry cutoffs,
analyze past tournament fields, and display tournament locations.
The tool supports mapping tournaments by **country** or by **week**, and
enriches each location with tournament-specific details.
The goal was to have a unified database of all qualifying draws of ITF tournaments to help 
low-ranked professional players understand acceptance trends and patterns to help them make
informed, data-based decisions on travel and tournament scheduling.

------------------------------------------------------------------------

## Features

-   🗺️ **Interactive maps** built with Folium
-   📍 Automatic **city geocoding** via OpenStreetMap (Nominatim)
-   🧹 Robust **city and country name standardization**
-   🗄️ SQLite database integration with foreign key enforcement
-   
-   🔄 Automatically updates missing/new latitude/longitude values in the database

------------------------------------------------------------------------

## Project Structure

    .
    ├── itf_tournaments.db        # SQLite database
    ├── map_creation.py          # Displays interactive map of tournaments on specified week or country
    ├── scraper.py          # Main scraper used to append tournament and player data to database
    ├── tournament.py          # Outputs all players from specified tournament with acceptance list data.
    ├── user_checker.py           # Compares user ranking with specified week, and outputs whether user would have been accepted.
    ├── README.md                 # Project documentation

------------------------------------------------------------------------

## Requirements

-   Python 3.9+
-   SQLite

### Python Libraries

    pandas
    geopy
    folium
    sqlite3

Install dependencies:

``` bash
pip install pandas geopy folium
```

------------------------------------------------------------------------

## Database Tables Used

-   **tTournaments**
    -   Tournament metadata (tournament key, city, country, dates, qualifying info)
-   **tPlayerInfo**
    -   Player data for all tournaments (name, ranking, tournament key, acceptance list position)
-   **tLocations**
    -   City-level latitude and longitude storage

The script automatically joins and updates these tables as needed.

------------------------------------------------------------------------

## Usage: Map Creation (`map_creation.py`)

Run the script from the command line:

``` bash
python map_creation.py
```

You will be prompted to choose:

-   **country** → Map all tournaments hosted in a selected country
-   **week** → Map tournaments occurring in a specific week (Enter starting day of tournament)

The generated interactive map will: - Save as an HTML file -
Automatically open in your default browser


## Usage: Tournament Scraper (`scraper.py`)

This script scrapes ITF tournament data for a given start date and populates the SQLite database with tournament, player, and acceptance list information.

Run from the command line with a tournament start date:

```bash
python scraper.py "12 Jan"
```


## Usage: Tournament Player Lookup (`tournament.py`)

This script allows you to query all players associated with a specific tournament using its unique tournament key.

Run the script:

```bash
python tournament.py
```


## Usage: Player Eligibility Checker (`user_checker.py`)

This interactive script determines which tournaments a player could have been accepted based on their ranking and a selected tournament week.

Run the script:

```bash
python user_checker.py
```

------------------------------------------------------------------------

## Geolocation Logic

1.  Detects cities with missing coordinates
2.  Cleans and standardizes city/country names
3.  Fetches coordinates via OpenStreetMap
4.  Updates the database using original city-country pairs

Rate limiting is enforced to respect geocoding service policies.

------------------------------------------------------------------------

## Example Output

-   Hoverable city markers
-   Dynamic tooltips with tournament statistics
-   Auto-scaled map bounds
-   Custom HTML title based on user selection

------------------------------------------------------------------------

## Potential Extensions

-   Player-level visualizations
-   Tournament surface or category filters
-   Historical trend analysis
-   Deployment as a web dashboard

------------------------------------------------------------------------

## Author

**David Garcia Carrasco**

------------------------------------------------------------------------

## Disclaimer

This project uses public geolocation services (OpenStreetMap /
Nominatim).\
Please avoid excessive automated requests to comply with usage policies.
