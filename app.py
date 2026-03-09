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
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['gameday'] = df['gameday'].astype(bool)

    # Calculate "Hours Since Start of Window" (0 to 6)
    # This aligns all 25 years perfectly, even if the 6-hour window crosses midnight.
    df['hour'] = df['date'].dt.hour
    if df['hour'].max() - df['hour'].min() > 12:  # True if window crosses midnight
        df['adj_hour'] = df['hour'].apply(lambda x: x + 24 if x < 12 else x)
    else:
        df['adj_hour'] = df['hour']

    min_hour = df['adj_hour'].min()
    df['relative_hour'] = df['adj_hour'] - min_hour

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
    xaxis_title="Hours Since Start of Window",
    yaxis_title="Number of Crimes",
    hovermode="x unified",
    xaxis=dict(tickmode='linear', dtick=1),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

st.plotly_chart(fig, width="stretch")

# --- 4. Heatmap ---
st.subheader("Crime Density Heatmap")

# Streamlit Layer Control Toggle
show_history = st.checkbox("Show Historical Baseline (Other Years)", value=False)


def create_heatmap(df_g, df_h, show_h):
    SOLDIER_FIELD_LAT = 41.8623
    SOLDIER_FIELD_LON = -87.6167

    layers = []

    # Base Historical Layer (Optional)
    if show_h:
        # Convert to pure Python dictionaries to bypass NumPy/Pandas JSON errors
        df_h_clean = df_h[['latitude', 'longitude']].dropna().to_dict(orient='records')

        layers.append(pdk.Layer(
            "HeatmapLayer",
            data=df_h_clean,
            get_position=["longitude", "latitude"],
            get_weight=1,
            radiusPixels=50,
            opacity=0.3,
            colorRange=[[237, 248, 251], [191, 211, 230], [158, 188, 218], [140, 150, 198], [136, 86, 167]]
        ))

    # Primary Game Day Layer
    # Convert to pure Python dictionaries
    df_g_clean = df_g[['latitude', 'longitude']].dropna().to_dict(orient='records')

    layers.append(pdk.Layer(
        "HeatmapLayer",
        data=df_g_clean,
        get_position=["longitude", "latitude"],
        get_weight=1,
        radiusPixels=50,
        opacity=0.8,
    ))

    # Soldier Field Marker
    # Use a raw Python list of dicts instead of pd.DataFrame
    stadium_data = [{"lat": SOLDIER_FIELD_LAT, "lon": SOLDIER_FIELD_LON}]

    layers.append(pdk.Layer(
        "ScatterplotLayer",
        data=stadium_data,
        get_position=["lon", "lat"],
        get_color=[255, 100, 0, 200],
        get_radius=800,
    ))

    view_state = pdk.ViewState(
        longitude=SOLDIER_FIELD_LON,
        latitude=SOLDIER_FIELD_LAT,
        zoom=10.5,
        pitch=0,
    )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={"text": "Crime Density"}
    )
    return deck


# Render the pydeck chart with the toggle state passed in
st.pydeck_chart(create_heatmap(df_game, df_history, show_history))