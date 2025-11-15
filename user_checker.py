import pandas as pd
import sqlite3
from datetime import datetime
pd.set_option('display.max_rows', None)
conn = sqlite3.connect('itf_tournaments.db')
curs = conn.cursor()
curs.execute("PRAGMA foreign_keys=ON;")



# Asking the user what their ranking is
def get_user_ranking():
    ranking_types = ["ATP", "ITF", "WTN", "NATIONAL"]
    for rtype in ranking_types:
        while True:
            answer = input(f"Do you have a {rtype} ranking? (y/n): ").strip().lower()
            if answer == "y":
                while True:
                    value = input(f"Enter your {rtype} ranking number: ")
                    if rtype == "WTN":
                        try:
                            float_value = float(value)
                            return rtype, float_value
                        except ValueError:
                            print("Please enter a valid number (integer or decimal) for WTN. Try again.")
                    else:
                        if value.isdigit():
                            return rtype, int(value)
                        else:
                            print("Please enter an integer ranking number. Try again.")
            elif answer == "n":
                break
            else:
                print("Please enter 'y' or 'n'. Try again.")
    print("No ranking provided.")
    return None, None


# Asking user for date input and validating it
def get_date():
    """Ask the user for a date in 'DD Mon YYYY' format (e.g., '01 Sep 2025'),
    validate it, and ensure tournaments exist for that date."""
    while True:
        date_input = input("Enter the tournament start date (e.g., 01 Sep 2025): ").strip()
        try:
            # Validate date format
            valid_date = datetime.strptime(date_input, "%d %b %Y")
            formatted_date = valid_date.strftime("%d %b %Y")

            # Check if there are tournaments for that date
            results = pd.read_sql("""
                SELECT *
                FROM tTournaments
                WHERE date_started = ?
            ;""", conn, params=(formatted_date,))

            if results.empty:
                print(f"No tournaments found starting on {formatted_date}. Please try another date.")
                continue  # Ask again

            # If results exist, return both the formatted date and the results if you need them
            return formatted_date

        except ValueError:
            print("Invalid format. Please enter the date as 'DD Mon YYYY' (e.g., 03 Sep 2025).")


# Getting last player accepted in each tournament (for given week)
def get_last_accepted_players(tournament_date):
    df = pd.read_sql("""
                        WITH NonByes AS (
                        SELECT tournament_key
                        FROM tTournaments
                        WHERE date_started = ?
                        AND qualybyes == '0'
                        ),

                        RankedPlayers AS (
                            SELECT *,
                                ROW_NUMBER() OVER (
                                    PARTITION BY tournament_key
                                    ORDER BY acceptancelist_type ASC, acceptancelist_number DESC
                                ) AS row_num
                            FROM tPlayerInfo
                            WHERE tournament_key IN (SELECT tournament_key FROM NonByes)
                            AND (designation = 'DA' OR designation = '(A)')
                        )
                        SELECT rank_type, rank_value, tournament_key
                        FROM RankedPlayers
                        WHERE row_num = 1
                        ORDER BY rank_type DESC, rank_value DESC


                        
                ;""", conn, params=(tournament_date,))
    return df


# Filtering tournaments based on user's ranking

rank_order = {"ATP": 4, "ITF": 3, "WTN": 2, "NATIONAL": 1, None: 0}

def normalize_rank_type(x):
    """Turn strings like 'NONE', 'null', '' or NaN into Python None; otherwise return uppercased string."""
    if pd.isna(x):
        return None
    s = str(x).strip().upper()
    if s in ("NONE", "NULL", "NAN", ""):
        return None
    return s

# Main function to run the user check

def run_user_check():
    rtype, rval = get_user_ranking()
    tournament_date = get_date()
    
    user_rank_type = normalize_rank_type(rtype)   # rtype is the user's rank type (e.g. "ATP", "NATIONAL", "NONE", or None)
    user_rank = rank_order.get(user_rank_type, 0)
    df = get_last_accepted_players(tournament_date)

    filtered = []
    filtered_n = []
    for idx, row in df.iterrows():
        tour_rank_type = normalize_rank_type(row.get('rank_type'))
        tour_rank_value = row.get('rank_value')
        tour_rank = rank_order.get(tour_rank_type, 0)

        # Case: user is NATIONAL -> include tournaments where last player was NATIONAL or None
        if user_rank_type == "NATIONAL":
            if tour_rank_type in ("NATIONAL", None):
                filtered.append(row)
            else:
                filtered_n.append(row)
            continue

        # Case: user is unranked / None -> include tournaments where last player was None
        if user_rank_type is None:
            if tour_rank_type is None:
                filtered.append(row)
            else:
                filtered_n.append(row)
            continue

        # Case: ATP / ITF / WTN -> keep original comparison logic
        if user_rank > tour_rank:
            filtered.append(row)
        elif user_rank == tour_rank:
            # compare rank values (rval is the user's numeric ranking value)
            try:
                if pd.isna(rval) or pd.isna(tour_rank_value):
                    # if either value is missing, skip this row (can't compare)
                    continue
                if float(rval) <= float(tour_rank_value):
                    filtered.append(row)
                else:
                    filtered_n.append(row)
            except Exception:
                # if conversion to float fails, skip this row
                continue
        else:
            # user_rank < tour_rank -> cannot get in
            filtered_n.append(row)
            continue


    # build DataFrames with the same columns as df so merges won't KeyError when lists are empty
    result_df = pd.DataFrame(filtered, columns=df.columns) if filtered else pd.DataFrame(columns=df.columns)
    result_n_df = pd.DataFrame(filtered_n, columns=df.columns) if filtered_n else pd.DataFrame(columns=df.columns)


    all_touraments = pd.read_sql("""
    SELECT tournament_key, city, country, date_started, qualysize, qualybyes
    FROM tTournaments
    WHERE date_started = ?
    """, conn, params=(tournament_date,))

    bye_tournaments = pd.read_sql("""
    SELECT tournament_key, city, country, date_started, qualysize, qualybyes
    FROM tTournaments
    WHERE date_started = ?
    AND qualybyes != '0'                             
    """, conn, params=(tournament_date,))

    combined = pd.merge(
        all_touraments,        # left DataFrame
        result_df,             # right DataFrame (your filtered tournaments)
        on='tournament_key',   # key column to match on
        how='inner'            # inner join = only tournaments in both
    )

    combined_n = pd.merge(
        all_touraments,      
        result_n_df,             
        on='tournament_key',   
        how='inner'            
    )

    combined_all = pd.concat([combined, bye_tournaments], ignore_index=True)

    print(f"Ranking type: {rtype}, Ranking value: {rval}")

    print("\nTournaments you would have gotten into:")
    print(combined_all)
    print("\nTournaments you would NOT have gotten into:")
    print(combined_n)

if __name__ == "__main__":
    run_user_check()