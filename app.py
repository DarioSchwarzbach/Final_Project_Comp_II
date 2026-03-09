import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import scipy.stats as stats
import glob
import os

# ==========================================
# 1. SETUP & CONSTANTS
# ==========================================
# Configure the browser tab title and set the app layout to stretch across the screen
st.set_page_config(page_title="Bears Game Day Crime Explorer", layout="wide")

# Coordinates for Soldier Field, used to center the heatmap and place the marker
SOLDIER_FIELD_LAT = 41.8623
SOLDIER_FIELD_LON = -87.6167


# ==========================================
# 2. DATA & STATISTICAL FUNCTIONS
# ==========================================
@st.cache_data
def get_available_games():
    """
    Scans the 'data/' directory for all generated CSV files and extracts the game dates.

    Returns:
        list: A reverse-chronological list of date strings (e.g., ['2023-09-10', '2022-09-11'])
              representing all available games.
    """
    files = glob.glob("data/crimes_for_game_*.csv")
    game_days = [
        os.path.basename(f).replace("crimes_for_game_", "").replace(".csv", "")
        for f in files
    ]
    return sorted(game_days, reverse=True)


@st.cache_data
def load_game_data(gameday_str):
    """
    Loads and preprocesses the crime data for a specific 9-hour window, standardizing the time
    so that kickoff is always mathematically anchored at hour 0.

    Args:
        gameday_str (str): The date of the game (e.g., '2023-09-10').

    Returns:
        pd.DataFrame: Preprocessed DataFrame with 'adj_hour' and 'relative_hour' columns.
    """
    path = f"data/crimes_for_game_{gameday_str}.csv"
    df = pd.read_csv(path)

    # Convert date strings to actual datetime objects for temporal math
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['hour'] = df['date'].dt.hour
    df['gameday'] = df['gameday'].astype(bool)

    # MIDNIGHT ROLLOVER LOGIC:
    # If a game starts late and ends the next morning, the hours jump from 23 to 0.
    # We check if the difference between the max and min hour in the 9-hour window > 12.
    # If true, we add 24 to the morning hours so the timeline remains linear (e.g., 22, 23, 24, 25).
    if df['hour'].max() - df['hour'].min() > 12:
        df['adj_hour'] = df['hour'].apply(lambda h: h + 24 if h < 12 else h)
    else:
        df["adj_hour"] = df["hour"]

    # The data fetching window always starts exactly 3 hours before kickoff.
    # Therefore, we find the absolute start of the window and add 3 to locate kickoff time.
    kickoff_hour_adj = df['adj_hour'].min() + 3

    # Subtract kickoff hour from every row so the game starts at '0' on the chart
    df['relative_hour'] = df['adj_hour'] - kickoff_hour_adj

    return df


def calculate_single_game_stats(df, game_year):
    """
    Calculates whether the crime volume on the selected game day is a statistically
    significant anomaly compared to historical baselines for that exact date and time.

    Args:
        df (pd.DataFrame): The preprocessed dataset containing the game and historical baselines.
        game_year (int): The year of the specific game being analyzed.

    Returns:
        tuple: (Game Day Total Crimes, Historical Mean, Z-Score, P-Value)
    """
    # Count total crimes per year in the 9-hour window
    yearly_totals = df.groupby('year').size().reset_index(name='total_crimes')

    # Extract the game day total (default to 0 if no crimes occurred)
    try:
        game_total = yearly_totals[yearly_totals["year"] == game_year][
            "total_crimes"
        ].values[0]
    except IndexError:
        game_total = 0

    # Extract all other years to form the baseline distribution
    historical_totals = yearly_totals[yearly_totals['year'] != game_year]['total_crimes']
    mu = historical_totals.mean()
    sigma = historical_totals.std()

    # Calculate Z-Score and two-tailed P-value to test for statistical significance
    if sigma > 0:
        z_score = (game_total - mu) / sigma
        p_value = stats.norm.sf(abs(z_score)) * 2
    else:
        z_score = 0
        p_value = 1.0

    return game_total, mu, z_score, p_value


