from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException
import map_creation
import sqlite3
import time
import pandas as pd
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_tournament_links_by_date(driver, desired_date, timeout=10):
    wait = WebDriverWait(driver, timeout)
    websites = []

    wait.until(
        EC.presence_of_element_located((By.CLASS_NAME, "whatson-table"))
    )

    rows = driver.find_elements(
        By.CSS_SELECTOR, "tr.whatson-table__tournament"
    )

    for row in rows:
        try:
            date_text = row.find_element(
                By.CSS_SELECTOR, "td.date span.date"
            ).text.strip()

            if desired_date in date_text:
                href = row.find_element(
                    By.CSS_SELECTOR, "td.name a"
                ).get_attribute("href")

                if href.startswith("/"):
                    href = "https://www.itftennis.com" + href

                websites.append(href)

        except (StaleElementReferenceException, NoSuchElementException):
            continue

    return websites

def tournament_exists(conn, tournament_key):
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM tTournaments WHERE tournament_key = ? LIMIT 1;",
        (tournament_key,)
    )
    exists = cur.fetchone() is not None
    cur.close()
    return exists



def extract_table_data(table):
    table_data = []
    rows = table.find_elements(By.TAG_NAME, "tr")

    for row in rows:
        columns = row.find_elements(By.TAG_NAME, "td")
        row_data = [column.text for column in columns]  
        table_data.append(row_data)

    return pd.DataFrame(table_data)

def get_player_ranking(player_data):
    
    player_name = player_data['PLAYER']
    
    if player_data['ATP RANKING']:
        return player_name, f"ATP ranking: {player_data['ATP RANKING']}"
    elif player_data['ITF RANKING']:
        return player_name, f"ITF ranking: {player_data['ITF RANKING']}"
    elif player_data['WTN'] != '-':
        return player_name, f"WTN: {player_data['WTN']}"
    elif player_data['NATIONAL RANKING']:
        return player_name, f"National ranking: {player_data['NATIONAL RANKING']}"
    else:
        return player_name, 'No ranking'
    
