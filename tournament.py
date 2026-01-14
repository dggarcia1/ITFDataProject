import pandas as pd
import sqlite3

DB_PATH = "itf_tournaments.db"

def main():
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON;")

    # Ask user for tournament key
    tournament_key = input("Enter tournament key: ").strip()

    query = """
        SELECT *
        FROM tPlayerInfo
        WHERE tournament_key = ?
    """

    df = pd.read_sql_query(query, conn, params=(tournament_key,))

    if df.empty:
        print(f"\nNo players found for tournament_key = {tournament_key}")
    else:
        # Modify acceptancelist_number based on acceptancelist_type
        if {"acceptancelist_type", "acceptancelist_number"}.issubset(df.columns):
            def format_acceptance(row):
                if row["acceptancelist_type"] == "Qualifying":
                    return f"{row['acceptancelist_number']} - Q"
                elif row["acceptancelist_type"] == "Alternate":
                    return f"{row['acceptancelist_number']} - A"
                else:
                    return row["acceptancelist_number"]

            df["acceptancelist_number"] = df.apply(format_acceptance, axis=1)

            # Drop acceptancelist_type column
            df = df.drop(columns=["acceptancelist_type"])

        print(f"\nPlayers in tournament {tournament_key}:\n")
        print(df.to_string(index=False))

    conn.close()


if __name__ == "__main__":
    main()