@st.cache_data
def calculate_macro_trends():
    """
    Aggregates the total crimes across ALL available game days and runs a paired t-test
    against their respective historical baselines to determine overarching macroeconomic trends.

    Returns:
        dict: A dictionary containing sample size, averages, statistical test results,
              and the raw array data needed to draw the box plot. Returns None if data is missing.
    """
    files = glob.glob("data/crimes_for_game_*.csv")
    game_day_totals, baseline_averages = [], []

    for file in files:
        df_macro = pd.read_csv(file)
        if df_macro.empty:
            continue

        df_macro["date"] = pd.to_datetime(df_macro["date"])
        df_macro["year"] = df_macro["date"].dt.year

        # Determine which year in the file represents the actual game day
        filename = os.path.basename(file)
        game_year = int(filename.replace("crimes_for_game_", "").split("-")[0])
        yearly_totals = df_macro.groupby("year").size().reset_index(name="crimes")

        try:
            game_total = yearly_totals[yearly_totals["year"] == game_year][
                "crimes"
            ].values[0]
        except IndexError:
            game_total = 0

        historical_totals = yearly_totals[yearly_totals["year"] != game_year]["crimes"]

        # Only append valid pairings where a historical baseline exists
        if not historical_totals.empty:
            game_day_totals.append(game_total)
            baseline_averages.append(historical_totals.mean())

    if not game_day_totals:
        return None

    # Run a paired t-test to compare game days against their own specific baselines
    t_stat, p_value = stats.ttest_rel(game_day_totals, baseline_averages)

    return {
        "n_games": len(game_day_totals),
        "avg_game": sum(game_day_totals) / len(game_day_totals),
        "avg_baseline": sum(baseline_averages) / len(baseline_averages),
        "t_stat": t_stat,
        "p_value": p_value,
        "raw_game_data": game_day_totals,
        "raw_baseline_data": baseline_averages,
    }