def insert_tournament(conn, tournament_data):
    curs = conn.cursor()

    query = """
    INSERT OR IGNORE INTO tTournaments (
        tournament_key, city, country, points, prize_money,
        date_started, date_ended, qualysize, qualybyes, surface, in_out, location_id
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    
    curs.execute(query, tournament_data)
    conn.commit()
    curs.close()



def insert_players(conn, df):
    curs = conn.cursor()

    query = """
        INSERT OR IGNORE INTO tPlayerInfo (
            player_name, country, designation, rank_type, rank_value, 
            tournament_key, acceptancelist_number, acceptancelist_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
    
    for row in df.itertuples(index=False, name=None):
        curs.execute(query, row)
    conn.commit()
    curs.close()

def get_or_create_location_id(conn, city, country, lat=None, lon=None):
    """
    Returns the location_id for (city, country). 
    If it doesn’t exist, inserts it and returns the new id.
    """

    # 1️⃣ Check if location already exists
    result = conn.execute("""
        SELECT location_id
        FROM tLocations
        WHERE city = ? AND country = ?;
    """, (city, country)).fetchone()

    if result:
        return result[0]  # reuse existing id

    # 2️⃣ If not found, compute next location_id manually
    max_id = conn.execute("SELECT MAX(location_id) FROM tLocations;").fetchone()[0]
    new_id = (max_id or 0) + 1

    # 3️⃣ Insert new location record
    conn.execute("""
        INSERT INTO tLocations (location_id, city, country, latitude, longitude)
        VALUES (?, ?, ?, ?, ?);
    """, (new_id, city, country, lat, lon))
    conn.commit()

    print(f"✅ Added new location {city}, {country} with ID {new_id}")
    return new_id


conn = sqlite3.connect('itf_tournaments.db')
curs = conn.cursor()
curs.execute("PRAGMA foreign_keys=ON;")
def itf_scraper(desired_date):
    path = 'chromedriver.exe'
    service = Service(executable_path=path)
    driver = webdriver.Chrome(service=service)
    wait = WebDriverWait(driver, 30)
    counter = 0
    conn = sqlite3.connect('itf_tournaments.db')
    curs = conn.cursor()
    curs.execute("PRAGMA foreign_keys=ON;")

    #print("Enter tournament start date (e.g. '12 Jan'):")
    #sys.stdout.flush()
    #desired_date = sys.stdin.readline().strip()

    driver.get("https://www.itftennis.com/en/tournament-calendar/mens-world-tennis-tour-calendar/")

    # Click accept cookies
    #cookies_click = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Consent']")))
    #cookies_click.click()
    
    websites = get_tournament_links_by_date(driver, desired_date)

    filtered_websites = []

    for website in websites:
        tournament_key = website.rstrip("/").split("/")[-1]

        if tournament_exists(conn, tournament_key):
            print(f"⏭️ Skipping already-scraped tournament: {tournament_key}")
            continue

        filtered_websites.append(website)

    websites = filtered_websites


    for website in websites:
        tourney_key = website.split('/')[-2]

        website_draw = website + 'draws-and-results/'
        website_al = website + 'acceptance-list/'

        tournament_part = website.split('/')[-5]
        formatted_name = tournament_part.replace('-', ' ').title()

        driver.get(website)

        qualy_size = int(driver.find_element(By.XPATH, "//*[contains(text(), 'Singles qualifying')]").text[-2:])
        driver.get(website_draw)


        driver.execute_script("window.scrollBy(0, 700);")
        time.sleep(0.8)
        for attempt in range(3):
            try:
                dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//div[contains(@class, 'css-j1esxd-singleValue')])[2]")))
                dropdown.click()
                break  # Success, exit loop
            except (StaleElementReferenceException, ElementClickInterceptedException):
                print("Dropdown not clickable or stale, refreshing and retrying...")
                driver.get(website_draw)
                time.sleep(2)
                driver.execute_script("window.scrollBy(0, 600);")
                time.sleep(0.8)
        else:
            print("Failed to click dropdown after retrying.")
        #dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//div[contains(@class, 'css-j1esxd-singleValue')])[2]")))
        #dropdown.click()
        qualifying_option = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Qualifying Draw']")))
        qualifying_option.click()

        time.sleep(0.5)
                
        player_l = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "drawsheet-widget__last-name")))
        player_last = []
        for lplayer in player_l:
            try:
                player_last.append(lplayer.text)
            except StaleElementReferenceException:
                break

        player_f = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "drawsheet-widget__first-name")))
        player_first = []
        for fplayer in player_f:
            try:
                player_first.append(fplayer.text)
            except StaleElementReferenceException:
                break
        
        
        countries = driver.find_elements(By.XPATH, "//span[contains(@class, 'drawsheet-widget__nationality')]")
        country_names = [country.text for country in countries]

        seen = set()
        full_names = [f"{first} {last}" for first, last in zip(player_first, player_last)
                    if f"{first} {last}" not in seen and not seen.add(f"{first} {last}")]
        
        parent_containers = driver.find_elements(By.XPATH, "//div[contains(@class, 'drawsheet-round-container is-first-round carousel__animation--drawsheet-enter-done')]")
        walkovers = 0
        for parent in parent_containers:
            walkovers += len(parent.find_elements(By.CLASS_NAME, "drawsheet-widget__alert-status-text"))
        
        byes = qualy_size - len(full_names) + walkovers

        surface_info = driver.find_element(By.ID, "ga__tournament-surface").text
        prize_money = int(driver.find_element(By.XPATH, "//span[contains(@class, 'tournament-hero__value') and contains(text(), '$')]").text[1:])
        date = driver.find_element(By.ID, "ga__tournament-dates").text
        host_country = driver.find_element(By.ID, "ga__tournament-host-nation").text.upper()

        city = " ".join(website.split('/')[-5].split('-')[1:]).upper()
        points = int(website.split('/')[-5].split('-')[0][1:3])


        start_year = website.split('/')[-2].split('-')[-2]
        date_started = date.split(' - ')[0]
        date_started = date_started + ' ' + start_year
        date_ended = date.split(' - ')[1]
        surface = surface_info.split(' - ')[0]

        if surface_info.split(' - ')[1] == 'O':
            in_out = 'Outdoor'
        else:
            in_out = 'Indoor'
        
        # Check if tournament city, country already exists elswhere, if so use that location_id, if not then increment one above the highest existing one
        location_id = get_or_create_location_id(conn, city, host_country)

        tournament_data = (tourney_key, city, host_country, points, prize_money, 
                           date_started, date_ended, qualy_size, byes, surface, in_out, location_id)
        

        designation_list = []
        counter = 0
        for player in player_l:
            try:
                if player.find_element(By.XPATH, "following-sibling::span"):
                    designation_span = player.find_element(By.XPATH, "following-sibling::span")
                    designation = designation_span.text.strip()
                    designation_list.append(designation)
            except:
                designation_list.append('DA')
            counter += 1
            if counter >= len(full_names):
                break



        driver.get(website_al)
        #time.sleep(30)
        tables = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "acceptance-list")))
        columns = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "acceptance-list__title-default")))
        column_names = [column_name.text for column_name in columns]
        final_columns = []
        [final_columns.append(column) for column in column_names if column not in final_columns]
        final_columns.pop(0)
        final_columns.pop()
        final_columns.insert(0, 'PLAYER')
        final_columns.append('PRIORITY')



        dataframes = []

        if len(tables)==4:
            # There's no Junior reserved
            for i in range(3): 
                table = tables[i]
                df = extract_table_data(table)
                dataframes.append(df) 
        if len(tables)==5:
            # There IS Junior reserved
            for i in range(1, 4): 
                table = tables[i]
                df = extract_table_data(table)
                dataframes.append(df)

        if dataframes:
            cleaned_dfs = []
            for d_f in dataframes:
                d_f = d_f.drop(d_f.columns[[0, -1]], axis=1)
                d_f = d_f.drop(d_f.index[0]).reset_index(drop=True)
                d_f.columns = final_columns
                d_f['COUNTRY'] = d_f['PLAYER'].apply(lambda x: x[:3] if '\n' in x else 'N/A')
                d_f['PLAYER'] = d_f['PLAYER'].apply(lambda x: x[3:] if '\n' in x else x).str.replace('\n', '')
                cleaned_dfs.append(d_f)
                
            if cleaned_dfs:
                main_draw_al = cleaned_dfs[0]
                qualy_al = cleaned_dfs[1]
                alternate_al = cleaned_dfs[2]
            else:
                print("Error: No cleaned dataframes were found.")
        else:
            print("Error: No tables were found or extracted.")



        #combined_al = pd.concat([main_draw_al, qualy_al, alternate_al], ignore_index=True)
        combined_al_no_m = pd.concat([qualy_al, alternate_al])

        players_in_qdraw = pd.DataFrame(list(zip(full_names, designation_list, country_names)))
        players_in_qdraw.columns = ['PLAYER', 'DESIGNATION', 'COUNTRY']

        acceptance_summary = combined_al_no_m.merge(players_in_qdraw, on='PLAYER', how='inner').drop(columns=['COUNTRY_y']).rename(columns={'COUNTRY_x':'COUNTRY'})
        acceptance_summary['WTN'] = acceptance_summary['WTN'].astype(str)
        acceptance_summary['ATP RANKING'] = acceptance_summary['ATP RANKING'].astype(str)
        acceptance_summary['ITF RANKING'] = acceptance_summary['ITF RANKING'].astype(str)
        acceptance_summary['NATIONAL RANKING'] = acceptance_summary['NATIONAL RANKING'].astype(str)




        if len(acceptance_summary) != len(players_in_qdraw):
            for name in players_in_qdraw['PLAYER']:
                if name not in list(acceptance_summary['PLAYER']):
                    temp_coun = players_in_qdraw.loc[players_in_qdraw['PLAYER'] == name, 'COUNTRY'].iloc[0]
                    temp_desg = players_in_qdraw.loc[players_in_qdraw['PLAYER'] == name, 'DESIGNATION'].iloc[0]
                    new_row = {'PLAYER': name, 'COUNTRY': temp_coun, 'PRIORITY': '1', 'DESIGNATION': temp_desg}
                    acceptance_summary.loc[len(acceptance_summary)] = new_row

        da_df = acceptance_summary[acceptance_summary['DESIGNATION'].str.contains('DA', na=False)].copy()
        last_direct_acc = da_df[da_df['ATP RANKING'].notna()].iloc[-1] if not da_df[da_df['ATP RANKING'].notna()].empty else None

        al_df = acceptance_summary[acceptance_summary['DESIGNATION'].str.contains(r'\(A\)', na=False)].copy()
        last_alt_acc = al_df.iloc[-1] if not al_df.empty else pd.Series([0])

        
        df_to_players = acceptance_summary[acceptance_summary['PLAYER'] != '(Available Slot)'].reset_index(drop=True)

        df_to_players['rank_type'] = df_to_players.apply(
            lambda row: 'ATP' if row['ATP RANKING'] not in ['', None] and not isinstance(row['ATP RANKING'], float) else
                'ITF' if row['ITF RANKING'] not in ['', None] and not isinstance(row['ITF RANKING'], float) else
                'WTN' if row['WTN'] not in ['-', '', None] and not isinstance(row['WTN'], float) else
                'NATIONAL' if row['NATIONAL RANKING'] not in ['', None] and not isinstance(row['NATIONAL RANKING'], float) else
                'NONE',
            axis=1
        )

        df_to_players['rank_value'] = df_to_players.apply(
            lambda row: row['ATP RANKING'] if row['rank_type'] == 'ATP' and pd.notna(row['ATP RANKING']) else
                row['ITF RANKING'] if row['rank_type'] == 'ITF' and pd.notna(row['ITF RANKING']) else
                row['WTN'] if row['rank_type'] == 'WTN' and pd.notna(row['WTN']) else
                row['NATIONAL RANKING'] if row['rank_type'] == 'NATIONAL' and pd.notna(row['NATIONAL RANKING']) else 0,
            axis=1
        )
        

        df_to_players = df_to_players.drop(columns=['ATP RANKING', 'ITF RANKING', 'WTN', 'NATIONAL RANKING', 'PRIORITY'])
        df_to_players['tournament_key'] = tourney_key
        
        matching_indices = combined_al_no_m[combined_al_no_m['PLAYER'].isin(acceptance_summary['PLAYER'])].index
        adjusted = matching_indices+1

        if len(adjusted) < len(df_to_players):
            adjusted = list(adjusted) + [0] * (len(df_to_players) - len(adjusted))

        df_to_players['acceptancelist_number'] = adjusted
        
        status = []
        previous_value = -1  
        current_status = 'Qualifying'

        for val in df_to_players['acceptancelist_number']:
            if pd.isna(val):
                current_status = 'None'
            elif val < previous_value and current_status != 'None':
                current_status = 'Alternate'
            # Once set to Alternate, it won't go back to Qualifying
            elif current_status != 'Alternate':
                current_status = 'Qualifying'
            
            status.append(current_status)
            previous_value = val if not pd.isna(val) else previous_value

        df_to_players['acceptancelist_type'] = status

        if 'JUNIOR RANKING' in df_to_players.columns:
            df_to_players = df_to_players.drop(columns=['JUNIOR RANKING'])
        
        insert_tournament(conn, tournament_data)
        print(f'Succesfully added {tourney_key} to the database')

        insert_players(conn, df_to_players)
        print(f'Succesfully added players to database from {tourney_key}\n')

        print(f'Tournament: {formatted_name} - {date}')
        print(f'Qualifying draw size: {qualy_size}')
        print(f'Number of byes: {byes} \n')

        print('Last direct acceptance:')
        dir = get_player_ranking(last_direct_acc)
        print(f"{dir[0]} ({last_direct_acc['COUNTRY']}) - {dir[1]}")

        player_name = last_direct_acc['PLAYER']
        alternate_num = alternate_al.loc[alternate_al['PLAYER'] == player_name].index
        if alternate_num.empty:
            print(f'No alternates played. Alternate list was length {alternate_al.shape[0]}\n')
        else:
            print(f'He was alternate number {alternate_num[0]+1}/{alternate_al.shape[0]}\n')

       # last_alts =  acceptance_summary[(acceptance_summary['DESIGNATION'] != '(WC)') & (acceptance_summary.isna().any(axis=1))]
       # num_last_alts = last_alts.shape[0]
       
        if len(last_alt_acc) > 0 and last_alt_acc.iloc[0] != 0:
            print('Last on-site alternate (A) in:')
            alt = get_player_ranking(last_alt_acc)
            if alt[1] == 'ATP ranking: nan':
                print(f"{alt[0]} ({last_alt_acc['COUNTRY']}) - {alt[1]}")
                print(f'He was an unregistered on-site alternate\n')
            else:
                print(f"{alt[0]} ({last_alt_acc['COUNTRY']}) - {alt[1]}")

                player_name = last_alt_acc['PLAYER']
                alternate_num = alternate_al.loc[alternate_al['PLAYER'] == player_name].index
                print(f'He was alternate number {alternate_num[0]+1}/{alternate_al.shape[0]}')
                
        else:
            print('No on-site alternates (A) got in')

        
        print('---------------------------------------')
        
        
    conn.close()
    driver.quit()

    map_creation.insert_new_locs()

    return print("Scraping complete")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python itf_scraper.py '12 Jan'")
        sys.exit(1)

    desired_date = sys.argv[1]
    itf_scraper(desired_date)