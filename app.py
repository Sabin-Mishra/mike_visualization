import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from datetime import datetime
import glob
import os

# Set page configuration
st.set_page_config(page_title="Oulu Hotels Dashboard", layout="wide")

# Helper function to extract scrape time from filename
def get_scrape_time(filename):
    """Extract scrape time (Morning/Evening) from filename"""
    basename = os.path.basename(filename)
    if 'Mor' in basename:
        return 'Morning'
    elif 'Eve' in basename:
        return 'Evening'
    return 'Unknown'

# Load and process data
@st.cache_data
def load_data():
    """Load all CSV files and combine them"""
    files = glob.glob('csv_files/*.csv')
    dfs = []
    
    for file in files:
        try:
            df = pd.read_csv(file)
            df['scrape_time'] = get_scrape_time(file)
            dfs.append(df)
        except Exception as e:
            st.error(f"Error loading {file}: {e}")
    
    if dfs:
        combined_data = pd.concat(dfs, ignore_index=True)
        
        # Data cleaning and preprocessing
        combined_data['price'] = pd.to_numeric(combined_data['price'], errors='coerce')
        combined_data['review_score'] = pd.to_numeric(combined_data['review_score'], errors='coerce')
        combined_data['distance'] = pd.to_numeric(combined_data['distance'], errors='coerce')
        
        # Convert price_date to datetime
        combined_data['price_date_dt'] = pd.to_datetime(combined_data['price_date'], dayfirst=True, errors='coerce')
        
        # Add weekday information
        combined_data['weekday'] = combined_data['price_date_dt'].dt.day_name()
        
        return combined_data
    else:
        return pd.DataFrame()

# Load data
data = load_data()

if data.empty:
    st.error("No data found. Please make sure CSV files are in the 'csv_files' folder.")
    st.stop()

# Sidebar filters
st.sidebar.header("🔍 Filters")

# Hotel selection
hotel_names = sorted(data['name'].dropna().unique())
selected_hotels = st.sidebar.multiselect(
    "Select Hotels",
    options=hotel_names,
    default=[],
    help="Leave empty to show all hotels"
)

# Number of nights
nights_options = sorted(data['nights'].unique())
selected_nights = st.sidebar.selectbox(
    "Number of Nights",
    options=nights_options,
    index=0
)

# Number of persons (occupancy)
persons_options = sorted(data['persons'].unique())
selected_persons = st.sidebar.selectbox(
    "Number of Persons",
    options=persons_options,
    index=0
)

# Price range
price_data = data['price'].dropna()
if not price_data.empty:
    min_price = float(price_data.min())
    max_price = float(price_data.max())
    
    price_range = st.sidebar.slider(
        "Price Range (€)",
        min_value=min_price,
        max_value=max_price,
        value=(min_price, max_price),
        step=1.0
    )
else:
    price_range = (0, 1000)

# Date range filter
date_range = st.sidebar.date_input(
    "Date Range",
    value=(data['price_date_dt'].min(), data['price_date_dt'].max()),
    min_value=data['price_date_dt'].min(),
    max_value=data['price_date_dt'].max()
)

# Apply filters
filtered_data = data.copy()

# Filter by hotels
if selected_hotels:
    filtered_data = filtered_data[filtered_data['name'].isin(selected_hotels)]

# Filter by nights and persons
filtered_data = filtered_data[
    (filtered_data['nights'] == selected_nights) &
    (filtered_data['persons'] == selected_persons)
]

# Filter by price range
filtered_data = filtered_data[
    (filtered_data['price'] >= price_range[0]) &
    (filtered_data['price'] <= price_range[1])
]

# Filter by date range
if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_data = filtered_data[
        (filtered_data['price_date_dt'] >= pd.Timestamp(start_date)) &
        (filtered_data['price_date_dt'] <= pd.Timestamp(end_date))
    ]

# Helper functions for metrics
def safe_mean(series):
    """Calculate mean safely handling NaN values"""
    clean_series = series.dropna()
    return round(clean_series.mean(), 2) if not clean_series.empty else 0

def calculate_occupancy_rate(df):
    """Calculate occupancy rate based on hotels with available prices"""
    if df.empty:
        return 0
    total_hotels = df['name'].nunique()
    hotels_with_prices = df.dropna(subset=['price'])['name'].nunique()
    return round((hotels_with_prices / total_hotels) * 100, 2) if total_hotels > 0 else 0

# Main dashboard
st.title("🏨 Oulu Hotels Dashboard")
st.markdown("---")

# Key metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    avg_review_score = safe_mean(filtered_data['review_score'])
    st.metric(
        "Average Review Score",
        f"{avg_review_score}",
        help="Average review score of selected hotels"
    )

with col2:
    adr = safe_mean(filtered_data['price'])
    st.metric(
        "ADR (Average Daily Rate)",
        f"€{adr}",
        help="Average Daily Rate across selected hotels"
    )

with col3:
    occupancy_rate = calculate_occupancy_rate(filtered_data)
    st.metric(
        "Occupancy Rate",
        f"{occupancy_rate}%",
        help="Percentage of hotels with available pricing"
    )

with col4:
    revpar = round(adr * (occupancy_rate / 100), 2)
    st.metric(
        "RevPAR",
        f"€{revpar}",
        help="Revenue Per Available Room (ADR × Occupancy Rate)"
    )

st.markdown("---")