# ==========================================
# 3. VISUALIZATION FUNCTIONS
# ==========================================
def create_line_chart(df, game_year):
    """
    Generates an interactive Plotly line chart comparing hourly crime on game day
    to individual historical years and the historical average.

    Args:
        df (pd.DataFrame): The standardized 9-hour dataset.
        game_year (int): The target year to highlight in red.

    Returns:
        go.Figure: The rendered Plotly line chart object.
    """
    hourly_counts = df.groupby(['year', 'relative_hour']).size().reset_index(name='crimes')
    historical_counts = hourly_counts[hourly_counts['year'] != game_year]
    avg_historical = historical_counts.groupby('relative_hour')['crimes'].mean().reset_index()

    fig = go.Figure()

    # Draw faint, semi-transparent lines for every historical year (the "spaghetti" lines)
    for year in historical_counts['year'].unique():
        year_data = historical_counts[historical_counts['year'] == year]
        fig.add_trace(go.Scatter(
            x=year_data['relative_hour'], y=year_data['crimes'],
            mode='lines', line=dict(color='gray', width=1),
            opacity=0.25, name=str(year), showlegend=False, hoverinfo='skip'
        ))

    # Draw the dashed yellow line representing the historical average
    fig.add_trace(go.Scatter(
        x=avg_historical['relative_hour'], y=avg_historical['crimes'],
        mode='lines+markers', line=dict(color='yellow', width=3, dash='dash'), name='Historical Avg'
    ))

    # Draw the thick red line representing the actual game day
    game_data = hourly_counts[hourly_counts['year'] == game_year]
    fig.add_trace(go.Scatter(
        x=game_data['relative_hour'], y=game_data['crimes'],
        mode='lines+markers', line=dict(color='red', width=4), name='Game Day'
    ))

    # Format layout and add vertical game phase markers
    fig.update_layout(
        xaxis_title="Hours Relative to Kickoff",
        yaxis_title="Number of Crimes",
        hovermode="x unified",
        xaxis=dict(tickmode="linear", dtick=1, range=[-3, 6]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.add_vline(x=0, line_dash="dot", line_color="green", annotation_text="Kickoff")
    fig.add_vline(x=3, line_dash="dot", line_color="orange", annotation_text="Game End")

    return fig


def create_heatmap(df_g, df_h, show_h):
    """
    Generates a 3D WebGL Pydeck heatmap overlaying crime locations around Soldier Field.

    Args:
        df_g (pd.DataFrame): Game day crime coordinates.
        df_h (pd.DataFrame): Historical baseline crime coordinates.
        show_h (bool): Whether to render the historical baseline layer beneath the game day layer.

    Returns:
        pdk.Deck: The rendered Pydeck map object.
    """
    layers = []

    # Optional Layer: Historical Data (dimmer, bluish tint)
    if show_h:
        df_h_clean = df_h[['latitude', 'longitude']].dropna().to_dict(orient='records')
        layers.append(pdk.Layer(
            "HeatmapLayer", data=df_h_clean,
            get_position=["longitude", "latitude"],
            get_weight=1, radiusPixels=10, opacity=0.3,
            colorRange=[[237, 248, 251], [191, 211, 230], [158, 188, 218], [140, 150, 198], [136, 86, 167]]
        ))

    # Primary Layer: Game Day Data (bright, highly opaque)
    df_g_clean = df_g[['latitude', 'longitude']].dropna().to_dict(orient='records')
    layers.append(pdk.Layer(
        "HeatmapLayer", data=df_g_clean,
        get_position=["longitude", "latitude"],
        get_weight=1, radiusPixels=10, opacity=0.8,
    ))

    # Marker Layer: Soldier Field Coordinates
    stadium_data = [{"lat": SOLDIER_FIELD_LAT, "lon": SOLDIER_FIELD_LON}]
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=stadium_data,
            get_position=["lon", "lat"],
            get_color=[255, 100, 0, 200],
            get_radius=800,
        )
    )

    view_state = pdk.ViewState(
        longitude=SOLDIER_FIELD_LON, latitude=SOLDIER_FIELD_LAT, zoom=10.5, pitch=0
    )
    return pdk.Deck(
        layers=layers, initial_view_state=view_state, tooltip={"text": "Crime Density"}
    )


def get_residential_proportion(df_g):
    """Calculates the proportion of game day crimes that are residential."""
    residential_types = ["APARTMENT", "RESIDENCE", "RETIREMENT HOME"]

    game_total_crimes = len(df_g)
    game_residential = df_g[df_g["location_description"].isin(residential_types)]
    game_res_crimes = len(game_residential)

    if game_total_crimes > 0:
        proportion = (game_res_crimes / game_total_crimes) * 100
    else:
        proportion = 0.0

    return game_res_crimes, game_total_crimes, proportion


# ==========================================
# 4. MAIN APP ROUTING & LAYOUT
# ==========================================
# Halt execution if no data is found
available_games = get_available_games()
if not available_games:
    st.error(
        "No CSV files found in the 'data/' directory. Please run your fetch script first."
    )
    st.stop()

st.title("🏈 Chicago Bears: Game Day Crime Analysis")

# Top UI Control: Game Selector
top_col1, top_col2 = st.columns([1, 2])
with top_col1:
    selected_game = st.selectbox("Select a Game Day:", available_games)

tab1, tab2 = st.tabs(["Single Game Analysis", "Macro Trends"])

