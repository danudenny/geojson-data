import streamlit as st
import pandas as pd
import json
import requests
from urllib.parse import urlparse
import geopandas as gpd
import io

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def load_geojson_from_url(url):
    try:
        response = requests.get(url)
        return response.json()
    except Exception as e:
        st.error(f"Error loading GeoJSON from URL: {str(e)}")
        return None

def geojson_to_dataframe(geojson_data):
    try:
        # Convert GeoJSON to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
        
        # Extract properties as a regular DataFrame
        properties_df = pd.DataFrame([feature["properties"] for feature in geojson_data["features"]])
        
        return properties_df
    except Exception as e:
        st.error(f"Error converting GeoJSON to DataFrame: {str(e)}")
        return None

def main():
    st.title("GeoJSON Checker")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        ["Upload File", "URL", "Direct Input"]
    )
    
    geojson_data = None
    
    if input_method == "Upload File":
        uploaded_file = st.file_uploader("Upload GeoJSON file", type=["json", "geojson"])
        if uploaded_file:
            try:
                geojson_data = json.load(uploaded_file)
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
    
    elif input_method == "URL":
        url = st.text_input("Enter GeoJSON URL")
        if url and is_valid_url(url):
            geojson_data = load_geojson_from_url(url)
    
    else:  # Direct Input
        geojson_text = st.text_area("Paste GeoJSON data")
        if geojson_text:
            try:
                geojson_data = json.loads(geojson_text)
            except Exception as e:
                st.error(f"Error parsing GeoJSON: {str(e)}")
    
    if geojson_data:
        # Convert to DataFrame
        df = geojson_to_dataframe(geojson_data)
        
        if df is not None and not df.empty:
            st.subheader("GeoJSON Properties")
            
            # Add filters for each column
            st.subheader("Filters")
            filters = {}
            cols = st.columns(3)
            
            for idx, column in enumerate(df.columns):
                with cols[idx % 3]:
                    if df[column].dtype in ['object', 'string']:
                        # For text columns, create a multiselect
                        unique_values = df[column].unique()
                        filters[column] = st.multiselect(
                            f"Filter {column}",
                            options=unique_values,
                            default=[]
                        )
                    elif df[column].dtype in ['int64', 'float64']:
                        # For numeric columns, create a slider
                        min_val = float(df[column].min())
                        max_val = float(df[column].max())
                        filters[column] = st.slider(
                            f"Filter {column}",
                            min_value=min_val,
                            max_value=max_val,
                            value=(min_val, max_val)
                        )
            
            # Apply filters
            filtered_df = df.copy()
            for column, filter_value in filters.items():
                if filter_value:  # If filter is set
                    if isinstance(filter_value, tuple):  # Numeric range
                        filtered_df = filtered_df[
                            (filtered_df[column] >= filter_value[0]) & 
                            (filtered_df[column] <= filter_value[1])
                        ]
                    elif isinstance(filter_value, list):  # Multiselect
                        if filter_value:  # If any values are selected
                            filtered_df = filtered_df[filtered_df[column].isin(filter_value)]
            
            # Display filtered DataFrame
            st.subheader("Data Table")
            st.dataframe(filtered_df)
            
            # Display summary statistics
            st.subheader("Summary Statistics")
            st.write(f"Total features: {len(df)}")
            st.write(f"Filtered features: {len(filtered_df)}")
            st.write(f"Number of properties: {len(df.columns)}")

if __name__ == "__main__":
    main()