# Visualizations
if not filtered_data.empty:
    
    # Price by Date
    st.subheader("📈 Price Trends by Date")
    
    price_by_date = filtered_data.groupby(['price_date_dt', 'scrape_time'])['price'].mean().reset_index()
    
    price_chart = alt.Chart(price_by_date).mark_line(
        point=True,
        strokeWidth=3
    ).encode(
        x=alt.X('price_date_dt:T', title='Date', axis=alt.Axis(labelAngle=-45)),
        y=alt.Y('price:Q', title='Average Price (€)'),
        color=alt.Color('scrape_time:N', 
                       title='Scrape Time',
                       scale=alt.Scale(range=['#1f77b4', '#ff7f0e'])),
        tooltip=['price_date_dt:T', 'price:Q', 'scrape_time:N']
    ).properties(
        width=1000,
        height=400
    ).interactive()
    
    st.altair_chart(price_chart, use_container_width=True)
    
    # RevPAR by Date
    st.subheader("💰 RevPAR Trends by Date")
    
    # Calculate RevPAR for each date and scrape time
    revpar_data = []
    for date in filtered_data['price_date_dt'].unique():
        for scrape_time in filtered_data['scrape_time'].unique():
            subset = filtered_data[
                (filtered_data['price_date_dt'] == date) &
                (filtered_data['scrape_time'] == scrape_time)
            ]
            if not subset.empty:
                avg_price = safe_mean(subset['price'])
                occ_rate = calculate_occupancy_rate(subset)
                revpar_value = avg_price * (occ_rate / 100)
                revpar_data.append({
                    'price_date_dt': date,
                    'scrape_time': scrape_time,
                    'revpar': revpar_value
                })
    
    revpar_df = pd.DataFrame(revpar_data)
    
    if not revpar_df.empty:
        revpar_chart = alt.Chart(revpar_df).mark_line(
            point=True,
            strokeWidth=3
        ).encode(
            x=alt.X('price_date_dt:T', title='Date', axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('revpar:Q', title='RevPAR (€)'),
            color=alt.Color('scrape_time:N', 
                           title='Scrape Time',
                           scale=alt.Scale(range=['#1f77b4', '#ff7f0e'])),
            tooltip=['price_date_dt:T', 'revpar:Q', 'scrape_time:N']
        ).properties(
            width=1000,
            height=400
        ).interactive()
        
        st.altair_chart(revpar_chart, use_container_width=True)
    
    # Occupancy Rate by Date
    st.subheader("🏠 Occupancy Rate Trends by Date")
    
    occupancy_data = []
    for date in filtered_data['price_date_dt'].unique():
        for scrape_time in filtered_data['scrape_time'].unique():
            subset = filtered_data[
                (filtered_data['price_date_dt'] == date) &
                (filtered_data['scrape_time'] == scrape_time)
            ]
            if not subset.empty:
                occ_rate = calculate_occupancy_rate(subset)
                occupancy_data.append({
                    'price_date_dt': date,
                    'scrape_time': scrape_time,
                    'occupancy_rate': occ_rate
                })
    
    occupancy_df = pd.DataFrame(occupancy_data)
    
    if not occupancy_df.empty:
        occupancy_chart = alt.Chart(occupancy_df).mark_line(
            point=True,
            strokeWidth=3
        ).encode(
            x=alt.X('price_date_dt:T', title='Date', axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('occupancy_rate:Q', title='Occupancy Rate (%)', scale=alt.Scale(domain=[0, 100])),
            color=alt.Color('scrape_time:N', 
                           title='Scrape Time',
                           scale=alt.Scale(range=['#1f77b4', '#ff7f0e'])),
            tooltip=['price_date_dt:T', 'occupancy_rate:Q', 'scrape_time:N']
        ).properties(
            width=1000,
            height=400
        ).interactive()
        
        st.altair_chart(occupancy_chart, use_container_width=True)
    
    # Average Rates by Weekday
    st.subheader("📊 Average Rates by Day of Week")
    
    weekday_data = filtered_data.groupby(['weekday', 'scrape_time'])['price'].mean().reset_index()
    
    weekday_chart = alt.Chart(weekday_data).mark_bar().encode(
        x=alt.X('weekday:N', 
               title='Day of Week',
               sort=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']),
        y=alt.Y('price:Q', title='Average Price (€)'),
        color=alt.Color('scrape_time:N', 
                       title='Scrape Time',
                       scale=alt.Scale(range=['#1f77b4', '#ff7f0e'])),
        tooltip=['weekday:N', 'price:Q', 'scrape_time:N']
    ).properties(
        width=1000,
        height=400
    ).interactive()
    
    st.altair_chart(weekday_chart, use_container_width=True)
    
    # Additional insights
    st.markdown("---")
    st.subheader("📋 Data Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Selected Hotels:**")
        if selected_hotels:
            for hotel in selected_hotels:
                st.write(f"• {hotel}")
        else:
            st.write("• All hotels selected")
    
    with col2:
        st.write("**Key Statistics:**")
        st.write(f"• Total records: {len(filtered_data)}")
        st.write(f"• Date range: {filtered_data['price_date_dt'].min().strftime('%Y-%m-%d')} to {filtered_data['price_date_dt'].max().strftime('%Y-%m-%d')}")
        st.write(f"• Unique hotels: {filtered_data['name'].nunique()}")
        st.write(f"• Price range: €{filtered_data['price'].min():.2f} - €{filtered_data['price'].max():.2f}")

else:
    st.warning("No data available for the selected filters. Please adjust your selections.")

# Data table (optional)
with st.expander("📄 View Raw Data"):
    st.dataframe(
        filtered_data[['name', 'price_date_dt', 'scrape_time', 'price', 'review_score', 'distance']].sort_values('price_date_dt'),
        use_container_width=True
    )

# Footer
st.markdown("---")
st.markdown("*Dashboard created with Streamlit • Data refreshed automatically*")
