import pandas as pd
import numpy as np
import os

# Soldier field coordinates
SOLDIER_FIELD_LAT = 41.8623
SOLDIER_FIELD_LON = -87.6167

# Haversine formula to calculate distance between two lat/lon points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    distance = R * c
    return distance # in km

def process_data():
    print("Loading raw datasets...")
    bears_df = pd.read_csv('data/bears_games_2010_2024.csv')
    try:
        crime_df = pd.read_csv('data/chicago_violent_crimes_2010_present.csv')
    except FileNotFoundError:
        print("Waiting on crime data download to finish...")
        return
        
    print("Cleaning Bears data dates...")
    bears_df['gameday'] = pd.to_datetime(bears_df['gameday'])
    
    print("Cleaning Crime data dates...")
    crime_df['date_parsed'] = pd.to_datetime(crime_df['date'])
    crime_df['date_only'] = crime_df['date_parsed'].dt.date
    crime_df['date_only'] = pd.to_datetime(crime_df['date_only'])
    
    print("Calculating distances to Soldier Field...")
    # Drop rows without lat/lon
    crime_df = crime_df.dropna(subset=['latitude', 'longitude'])
    crime_df['dist_to_stadium_km'] = haversine(
        crime_df['latitude'], crime_df['longitude'], 
        SOLDIER_FIELD_LAT, SOLDIER_FIELD_LON
    )
    
    print("Building Daily Aggregates...")
    # Count daily crimes
    daily_crimes = crime_df.groupby('date_only').size().reset_index(name='total_violent_crimes')
    
    # Crimes within 3km of soldier field
    stadium_crimes = crime_df[crime_df['dist_to_stadium_km'] <= 3.0]
    daily_stadium_crimes = stadium_crimes.groupby('date_only').size().reset_index(name='stadium_crimes')
    
    daily_merged = pd.merge(daily_crimes, daily_stadium_crimes, on='date_only', how='left')
    daily_merged['stadium_crimes'] = daily_merged['stadium_crimes'].fillna(0)
    
    # Merge with Bears schedule (Outer join to keep all days, then we can flag game days)
    final_daily = pd.merge(
        daily_merged, 
        bears_df[['gameday', 'bears_win', 'home_team', 'away_team', 'result']], 
        left_on='date_only', 
        right_on='gameday', 
        how='left'
    )
    
    final_daily['is_game_day'] = ~final_daily['gameday'].isna()
    
    os.makedirs('data/processed', exist_ok=True)
    
    print("Building Seasonal Aggregates...")
    # Add year and month attributes to the daily set for grouping
    final_daily['year'] = final_daily['date_only'].dt.year
    final_daily['month'] = final_daily['date_only'].dt.month
    
    # Save daily
    final_daily.to_csv('data/processed/daily_crime_with_bears.csv', index=False)
    
    # Group by NFL season (Roughly Sept-Jan). For simplicity, let's look at Year over Year mapping
    # Getting stadium crimes from the daily dataset
    seasonal_old = final_daily.groupby('year').agg({
        'stadium_crimes': 'sum'
    }).reset_index()

    print("Loading yearly aggregates from new chicago crimes dataset...")
    crime_totals_df = pd.read_csv('data/chicago_crimes_01_1985_to_03_2026.csv')
    # Melt dataset to get year/month rows
    crime_totals_long = crime_totals_df.melt(id_vars='Series', var_name='month_year', value_name='total_crimes')
    # Extract year
    crime_totals_long['year'] = crime_totals_long['month_year'].str.split('-').str[1].astype(int)
    # Convert total_crimes to numeric, filling NaNs with 0
    crime_totals_long['total_crimes'] = pd.to_numeric(crime_totals_long['total_crimes'], errors='coerce').fillna(0)
    
    new_yearly = crime_totals_long.groupby('year')['total_crimes'].sum().reset_index()
    new_yearly.rename(columns={'total_crimes': 'total_violent_crimes'}, inplace=True)
    
    # Merge new totals with stadium crimes
    seasonal_merged = pd.merge(new_yearly, seasonal_old, on='year', how='left')
    seasonal_merged['stadium_crimes'] = seasonal_merged['stadium_crimes'].fillna(0)
    
    # Load and merge the newly scraped Pro-Football-Reference JSON/CSV data
    pfr_df = pd.read_csv('data/bears_pfr_stats.csv')
    pfr_df['Year'] = pfr_df['Year'].astype(int)
    
    seasonal = pd.merge(seasonal_merged, pfr_df, left_on='year', right_on='Year', how='right')
    # Since right join preserves 'Year' from PFR, let's make sure our 'year' column is populated for the dashboard
    seasonal['year'] = seasonal['Year']
    
    seasonal.to_csv('data/processed/seasonal_aggregates.csv', index=False)
    
    # Save a filtered version of the raw crime dataset only containing game-days vs nearby days for heatmap
    # Get all game dates
    game_dates = bears_df['gameday'].dt.date.tolist()
    
    # Filter crime coordinates for game days
    heatmap_data = crime_df[crime_df['date_only'].dt.date.isin(game_dates)][['latitude', 'longitude', 'primary_type', 'dist_to_stadium_km']]
    heatmap_data.to_csv('data/processed/heatmap_game_days.csv', index=False)
    
    print("Data processing complete. Processed files saved to data/processed/")

if __name__ == "__main__":
    process_data()
