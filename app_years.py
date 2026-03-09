import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import glob
import os

# --- Page Config ---
st.set_page_config(page_title="Bears Game Day Crime Explorer", layout="wide")

# --- 1. Load Available Game Days ---
@st.cache_data
def get_available_games():
    # Looks for files matching the pattern in the data folder
    files = glob.glob("data/crimes_for_game_*.csv")
    # Extract just the date part from the filename
    game_days = [os.path.basename(f).replace('crimes_for_game_', '').replace('.csv', '') for f in files]
    return sorted(game_days, reverse=True)

available_games = get_available_games()

if not available_games:
    st.error("No CSV files found in the 'data/' directory. Please run your fetch script first.")
    st.stop()

# --- Top Header & Controls ---
st.title("🏈 Chicago Bears: Game Day Crime Analysis")

top_col1, top_col2 = st.columns([1, 2])
with top_col1:
    selected_game = st.selectbox("Select a Game Day:", available_games)

# --- 2. Load Data for Selected Game ---
@st.cache_data
def load_game_data(gameday_str):
    path = f"data/crimes_for_game_{gameday_str}.csv"
    df = pd.read_csv(path)

    # 1. Convert the main date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['hour'] = df['date'].dt.hour
    df['gameday'] = df['gameday'].astype(bool)

    # If the difference between max and min hour is large, it's a midnight wrap-around.
    # (e.g., Start 10pm (22), End 7am (7). 22 - 7 = 15. 15 > 12 is True)
    if df['hour'].max() - df['hour'].min() > 12:
        df['adj_hour'] = df['hour'].apply(lambda h: h + 24 if h < 12 else h)
    else:
        df['adj_hour'] = df['hour']

    # The kickoff is always 3 hours after the start of our 9-hour fetch window
    kickoff_hour_adj = df['adj_hour'].min() + 3

    # Calculate the relative hour anchored at 0 for kickoff
    df['relative_hour'] = df['adj_hour'] - kickoff_hour_adj

    return df


df = load_game_data(selected_game)

# Split into actual game day vs historical baseline
df_game = df[df['gameday'] == True]
df_history = df[df['gameday'] == False]

# --- 3. Line Chart ---
st.subheader("Crime Volume: Game Day vs. Baseline")

# Group by year and relative hour to get crime counts
hourly_counts = df.groupby(['year', 'relative_hour']).size().reset_index(name='crimes')

game_year = int(selected_game.split('-')[0])

# Calculate historical average
historical_counts = hourly_counts[hourly_counts['year'] != game_year]
avg_historical = historical_counts.groupby('relative_hour')['crimes'].mean().reset_index()

fig = go.Figure()

# 1. Add individual historical years (low opacity)
for year in historical_counts['year'].unique():
    year_data = historical_counts[historical_counts['year'] == year]
    fig.add_trace(go.Scatter(
        x=year_data['relative_hour'],
        y=year_data['crimes'],
        mode='lines',
        line=dict(color='gray', width=1),
        opacity=0.25,
        name=str(year),
        showlegend=False,
        hoverinfo='skip'
    ))

# 2. Add the historical average line
fig.add_trace(go.Scatter(
    x=avg_historical['relative_hour'],
    y=avg_historical['crimes'],
    mode='lines+markers',
    line=dict(color='yellow', width=3, dash='dash'),
    name='Historical Avg'
))

# 3. Add the actual game day line
game_data = hourly_counts[hourly_counts['year'] == game_year]
fig.add_trace(go.Scatter(
    x=game_data['relative_hour'],
    y=game_data['crimes'],
    mode='lines+markers',
    line=dict(color='red', width=4),
    name=f'Game Day'
))

fig.update_layout(
    # Titles
    xaxis_title="Hours Relative to Kickoff",
    yaxis_title="Number of Crimes",

    # Interaction
    hovermode="x unified",

    # X-Axis specific settings
    xaxis=dict(
        tickmode='linear',
        dtick=1,
        range=[-3, 6]
    ),

    # Legend placement (moves it above the chart)
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

# Add vertical lines for Game Start and Game End
fig.add_vline(x=0, line_dash="dot", line_color="green", annotation_text="Kickoff")
fig.add_vline(x=3, line_dash="dot", line_color="orange", annotation_text="Game End")

st.plotly_chart(fig, width="stretch")

# --- 4. Heatmap ---
st.subheader("Crime Density Heatmap")

# 1. Get a sorted list of all available historical years
historical_years = sorted(df_history['year'].unique().tolist())

# 2. Use a multiselect widget for individual year toggling
selected_years = st.multiselect(
    "Select Historical Years to Overlay:",
    options=historical_years,
    default=[]  # Leave empty by default to prevent clutter
)


def create_heatmap(df_g, df_h, years_to_show):
    SOLDIER_FIELD_LAT = 41.8623
    SOLDIER_FIELD_LON = -87.6167

    layers = []

    # 3. Create a separate layer for EACH selected historical year
    for year in years_to_show:
        df_year = df_h[df_h['year'] == year]
        df_year_clean = df_year[['latitude', 'longitude']].dropna().to_dict(orient='records')

        if df_year_clean:
            layers.append(pdk.Layer(
                "HeatmapLayer",
                data=df_year_clean,
                get_position=["longitude", "latitude"],
                get_weight=1,
                radiusPixels=50,
                # opacity=0.3,  # Dimmer so it doesn't overpower the main game
                colorRange=[[237, 248, 251], [191, 211, 230], [158, 188, 218], [140, 150, 198], [136, 86, 167]],
                id=f"heatmap_historical_{year}"  # Unique ID for each year's layer
            ))

    # Primary Game Day Layer
    df_g_clean = df_g[['latitude', 'longitude']].dropna().to_dict(orient='records')

    layers.append(pdk.Layer(
        "HeatmapLayer",
        data=df_g_clean,
        get_position=["longitude", "latitude"],
        get_weight=1,
        radiusPixels=50,
        opacity=0.8,
        id="heatmap_gameday"
    ))

    # Soldier Field Marker
    stadium_data = [{"lat": SOLDIER_FIELD_LAT, "lon": SOLDIER_FIELD_LON}]

    layers.append(pdk.Layer(
        "ScatterplotLayer",
        data=stadium_data,
        get_position=["lon", "lat"],
        get_color=[255, 100, 0, 200],
        get_radius=800,
        id="stadium_marker"
    ))

    view_state = pdk.ViewState(
        longitude=SOLDIER_FIELD_LON,
        latitude=SOLDIER_FIELD_LAT,
        zoom=10.5,
        pitch=0,
    )

    r = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={"text": "Crime Density"}
    )
    return r


# Render the pydeck chart passing the selected years
st.pydeck_chart(create_heatmap(df_game, df_history, selected_years))