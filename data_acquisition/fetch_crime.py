import requests
import pandas as pd
import os
import time

def fetch_chicago_crime_data():
    # Chicago Data Portal API endpoint for crime data
    base_url = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
    
    # Query parameters
    # We want Violent Crimes from 2010 onwards
    # Note: 'date' in Socrata is stored as floating timestamp, e.g., '2010-01-01T00:00:00.000'
    where_clause = "date >= '2010-01-01T00:00:00' AND primary_type IN ('HOMICIDE', 'ASSAULT', 'BATTERY')"
    
    limit = 50000
    offset = 0
    all_data = []
    
    print(f"Fetching Chicago Crime data from 2010-present (Types: Homicide, Assault, Battery)")
    
    while True:
        params = {
            "$where": where_clause,
            "$limit": limit,
            "$offset": offset,
            "$order": "date DESC"
        }
        
        print(f"Fetching records {offset} to {offset + limit}...")
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                print("No more data to fetch.")
                break
                
            all_data.extend(data)
            print(f"Retrieved {len(data)} records in this batch.")
            
            if len(data) < limit:
                # Reached the end of the dataset
                break
                
            offset += limit
            # Sleep slightly to respect API limits
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            break
            
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Keep relevant columns and clean up
        relevant_columns = ['id', 'case_number', 'date', 'block', 'primary_type', 'description', 
                            'location_description', 'arrest', 'domestic', 'beat', 'district', 
                            'ward', 'community_area', 'latitude', 'longitude']
        
        # Keep columns that actually exist in the return payload
        cols_to_keep = [col for col in relevant_columns if col in df.columns]
        df = df[cols_to_keep]
        
        os.makedirs('data', exist_ok=True)
        out_path = 'data/chicago_violent_crimes_2010_present.csv'
        df.to_csv(out_path, index=False)
        print(f"Successfully saved {len(df)} crime records to {out_path}.")
    else:
        print("No data was retrieved.")

if __name__ == "__main__":
    fetch_chicago_crime_data()
