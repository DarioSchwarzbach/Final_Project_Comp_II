import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import great_tables as gt
import pydeck as pdk
from plotly.subplots import make_subplots


st.set_page_config(layout="wide", page_title="Bears Performance vs. Chicago Crime")

# Load data
def load_data():
    # Force reload

    try:
        daily_df = pd.read_csv('data/processed/daily_crime_with_bears.csv')
        daily_df['date_only'] = pd.to_datetime(daily_df['date_only'])
        
        seasonal_df = pd.read_csv('data/processed/seasonal_aggregates.csv')
        heatmap_df = pd.read_csv('data/processed/filtered_jan18_crimes.csv').sort_values(by='date', ascending=False)
        
        return daily_df, seasonal_df, heatmap_df
    except FileNotFoundError as ex:
        st.error(f"Data files not found. Please run the data acquisition and processing pipelines first: {ex}")
        return None, None, None

def plot_seasonal_trends(seasonal_df):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Left Y axis (Crimes)
    fig.add_trace(
        go.Scatter(
            x=seasonal_df.query('year >= 1985')['year'], 
            y=seasonal_df.query('year >= 1985')['total_violent_crimes'], 
            name="Violent Crimes", 
            mode='lines+markers', 
            marker=dict(color='red', size=8),
            line=dict(color='red', width=2)
        ),
        secondary_y=False,
    )
    
    # Right Y axis (Wins)
    fig.add_trace(
        go.Scatter(
            x=seasonal_df.query('year >= 1985')['year'], 
            y=seasonal_df.query('year >= 1985')['wins'], 
            name="Bears Wins (PFR)", 
            mode='lines+markers', 
            marker=dict(color='white', symbol='circle-open', size=10),
            line=dict(color='white', width=2)
        ),
        secondary_y=True,
    )
    
    fig.update_layout(
        title_text="Year-over-Year: Bears Wins vs Total Violent Crimes",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    fig.update_xaxes(title_text="Year")
    fig.update_yaxes(title_text="Total Violent Crimes (Scale)", secondary_y=False)
    fig.update_yaxes(title_text="Bears Wins", secondary_y=True, range=[0, 17])
    
    return fig

def create_heatmap(heatmap_df):
    SOLDIER_FIELD_LAT = 41.8623
    SOLDIER_FIELD_LON = -87.6167
    
    # Pydeck continuous 2D Heatmap Layer for crime density
    layer = pdk.Layer(
        "HeatmapLayer",
        heatmap_df,
        get_position=["longitude", "latitude"],
        get_weight=1,
        radiusPixels=50,
        opacity=0.7,
    )
    
    # Soldier field marker
    stadium_layer = pdk.Layer(
        "ScatterplotLayer",
        pd.DataFrame([{"lat": SOLDIER_FIELD_LAT, "lon": SOLDIER_FIELD_LON}]),
        get_position=["lon", "lat"],
        get_color=[255, 100, 0, 200],
        get_radius=800,
    )

    view_state = pdk.ViewState(
        longitude=SOLDIER_FIELD_LON,
        latitude=SOLDIER_FIELD_LAT,
        zoom=11,
        pitch=0,
    )

    r = pdk.Deck(
        layers=[layer, stadium_layer],
        initial_view_state=view_state,
        tooltip={"text": "Density Focus"}
    )
    return r

def main():
    st.title("🏈 EDA: Chicago Bears Performance vs. Civic Safety")
    st.markdown("""
    This project explores whether the performance of the Chicago Bears (Wins/Losses) has any observable correlation with violent crime rates (Homicides, Assaults, Battery) in the city of Chicago, with a focus on areas close to Soldier Field.
    """)
    
    daily_df, seasonal_df, heatmap_df = load_data()
    if daily_df is None:
        return
        
    st.header("1. Macro View: Seasonal Trends")
    st.markdown("Do seasons with poorly performing Bears teams correlate with higher overall violent crime rates?")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(plot_seasonal_trends(seasonal_df), use_container_width=True)
    
    with col2:
        st.markdown("### Summary Statistics")
        # Generate GreatTable using new PFR metrics
        cols_for_table = ['year', 'wins', 'losses', 'points', 'points_opp', 'total_violent_crimes']
        gt_tbl = (
            gt.GT(seasonal_df[cols_for_table].sort_values('year', ascending=False).head(5))
            .tab_header(title="Recent Seasons Recap (PFR Adjusted)")
            .fmt_number(columns=["total_violent_crimes"], decimals=0, use_seps=True)
        )
        st.html(gt_tbl.as_raw_html())

    st.header("2. Micro View: Game Day Density")
    st.markdown("Where do crimes occur on Game Days specifically? The orange circle represents Soldier Field.")
    
    # Add toggleable layers for each year from 2010 to 2026
    if 'date' in heatmap_df.columns:
        heatmap_df['year'] = pd.to_datetime(heatmap_df['date']).dt.year
    elif 'date_only' in heatmap_df.columns:
        heatmap_df['year'] = pd.to_datetime(heatmap_df['date_only']).dt.year
        
    if 'year' in heatmap_df.columns:
        years = sorted(heatmap_df['year'].dropna().unique().astype(int).tolist(), reverse=True)
        selected_years = st.multiselect("Toggle Years to Display", options=years, default=years)
        filtered_heatmap = heatmap_df[heatmap_df['year'].isin(selected_years)]
    else:
        filtered_heatmap = heatmap_df
        
    st.pydeck_chart(create_heatmap(filtered_heatmap))

if __name__ == "__main__":
    main()
