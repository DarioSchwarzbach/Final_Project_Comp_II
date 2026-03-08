import nflreadpy as nfl
import polars as pl
import os

def fetch_bears_data():
    years = list(range(2001, 2026))
    print(f"Fetching NFL schedules for years: {years}")
    
    # Import schedules
    schedules = nfl.load_schedules(years)
    # Filter for Chicago Bears games (home or away)
    bears_games = schedules.filter((pl.col("home_team") == "CHI") | (pl.col("away_team") == "CHI"))
    # Keep relevant columns
    cols_to_keep = [
        'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime', 
        'away_team', 'away_score', 'home_team', 'home_score', "location", 'result', 'total'
    ]
    bears_games = bears_games[cols_to_keep]

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

    # Save to data directory
    os.makedirs('data', exist_ok=True)
    out_path = 'data/bears_games_2001_2025.csv'
    bears_games.write_csv(out_path)
    print(f"Saved Bears data to {out_path} ({len(bears_games)} games found).")

if __name__ == "__main__":
    fetch_bears_data()
