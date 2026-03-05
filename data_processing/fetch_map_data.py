import pandas as pd
import requests
import time

def get_location_info_osm(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
    headers = {'User-Agent': 'AntigravityCoder/1.0'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'name' in data and data['name']:
                return data['name'] + ' (' + data.get('display_name', '').split(',')[0] + ')'
            return data.get('display_name', 'Unknown Location').split(',')[0] + ', ' + data.get('display_name', 'Unknown Location').split(',')[1] if ',' in data.get('display_name', '') else data.get('display_name', 'Unknown Location')
    except Exception as e:
        pass
    return "Unknown"

df = pd.read_csv('data/processed/filtered_jan18_crimes.csv').sort_values(by='date', ascending=False).head(34)
results = []

print("Fetching location data... This will take ~35 seconds.")
for idx, row in df.iterrows():
    lat = row['latitude']
    lon = row['longitude']
    desc = row['description']
    block = row['block']
    loc_desc = row['location_description']
    
    if pd.isna(lat) or pd.isna(lon):
        place = "No Coordinates"
    else:
        place = get_location_info_osm(lat, lon)
        time.sleep(1.1) # Be nice to Nominatim
        
    results.append(f"- **{block}**: {place} (Type: {loc_desc} - {desc})")

output = "\n".join(results)
with open('data/processed/heatmap_locations.txt', 'w') as f:
    f.write(output)
print("Finished!")
