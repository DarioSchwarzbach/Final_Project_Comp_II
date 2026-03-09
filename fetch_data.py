import nflreadpy as nfl
import polars as pl
import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta

# ==========================================
# 1. SETUP & CONSTANTS
# ==========================================
YEARS_TO_FETCH = list(range(2001, 2027))
CHICAGO_API_URL = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
DATA_DIR = "data"

CRIME_COLUMNS = [
    'id', 'case_number', 'date', 'block', 'primary_type', 'description',
    'location_description', 'arrest', 'domestic', 'beat', 'district',
    'ward', 'community_area', 'latitude', 'longitude'
]


# ==========================================
# 2. DATA EXTRACTION FUNCTIONS
# ==========================================
def fetch_bears_schedule(years: list) -> pl.DataFrame:
    """
    Fetches historical NFL schedules and filters for Chicago Bears games.
    Calculates whether the Bears won each game based on home/away status.

    Args:
        years (list): List of integer years to fetch data for.

    Returns:
        pl.DataFrame: A Polars DataFrame containing filtered game data.
    """
    print(f"Fetching NFL schedules for years: {years[0]} to {years[-1]}")
    schedules = nfl.load_schedules(years)

    # Filter for games involving the Bears
    bears_games = schedules.filter((pl.col("home_team") == "CHI") | (pl.col("away_team") == "CHI"))

    cols_to_keep = [
        'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime',
        'away_team', 'away_score', 'home_team', 'home_score', "location", 'result', 'total'
    ]
    bears_games = bears_games.select(cols_to_keep)

    # Determine games where Bears won (1.0 = Win, 0.0 = Loss, 0.5 = Tie)
    bears_games = bears_games.with_columns(
        pl.when(pl.col("home_score").is_null() | pl.col("away_score").is_null())
        .then(None)
        .when(pl.col("home_team") == "CHI")
        .then(
            pl.when(pl.col("home_score") > pl.col("away_score")).then(1.0)
            .when(pl.col("home_score") < pl.col("away_score")).then(0.0)
            .otherwise(0.5)
        )
        .otherwise(
            pl.when(pl.col("away_score") > pl.col("home_score")).then(1.0)
            .when(pl.col("away_score") < pl.col("home_score")).then(0.0)
            .otherwise(0.5)
        )
        .alias("bears_win")
    )
    return bears_games


def build_socrata_query(gameday: str, gametime: str, years: list) -> str:
    """
    Constructs a SoQL (Socrata Query Language) WHERE clause to fetch crimes
    occurring exactly within a 9-hour window across multiple historical years.

    Args:
        gameday (str): The date of the game (YYYY-MM-DD).
        gametime (str): The kickoff time (HH:MM or HH:MM:SS).
        years (list): List of historical years to build the baseline against.

    Returns:
        str: A concatenated SQL-like WHERE clause.
    """
    # Standardize time parsing
    try:
        base_dt = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M")
    except ValueError:
        base_dt = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M:%S")

    conditions = []

    # Generate the 9-hour window for every year in our dataset
    for y in years:
        try:
            # Reconstruct the target date for the historical year
            target_dt = datetime(
                year=y, month=base_dt.month, day=base_dt.day,
                hour=base_dt.hour, minute=base_dt.minute
            )
        except ValueError:
            # Automatically skips leap-year days (Feb 29) on non-leap years
            continue

        # Window: 3 hours pre-game, 3 hours game time, 3 hours post-game
        start_dt = target_dt - timedelta(hours=3)
        end_dt = target_dt + timedelta(hours=6)

        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

        conditions.append(f"(date >= '{start_str}' AND date <= '{end_str}')")

    return " OR ".join(conditions)


def fetch_crimes_from_api(where_clause: str) -> list:
    """
    Paginates through the Chicago Data Portal API using an offset/limit strategy
    to bypass strict data limits per request.

    Args:
        where_clause (str): The SoQL string specifying the time windows.

    Returns:
        list: A list of dictionaries containing raw crime records.
    """
    limit = 50000
    offset = 0
    all_data = []

    #
    while True:
        params = {
            "$where": where_clause,
            "$limit": limit,
            "$offset": offset,
            "$order": "date DESC"
        }

        try:
            response = requests.get(CHICAGO_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            all_data.extend(data)

            # If the API returned fewer records than the limit, we've hit the end
            if len(data) < limit:
                break

            offset += limit
            time.sleep(1)  # Throttle requests to respect API rate limits

        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            break

    return all_data


# ==========================================
# 3. DATA PROCESSING & ORCHESTRATION
# ==========================================
def process_and_save_crimes(raw_crimes: list, game_metadata: dict, output_path: str):
    """
    Cleans raw API data, attaches game-specific boolean flags, and saves to CSV.

    Args:
        raw_crimes (list): Raw list of dicts from the API.
        game_metadata (dict): Metadata about the game (teams, location, date).
        output_path (str): Filepath to save the final CSV.
    """
    if not raw_crimes:
        print(f"  -> No crime data found for {game_metadata['gameday']}.")
        return

    df_crimes = pd.DataFrame(raw_crimes)

    # Filter columns safely
    cols_to_keep = [col for col in CRIME_COLUMNS if col in df_crimes.columns]
    df_crimes = df_crimes[cols_to_keep]

    # Attach contextual boolean flags for the Streamlit app
    is_home = (game_metadata['home_team'] == 'CHI') and (game_metadata['location'] == 'Home')
    df_crimes['home_game'] = is_home

    # Identify which crimes actually happened on the real game day versus historical baseline days
    df_crimes['gameday'] = df_crimes['date'].astype(str).str.startswith(game_metadata['gameday'])

    df_crimes.to_csv(output_path, index=False)
    print(f"  -> Successfully saved {len(df_crimes)} crime records to {output_path}.")


def main():
    """Main orchestrator function for the Extract Tranform Load pipeline."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Fetch Bears Data
    bears_games = fetch_bears_schedule(YEARS_TO_FETCH)
    out_path_nfl = os.path.join(DATA_DIR, 'bears_games_2001_2025.csv')
    bears_games.write_csv(out_path_nfl)
    print(f"Saved NFL schedule to {out_path_nfl} ({len(bears_games)} games found).\n")

    # 2. Filter target games (e.g., non-regular season for your current logic)
    target_games = bears_games.filter(pl.col("game_type") != "REG")
    print(f"Found {len(target_games)} target games. Fetching crime data...")

    # 3. Iterate through games and fetch crime baselines
    games_list = target_games.to_dicts()

    for game in games_list:
        gameday, gametime = game['gameday'], game['gametime']

        if not gameday or not gametime:
            print(f"Skipping game {game['game_id']} due to missing datetime.")
            continue

        print(f"Fetching crimes for {gameday} (Window: {gametime} +/- hours across all years)...")

        # Build Query -> Fetch -> Clean -> Save
        where_clause = build_socrata_query(gameday, gametime, YEARS_TO_FETCH)
        raw_crime_data = fetch_crimes_from_api(where_clause)

        out_path_crime = os.path.join(DATA_DIR, f'crimes_for_game_{gameday}.csv')
        process_and_save_crimes(raw_crime_data, game, out_path_crime)


if __name__ == "__main__":
    main()