# Chicago Bears Game Day Crime Explorer
[![Fetch NFL and Crime Data](https://github.com/DarioSchwarzbach/Final_Project_Comp_II/actions/workflows/fetch_data.yml/badge.svg?branch=dev)](https://github.com/DarioSchwarzbach/Final_Project_Comp_II/actions/workflows/fetch_data.yml)

## Project Overview:

This project provides a comprehensive analysis and interactive dashboard to explore the impact of the Chicago Bears on crime rates in Chicago. The application uses a Python model to compare crime volumes on game days against historical baselines, visualizing data through density heatmaps, line charts, and statistical paired t-tests (macro trends). Initially, the team sought to discover a correlation between the Bears' overall season success and Chicago's violent crime rates. After finding this macro-leve success rate to be statistically insignificant, the team pivoted to a micro-level temporal analysis, focusing specifically on the game days and game play hours to uncover localized insights.

## Motivation for the Research Problem:

Two critical questions that may be asked by municipal leaders and law enforcement are whether high visibility events, such as Chicago Bears home and away games, have a statistically significant impact on crime rates and more broadly speaking, whether the overall performance in an NFL season significantly impacts crime rates. By analyzing crime volumes during game windows against historical baselines, this tool aims to provide actionable intelligence for resource allocation, public safety planning, and understanding the broader sociological impact of NFL games on the city of Chicago.

## Summary of the Overall Approach:

The project adopts a data-driven approach leveraging three distinct methods of analysis to evaluate the correlation between Chicago Bears game days and civic safety:

1. **General Correlation (Seasonal Trends)**: Analyzing long-term trends by plotting the Bears' year-over-year win/loss record against the total volume of violent crimes in Chicago. This macro view attempts to identify if broader team success (or failure) correlates with the city's overall violent crime rate across an entire season.
2. **Game Day vs. Baseline (Temporal Analysis)**: Utilizing a specialized data pipeline (`fetch_data.py`), the project extracts a specific 9-hour temporal window (3 hours before kickoff to 6 hours after) for each game day. This is compared against the exact same 9-hour window on historical Sundays where no game was played, establishing a control baseline. A paired t-test determines if the variance in crime is statistically significant.
3. **Spatial Crime Location (Density Mapping)**: Highlighting the localized spatial impact of crime. Using PyDeck heatmaps, the dashboard maps the exact locations of crimes occurring during the game window, focusing particularly on the density of incidents in proximity to Soldier Field and surrounding neighborhoods.

## Key Findings, Results, and Recommendations:

The analytical dashboard relies on rigorous statistical tests to draw conclusions from the localized and macro-level data. The mathematical outputs are intended to guide the following findings and recommendations:

- **Z-Scores & P-Values (Single Game)**: By measuring the number of standard deviations (z-score) a game day's crime volume (Sunday with a game) is from the historical mean (Sunday baseline), the model calculates a p-value. A p-value < 0.05 indicates a statistically significant anomaly (either an increase or decrease in crime).
- **Paired T-Test (Macro Trends)**: By evaluating the mean difference between game day crimes and baseline crimes across the entire dataset, the tool identifies definitive, overarching statistical trends.
- **Recommendations for Stakeholders**:
  - Overall, as we looked at various days across multiple years there was no statistical significance indicated by the Bears' performance nor was there enough evidence to confidently state that during the hours of the football game crime rates were in decline. Because of this result, the team would recommend that the city leaders do not allocate additional resources during the times of the games beyond what they currently do as there is no guarantee that this will lead to consistently less crime.

## File Summary:

- **`app.py`**: The main Streamlit dashboard application for exploring game day crime analytics, including the three main analytical methods (General Correlation, Single Game Analysis, and Macro Trends).
- **`fetch_data.py`**: Python script used to fetch NFL schedules using `nflreadpy` and query the City of Chicago Data API for crime statistics correlated with game windows. Saves outputs to the `data/` directory.
- **`requirements.txt`**: Contains all the required Python packages to run the data fetching script and Streamlit dashboard.
- **`.github/workflows/fetch_data.yml`**: GitHub Actions workflow to automate the fetching of new NFL and crime data.

## Python Packages:

- **streamlit**: An open-source app framework for Machine Learning and Data Science teams.
- **pandas**: Used for core data manipulation and cleaning.
- **scipy.stats**: Used for statistical functions, specifically calculating z-scores, p-values, and t-tests.
- **plotly.graph_objects**: A graphing library for making interactive, publication-quality graphs (used here for line charts, box plots, and dual-axis correlation charts).
- **pydeck**: A WebGL-powered framework for visual exploratory data analysis of large datasets (used for the spatial crime density heatmaps).
- **requests**: An HTTP library for making API calls to the City of Chicago data portal.
- **polars**: A blazingly fast DataFrames library used here alongside pandas for data manipulation.
- **nflreadpy**: A Python library to access NFL schedule and game data.

## Steps to run the application:

1. Clone the app repository:
    ```bash
    git clone https://github.com/DarioSchwarzbach/Final_Project_Comp_II.git
    ```
2. Open Anaconda Command Prompt or Terminal.
3. Navigate to the project root directory where `app.py` is saved.
4. Create a new `conda` environment or activate an existing one, e.g.:
    * Create:
    ```bash
    conda create -n new_name python=3.13 pip
    ```
    * Activate (at least **Python 3.12** recommended and `pip` installed): 
    ```bash
    conda activate old_name
    ```
5. Install all required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
6. Ensure you have the datasets downloaded by running the fetch script:
   ```bash
   python fetch_data.py
   ```
7. Run the following command to start the dashboard:
   ```bash
   python -m streamlit run app.py
   ```
