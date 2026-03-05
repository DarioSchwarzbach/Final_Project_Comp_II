import json
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
import undetected_chromedriver as uc

def fetch_pfr_data():
    url = "https://www.pro-football-reference.com/teams/chi/1920-2025/index.htm"
    print(f"Scraping Pro-Football-Reference using Selenium: {url}")
    
    # Setup headless Chrome
    
    chrome_options = uc.ChromeOptions()
    #chrome_options.headless = True
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    driver = uc.Chrome(options=chrome_options, version_main=145)
    
    try:
        driver.get(url)
        time.sleep(10) # Give cloudflare more time
        html = driver.page_source
        print(f"Page title: {driver.title}")
        with open('debug_pfr.html', 'w') as f:
            f.write(html)
    finally:
        driver.quit()

    soup = BeautifulSoup(html, 'html.parser')
    
    # Pro-football-reference heavily comments out tables to delay loading them. 
    # But the main franchise table "franchise_years" is usually not commented out.
    table = soup.find('table', {'id': 'team_index'})
    
    if not table:
        print("Could not find table 'team_index'. Looking in comments...")
        import re
        comments = soup.find_all(string=lambda text: isinstance(text, str) and 'id="team_index"' in text)
        if comments:
            table_html = re.search(r'<table.*</table>', comments[0], re.DOTALL)
            if table_html:
                table = BeautifulSoup(table_html.group(0), 'html.parser').find('table')
                
    if not table:
        print("Failed to find the data table entirely.")
        return

    # Extract headers
    thead = table.find('thead')
    # PFR has multiple header rows usually, the sub-headers are in the second tr
    headers = []
    header_rows = thead.find_all('tr')
    
    # Sometimes first row is groups (like "Offensive Stats", "Defensive Stats"), second is actual cols
    if len(header_rows) > 1:
        # We will parse the exact column labels from the last header row or build composite headers
        th_elements = header_rows[-1].find_all('th')
    else:
        th_elements = header_rows[0].find_all('th')
        
    for th in th_elements:
        title = th.get('data-stat') or th.text.strip()
        headers.append(title)
        
    print(f"Headers found: {headers}")

    # Extract rows
    tbody = table.find('tbody')
    rows = tbody.find_all('tr')
    
    data = []
    years_to_collect = [str(y) for y in range(1920, 2026)]
    
    for row in rows:
        if row.get('class') and 'thead' in row.get('class'):
            continue # skip intermediate header rows
            
        th = row.find('th') # The year is typically in a th
        if not th:
            continue
            
        year = th.text.strip()
        if year not in years_to_collect:
            continue
            
        row_data = {"Year": year}
        tds = row.find_all('td')
        
        # Merge th + tds to zip with headers
        all_cells = [th] + tds
        
        for header, cell in zip(headers, all_cells):
            if header == 'year_id':
                continue # we already took year
            val = cell.text.strip()
            row_data[header] = val
        
        data.append(row_data)

    # Save to JSON as requested
    import os
    os.makedirs('data', exist_ok=True)
    json_path = 'data/bears_pfr_stats.json'
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Saved {len(data)} records to {json_path}")
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    csv_path = 'data/bears_pfr_stats.csv'
    df.to_csv(csv_path, index=False)
    print(f"Saved DataFrame to {csv_path}")
    print("Sample:\n", df.head(2))

if __name__ == "__main__":
    fetch_pfr_data()
