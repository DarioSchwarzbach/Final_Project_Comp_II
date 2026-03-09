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
st.set_page_config(page_title="Bears Game Day Crime Explorer", layout="wide")

SOLDIER_FIELD_LAT = 41.8623
SOLDIER_FIELD_LON = -87.6167


# ==========================================
# 2. DATA & STATISTICAL FUNCTIONS
# ==========================================
@st.cache_data
def get_available_games():
    files = glob.glob("data/crimes_for_game_*.csv")
    game_days = [
        os.path.basename(f).replace("crimes_for_game_", "").replace(".csv", "")
        for f in files
    ]
    return sorted(game_days, reverse=True)


@st.cache_data
def load_game_data(gameday_str):
    path = f"data/crimes_for_game_{gameday_str}.csv"
    df = pd.read_csv(path)

    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["hour"] = df["date"].dt.hour
    df["gameday"] = df["gameday"].astype(bool)

    if df["hour"].max() - df["hour"].min() > 12:
        df["adj_hour"] = df["hour"].apply(lambda h: h + 24 if h < 12 else h)
    else:
        df["adj_hour"] = df["hour"]

    kickoff_hour_adj = df["adj_hour"].min() + 3
    df["relative_hour"] = df["adj_hour"] - kickoff_hour_adj

    return df


def calculate_single_game_stats(df, game_year):
    """Calculates Z-score and p-value for a single game day."""
    yearly_totals = df.groupby("year").size().reset_index(name="total_crimes")

    try:
        game_total = yearly_totals[yearly_totals["year"] == game_year][
            "total_crimes"
        ].values[0]
    except IndexError:
        game_total = 0

    historical_totals = yearly_totals[yearly_totals["year"] != game_year][
        "total_crimes"
    ]
    mu = historical_totals.mean()
    sigma = historical_totals.std()

    if sigma > 0:
        z_score = (game_total - mu) / sigma
        p_value = stats.norm.sf(abs(z_score)) * 2
    else:
        z_score = 0
        p_value = 1.0

    return game_total, mu, z_score, p_value


@st.cache_data
def calculate_macro_trends():
    files = glob.glob("data/crimes_for_game_*.csv")
    game_day_totals, baseline_averages = [], []

    for file in files:
        df_macro = pd.read_csv(file)
        if df_macro.empty:
            continue

        df_macro["date"] = pd.to_datetime(df_macro["date"])
        df_macro["year"] = df_macro["date"].dt.year

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

        if not historical_totals.empty:
            game_day_totals.append(game_total)
            baseline_averages.append(historical_totals.mean())

    if not game_day_totals:
        return None

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
    hourly_counts = (
        df.groupby(["year", "relative_hour"]).size().reset_index(name="crimes")
    )
    historical_counts = hourly_counts[hourly_counts["year"] != game_year]
    avg_historical = (
        historical_counts.groupby("relative_hour")["crimes"].mean().reset_index()
    )

    fig = go.Figure()

    for year in historical_counts["year"].unique():
        year_data = historical_counts[historical_counts["year"] == year]
        fig.add_trace(
            go.Scatter(
                x=year_data["relative_hour"],
                y=year_data["crimes"],
                mode="lines",
                line=dict(color="gray", width=1),
                opacity=0.25,
                name=str(year),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=avg_historical["relative_hour"],
            y=avg_historical["crimes"],
            mode="lines+markers",
            line=dict(color="yellow", width=3, dash="dash"),
            name="Historical Avg",
        )
    )

    game_data = hourly_counts[hourly_counts["year"] == game_year]
    fig.add_trace(
        go.Scatter(
            x=game_data["relative_hour"],
            y=game_data["crimes"],
            mode="lines+markers",
            line=dict(color="red", width=4),
            name="Game Day",
        )
    )

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
    layers = []

    if show_h:
        df_h_clean = df_h[["latitude", "longitude"]].dropna().to_dict(orient="records")
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                data=df_h_clean,
                get_position=["longitude", "latitude"],
                get_weight=1,
                radiusPixels=50,
                opacity=0.3,
                colorRange=[
                    [237, 248, 251],
                    [191, 211, 230],
                    [158, 188, 218],
                    [140, 150, 198],
                    [136, 86, 167],
                ],
            )
        )

    df_g_clean = df_g[["latitude", "longitude"]].dropna().to_dict(orient="records")
    layers.append(
        pdk.Layer(
            "HeatmapLayer",
            data=df_g_clean,
            get_position=["longitude", "latitude"],
            get_weight=1,
            radiusPixels=50,
            opacity=0.8,
        )
    )

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
available_games = get_available_games()
if not available_games:
    st.error(
        "No CSV files found in the 'data/' directory. Please run your fetch script first."
    )
    st.stop()

st.title("🏈 Chicago Bears: Game Day Crime Analysis")

top_col1, top_col2 = st.columns([1, 2])
with top_col1:
    selected_game = st.selectbox("Select a Game Day:", available_games)

tab1, tab2 = st.tabs(["Single Game Analysis", "Macro Trends"])

# --- TAB 1: SINGLE GAME ---
with tab1:
    st.header(f"Analysis for {selected_game}")

    df = load_game_data(selected_game)
    game_year = int(selected_game.split("-")[0])
    df_game = df[df["gameday"]]
    df_history = df[~df["gameday"]]

    # Stats Section
    st.subheader("Crime Volume: Game Day vs. Baseline")
    game_total, mu, z_score, p_value = calculate_single_game_stats(df, game_year)

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

    # Line Chart
    st.plotly_chart(create_line_chart(df, game_year), width="stretch")

    # Heatmap & Residential Stats
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

    with st.spinner("Crunching macro statistics across all games..."):
        macro_results = calculate_macro_trends()

    if macro_results:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Games Analyzed", macro_results["n_games"])
        col_m2.metric("Avg Crimes (Game Day)", f"{macro_results['avg_game']:.2f}")
        col_m3.metric(
            "Avg Crimes (Baseline)",
            f"{macro_results['avg_baseline']:.2f}",
            delta=f"{macro_results['avg_game'] - macro_results['avg_baseline']:.2f} crimes",
            delta_color="inverse",
        )

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
