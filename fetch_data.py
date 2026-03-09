import nflreadpy as nfl
import polars as pl
import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta


def fetch_data():
    years = list(range(2001, 2027))

    # ---------------------------------------------------------
    # 1. Fetch and Prepare Bears Data
    # ---------------------------------------------------------
    print(f"Fetching NFL schedules for years: {years}")
    schedules = nfl.load_schedules(years)

    # Filter for Chicago Bears games (home or away)
    bears_games = schedules.filter((pl.col("home_team") == "CHI") | (pl.col("away_team") == "CHI"))

    # Keep relevant columns
    cols_to_keep = [
        'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime',
        'away_team', 'away_score', 'home_team', 'home_score', "location", 'result', 'total'
    ]
    bears_games = bears_games.select(cols_to_keep)  # .select() is safer in Polars than bracket notation

    # Determine games where Bears won
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

    os.makedirs('data_acquisition/data', exist_ok=True)
    out_path_nfl = 'data/bears_games_2001_2025.csv'
    bears_games.write_csv(out_path_nfl)
    print(f"Saved Bears data to {out_path_nfl} ({len(bears_games)} games found).\n")

    # ---------------------------------------------------------
    # 2. Process non-REG games for Crime Data
    # ---------------------------------------------------------
    non_reg_games = bears_games.filter(pl.col("game_type") != "REG")
    print(f"Found {len(non_reg_games)} non-regular season games. Fetching crime data...")

    base_url = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"

    # Convert to Python dicts for row-by-row processing
    games_list = non_reg_games.to_dicts()

    for game in games_list:
        gameday = game['gameday']
        gametime = game['gametime']

        # Skip if either is missing
        if not gameday or not gametime:
            print(f"Skipping game {game['game_id']} due to missing date or time.")
            continue

        # Parse the datetime. Handle both HH:MM and HH:MM:SS formats just in case.
        try:
            base_dt = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M")
        except ValueError:
            base_dt = datetime.strptime(f"{gameday} {gametime}", "%Y-%m-%d %H:%M:%S")

        game_month = base_dt.month
        game_day = base_dt.day
        game_hour = base_dt.hour
        game_minute = base_dt.minute

        # Build the exact time windows across ALL years
        conditions = []
        for y in years:
            try:
                # This will raise a ValueError if it's Feb 29 on a non-leap year
                target_dt = datetime(year=y, month=game_month, day=game_day, hour=game_hour, minute=game_minute)
            except ValueError:
                # Skip invalid leap year dates
                continue

            # We want a time window 3 hours before and 3 hours after a game with 3 hours avg game time.
            start_dt = target_dt - timedelta(hours=3)
            end_dt = target_dt + timedelta(hours=6)

            # Format to Socrata API standard
            start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

            conditions.append(f"(date >= '{start_str}' AND date <= '{end_str}')")

        # Combine all yearly time windows into one big API query for this game
        where_clause = " OR ".join(conditions)

        # ---------------------------------------------------------
        # 3. Fetch Crime Data from API
        # ---------------------------------------------------------
        limit = 50000
        offset = 0
        all_data = []

        print(f"Fetching crimes for {gameday} (Window: {gametime} + 6 hours/ - 3 hours across all years)...")

        while True:
            params = {
                "$where": where_clause,
                "$limit": limit,
                "$offset": offset,
                "$order": "date DESC"
            }

            try:
                response = requests.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()

                if not data:
                    break

                all_data.extend(data)

                if len(data) < limit:
                    break

                offset += limit
                time.sleep(1)  # Be nice to the API

            except requests.exceptions.RequestException as e:
                print(f"Error fetching crime data for {gameday}: {e}")
                break

        # Save Crime Data
        if all_data:
            df_crimes = pd.DataFrame(all_data)

            relevant_columns = [
                'id', 'case_number', 'date', 'block', 'primary_type', 'description',
                'location_description', 'arrest', 'domestic', 'beat', 'district',
                'ward', 'community_area', 'latitude', 'longitude'
            ]
            cols_to_keep = [col for col in relevant_columns if col in df_crimes.columns]
            df_crimes = df_crimes[cols_to_keep]

            # Add the 'home_game' boolean flag
            is_home = (game['home_team'] == 'CHI') and (game['location'] == 'Home')
            df_crimes['home_game'] = is_home

            # Add the 'gameday' boolean flag (True only for the specific year/month/day of the game)
            df_crimes['gameday'] = df_crimes['date'].astype(str).str.startswith(gameday)

            out_path_crime = f'data/crimes_for_game_{gameday}.csv'
            df_crimes.to_csv(out_path_crime, index=False)
            print(f"  -> Successfully saved {len(df_crimes)} crime records to {out_path_crime}.")
        else:
            print(f"  -> No crime data found for {gameday} time windows.")


if __name__ == "__main__":
    fetch_data()