# --- TAB 1: SINGLE GAME ---
with tab1:
    st.header(f"Analysis for {selected_game}")

    # Process data for the currently selected dropdown value
    df = load_game_data(selected_game)
    game_year = int(selected_game.split('-')[0])

    # Split into game day vs. historical background
    df_game = df[df['gameday']]
    df_history = df[~df['gameday']]

    # --- Metrics Section ---
    st.subheader("Crime Volume: Game Day vs. Baseline")
    game_total, mu, z_score, p_value = calculate_single_game_stats(df, game_year)

    # Display dynamic color-coded alerts based on the p-value
    if p_value < 0.05:
        if z_score > 0:
            st.error(
                f"🚨 **Statistically Significant Increase:** {game_total} crimes vs avg of {mu:.1f}. (Z: {z_score:.2f}, p={p_value:.3f})"
            )
        else:
            st.success(
                f"📉 **Statistically Significant Decrease:** {game_total} crimes vs avg of {mu:.1f}. (Z: {z_score:.2f}, p={p_value:.3f})"
            )
    else:
        st.info(
            f"📊 **Normal Variance:** {game_total} crimes (Avg: {mu:.1f}). Difference not significant. (Z: {z_score:.2f}, p={p_value:.3f})"
        )

    # --- Render Line Chart ---
    st.plotly_chart(create_line_chart(df, game_year), width="stretch")

    # --- Render Heatmap & Residential Stats ---
    st.subheader("Crime Density Heatmap")

    # Get residential stats
    res_count, total_count, res_prop = get_residential_proportion(df_game)
    col_res1, col_res2 = st.columns([1, 2])

    with col_res1:
        st.metric(
            label="Residential Crimes (Game Day)",
            value=f"{res_count} / {total_count}",
            delta=f"{res_prop:.1f}% of total",
            delta_color="off",
        )
        st.caption("Includes: Apartments, Residences, and Retirement Homes")

    with col_res2:
        show_history = st.checkbox(
            "Show Historical Baseline (Other Years)", value=False
        )

    st.pydeck_chart(create_heatmap(df_game, df_history, show_history))

# --- TAB 2: MACRO TRENDS ---
with tab2:
    st.header("Macro Trends: Do Bears Games Affect Crime?")
    st.write(
        "Analyzes the 9-hour window across **all** historical games running a paired t-test against baselines."
    )

    # Wrap the heavy processing in a spinner so the UI doesn't freeze
    with st.spinner("Crunching macro statistics across all games..."):
        macro_results = calculate_macro_trends()

    if macro_results:
        # High-level KPIs
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Games Analyzed", macro_results["n_games"])
        col_m2.metric("Avg Crimes (Game Day)", f"{macro_results['avg_game']:.2f}")
        col_m3.metric(
            "Avg Crimes (Baseline)",
            f"{macro_results['avg_baseline']:.2f}",
            delta=f"{macro_results['avg_game'] - macro_results['avg_baseline']:.2f} crimes",
            delta_color="inverse",
        )

        # Evaluate the p-value across the entire dataset
        st.subheader("Statistical Conclusion")
        p_val, t_stat = macro_results["p_value"], macro_results["t_stat"]
        if p_val < 0.05:
            if t_stat > 0:
                st.error(
                    f"🚨 **Significant Increase:** Crime is definitively **higher** on game days. (p={p_val:.4f})"
                )
            else:
                st.success(
                    f"📉 **Significant Decrease:** Crime is definitively **lower** on game days. (p={p_val:.4f})"
                )
        else:
            st.info(
                f"📊 **No Significant Difference:** No statistical difference in crime volume. (p={p_val:.4f})"
            )

        # Render Side-by-Side Box Plots
        st.subheader("Distribution of Crime Volume")
        fig_macro = go.Figure()
        fig_macro.add_trace(
            go.Box(
                y=macro_results["raw_baseline_data"],
                name="Historical Baselines",
                marker_color="yellow",
            )
        )
        fig_macro.add_trace(
            go.Box(
                y=macro_results["raw_game_data"],
                name="Actual Game Days",
                marker_color="red",
            )
        )
        fig_macro.update_layout(
            yaxis_title="Total Crimes per 9-Hour Window", showlegend=False
        )
        st.plotly_chart(fig_macro, use_container_width=True)
    else:
        st.warning("Not enough data to run macro analysis.")
