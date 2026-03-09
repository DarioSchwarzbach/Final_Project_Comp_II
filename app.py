import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import scipy.stats as stats
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

# Create the tabs
tab1, tab2 = st.tabs(["Single Game Analysis", "Macro Trends"])

with tab1:
    st.header(f"Analysis for {selected_game}")

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

    # Stats for each game day
    # 1. Calculate total crimes for each year in the 9-hour window
    yearly_totals = df.groupby('year').size().reset_index(name='total_crimes')
    game_year = int(selected_game.split('-')[0])

    # 2. Separate game day total from historical totals
    try:
        game_total = yearly_totals[yearly_totals['year'] == game_year]['total_crimes'].values[0]
    except IndexError:
        game_total = 0

    historical_totals = yearly_totals[yearly_totals['year'] != game_year]['total_crimes']
    mu = historical_totals.mean()
    sigma = historical_totals.std()

    # 3. Calculate Z-Score and statistical significance
    if sigma > 0:
        z_score = (game_total - mu) / sigma
        # Calculate two-tailed p-value
        p_value = stats.norm.sf(abs(z_score)) * 2
    else:
        z_score = 0
        p_value = 1.0

    # 4. Display the result in a Streamlit Metric/Info box
    is_significant = p_value < 0.05

    if is_significant:
        if z_score > 0:
            st.error(f"🚨 **Statistically Significant Increase:** This game day had {game_total} crimes compared to the historical average of {mu:.1f}. (Z-score: {z_score:.2f}, p={p_value:.3f})")
        else:
            st.success(f"📉 **Statistically Significant Decrease:** This game day had {game_total} crimes compared to the historical average of {mu:.1f}. (Z-score: {z_score:.2f}, p={p_value:.3f})")
    else:
        st.info(f"📊 **Normal Variance:** This game day had {game_total} crimes (Avg: {mu:.1f}). The difference is not statistically significant. (Z-score: {z_score:.2f}, p={p_value:.3f})")

    # Group by year and relative hour to get crime counts
    hourly_counts = df.groupby(['year', 'relative_hour']).size().reset_index(name='crimes')

    # Calculate historical average
    historical_counts = hourly_counts[hourly_counts['year'] != game_year]
    avg_historical = historical_counts.groupby('relative_hour')['crimes'].mean().reset_index()

    fig = go.Figure()

    # Add the lines
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

with tab2:
    st.header("Macro Trends: Do Bears Games Affect Crime?")
    st.write(
        "This tab analyzes the 9-hour window across **all** historical games in our dataset, running a paired t-test against their respective historical baselines.")


    @st.cache_data
    def calculate_macro_trends():
        files = glob.glob("data/crimes_for_game_*.csv")
        game_day_totals = []
        baseline_averages = []

        for file in files:
            df_macro = pd.read_csv(file)
            if df_macro.empty:
                continue

            df_macro['date'] = pd.to_datetime(df_macro['date'])
            df_macro['year'] = df_macro['date'].dt.year

            # Extract game year from filename
            filename = os.path.basename(file)
            game_year = int(filename.replace('crimes_for_game_', '').split('-')[0])

            yearly_totals = df_macro.groupby('year').size().reset_index(name='crimes')

            try:
                game_total = yearly_totals[yearly_totals['year'] == game_year]['crimes'].values[0]
            except IndexError:
                game_total = 0

            historical_totals = yearly_totals[yearly_totals['year'] != game_year]['crimes']

            if not historical_totals.empty:
                game_day_totals.append(game_total)
                baseline_averages.append(historical_totals.mean())

        if not game_day_totals:
            return None

        # Run the statistical test
        t_stat, p_value = stats.ttest_rel(game_day_totals, baseline_averages)
        avg_game = sum(game_day_totals) / len(game_day_totals)
        avg_baseline = sum(baseline_averages) / len(baseline_averages)

        return {
            "n_games": len(game_day_totals),
            "avg_game": avg_game,
            "avg_baseline": avg_baseline,
            "t_stat": t_stat,
            "p_value": p_value,
            "raw_game_data": game_day_totals,
            "raw_baseline_data": baseline_averages
        }


    # Run the cached function
    with st.spinner("Crunching macro statistics across all games..."):
        macro_results = calculate_macro_trends()

    if macro_results:
        # --- Display Top Level Metrics ---
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Games Analyzed", macro_results["n_games"])
        col_m2.metric("Avg Crimes (Game Day)", f"{macro_results['avg_game']:.2f}")
        col_m3.metric("Avg Crimes (Baseline)", f"{macro_results['avg_baseline']:.2f}",
                      delta=f"{macro_results['avg_game'] - macro_results['avg_baseline']:.2f} crimes",
                      delta_color="inverse")  # Inverse means red is positive (more crime)

        # --- Display Statistical Conclusion ---
        st.subheader("Statistical Conclusion")
        p_val = macro_results['p_value']
        t_stat = macro_results['t_stat']

        if p_val < 0.05:
            if t_stat > 0:
                st.error(
                    f"🚨 **Statistically Significant Increase:** Across {macro_results['n_games']} games, crime is definitively **higher** on game days compared to historical baselines. (p-value: {p_val:.4f})")
            else:
                st.success(
                    f"📉 **Statistically Significant Decrease:** Across {macro_results['n_games']} games, crime is definitively **lower** on game days compared to historical baselines. (p-value: {p_val:.4f})")
        else:
            st.info(
                f"📊 **No Significant Difference:** There is no statistically significant difference in crime volume between game days and their historical baselines. (p-value: {p_val:.4f})")

        # --- Display Box Plot ---
        st.subheader("Distribution of Crime Volume")
        fig_macro = go.Figure()

        fig_macro.add_trace(go.Box(
            y=macro_results["raw_baseline_data"],
            name="Historical Baselines",
            marker_color="yellow"
        ))
        fig_macro.add_trace(go.Box(
            y=macro_results["raw_game_data"],
            name="Actual Game Days",
            marker_color="red"
        ))

        fig_macro.update_layout(
            yaxis_title="Total Crimes per 9-Hour Window",
            showlegend=False
        )
        st.plotly_chart(fig_macro, use_container_width=True)
    else:
        st.warning("Not enough data to run macro analysis.")