import nfl_data_py as nfl
import pandas as pd
import os

def fetch_bears_data():
    years = list(range(2010, 2025))
    print(f"Fetching NFL schedules for years: {years}")
    
    # Import schedules
    schedules = nfl.import_schedules(years)
    
    # Filter for Chicago Bears games (home or away)
    bears_games = schedules[(schedules['home_team'] == 'CHI') | (schedules['away_team'] == 'CHI')].copy()
    
    # Keep relevant columns
    cols_to_keep = [
        'game_id', 'season', 'game_type', 'week', 'gameday', 'weekday', 'gametime', 
        'away_team', 'away_score', 'home_team', 'home_score', 'result', 'total'
    ]
    bears_games = bears_games[cols_to_keep]
    
    # Determine if Bears won
    def bears_won(row):
        if pd.isna(row['home_score']) or pd.isna(row['away_score']):
            return None # Game hasn't happened or missing data
        
        if row['home_team'] == 'CHI':
            return 1 if row['home_score'] > row['away_score'] else (0 if row['home_score'] < row['away_score'] else 0.5)
        else:
            return 1 if row['away_score'] > row['home_score'] else (0 if row['away_score'] < row['home_score'] else 0.5)
            
    bears_games['bears_win'] = bears_games.apply(bears_won, axis=1)
    
    # Save to data directory
    os.makedirs('data', exist_ok=True)
    out_path = 'data/bears_games_2010_2024.csv'
    bears_games.to_csv(out_path, index=False)
    print(f"Saved Bears data to {out_path} ({len(bears_games)} games found).")

if __name__ == "__main__":
    fetch_bears_data()
