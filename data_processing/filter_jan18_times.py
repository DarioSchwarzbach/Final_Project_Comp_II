import pandas as pd
import os

def filter_crime_data():
    in_path = '../data/chicago_violent_crimes_2010_present.csv'
    out_path = '../data/processed/filtered_jan18_crimes.csv'
    
    print(f"Loading data from {in_path}...")
    # Load dataset
    df = pd.read_csv(in_path)
    
    # Convert 'date' column to datetime objects
    print("Converting dates...")
    df['date'] = pd.to_datetime(df['date'])
    
    # Filter conditions:
    print("Filtering down to January 18th...")
    is_jan18 = (df['date'].dt.month == 1) & (df['date'].dt.day == 18)
    
    # Needs to be between 18:30 (6:30 PM) and 21:30 (9:30 PM)
    print("Applying time constraints (18:30 to 21:30)...")
    time_condition = (
        (df['date'].dt.hour > 18) | ((df['date'].dt.hour == 18) & (df['date'].dt.minute >= 30))
    ) & (
        (df['date'].dt.hour < 21) | ((df['date'].dt.hour == 21) & (df['date'].dt.minute <= 30))
    )
    
    # Apply filters
    filtered_df = df[is_jan18 & time_condition]
    
    # Create directory if it doesn't exist
    os.makedirs('data/processed', exist_ok=True)
    
    # Save the filtered results
    filtered_df.to_csv(out_path, index=False)
    
    print(f"Successfully saved {len(filtered_df)} records to {out_path}.")
    
if __name__ == "__main__":
    filter_crime_data()
