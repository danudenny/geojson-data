import streamlit as st
import pandas as pd
import json
import requests
from urllib.parse import urlparse
import geopandas as gpd
import numpy as np
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.geometry.polygon import orient

# Set page config to wide mode
st.set_page_config(layout="wide")

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

def is_ccw(geometry):
    """Check if a polygon is counter-clockwise (CCW)."""
    if isinstance(geometry, Polygon):
        return not orient(geometry, sign=1.0).exterior.is_ccw
    elif isinstance(geometry, MultiPolygon):
        return any(not orient(poly, sign=1.0).exterior.is_ccw for poly in geometry.geoms)
    return False

def has_more_than_6_decimals(coords):
    """Check if any coordinate has more than 6 decimal places."""
    for coord in coords:
        for point in coord:
            lon, lat = point
            if (
                len(str(lon).split(".")[1]) > 6
                or len(str(lat).split(".")[1]) > 6
            ):
                return True
    return False

def geojson_to_dataframe(geojson_data):
    try:
        # Convert GeoJSON to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
        
        # Extract properties as a regular DataFrame
        properties_df = pd.DataFrame([feature["properties"] for feature in geojson_data["features"]])
        
        # Add WKT representation of geometries
        properties_df['geometry_wkt'] = gdf.geometry.to_wkt()
        
        # Add CCW column
        properties_df['CCW (true/false)'] = gdf.geometry.apply(is_ccw)
        
        # Add 6dec column
        properties_df['6dec (true/false)'] = gdf.geometry.apply(
            lambda geom: has_more_than_6_decimals(
                geom.exterior.coords if isinstance(geom, Polygon)
                else [part.exterior.coords for part in geom.geoms] if isinstance(geom, MultiPolygon)
                else []
            )
        )
        
        return properties_df
    except Exception as e:
        st.error(f"Error converting GeoJSON to DataFrame: {str(e)}")
        return None

def create_numeric_filter(df, column):
    try:
        # Convert to float and handle NaN values
        values = pd.to_numeric(df[column], errors='coerce')
        valid_values = values.dropna()
        
        if len(valid_values) == 0:
            return None
        
        min_val = float(valid_values.min())
        max_val = float(valid_values.max())
        
        # Ensure min and max are not equal to avoid slider issues
        if min_val == max_val:
            max_val += 1
            
        # Round values to 2 decimal places to avoid floating point issues
        min_val = round(min_val, 2)
        max_val = round(max_val, 2)
        
        return st.slider(
            f"Filter {column}",
            min_value=min_val,
            max_value=max_val,
            value=(min_val, max_val)
        )
    except Exception as e:
        st.warning(f"Could not create numeric filter for column {column}: {str(e)}")
        return None

def create_filter_layout(df):
    # Calculate number of columns based on total number of properties
    num_properties = len(df.columns)
    num_columns = min(5, max(3, num_properties // 4))  # Adjust number of columns based on properties
    
    filters = {}
    
    # Create columns for filter layout
    cols = st.columns(num_columns)
    
    # Create a container for filters with scrolling
    with st.container():
        for idx, column in enumerate(df.columns):
            # Skip geometry_wkt column for filtering
            if column == 'geometry_wkt':
                continue
                
            with cols[idx % num_columns]:
                # Try to convert to numeric, if fails, treat as categorical
                try:
                    numeric_series = pd.to_numeric(df[column], errors='raise')
                    numeric_filter = create_numeric_filter(df, column)
                    if numeric_filter is not None:
                        filters[column] = numeric_filter
                except:
                    # For non-numeric columns, create a multiselect
                    unique_values = df[column].dropna().unique()
                    if len(unique_values) > 0 and len(unique_values) <= 100:  # Limit unique values to prevent UI overload
                        filters[column] = st.multiselect(
                            f"Filter {column}",
                            options=unique_values,
                            default=[]
                        )
    
    return filters

def main():
    st.title("GeoJSON Checker")
    
    # Create two columns for input section
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            ["Upload File", "URL", "Direct Input"]
        )
    
    geojson_data = None
    
    with col2:
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
            geojson_text = st.text_area("Paste GeoJSON data", height=150)
            if geojson_text:
                try:
                    geojson_data = json.loads(geojson_text)
                except Exception as e:
                    st.error(f"Error parsing GeoJSON: {str(e)}")
    
    if geojson_data:
        # Convert to DataFrame
        df = geojson_to_dataframe(geojson_data)
        
        if df is not None and not df.empty:
            # Create tabs for better organization
            tab1, tab2 = st.tabs(["Data View", "Summary"])
            
            with tab1:
                # Filters section
                with st.expander("Filters", expanded=True):
                    filters = create_filter_layout(df)
                
                # Apply filters
                filtered_df = df.copy()
                for column, filter_value in filters.items():
                    if filter_value:  # If filter is set
                        if isinstance(filter_value, tuple):  # Numeric range
                            numeric_series = pd.to_numeric(filtered_df[column], errors='coerce')
                            filtered_df = filtered_df[
                                (numeric_series >= filter_value[0]) & 
                                (numeric_series <= filter_value[1])
                            ]
                        elif isinstance(filter_value, list):  # Multiselect
                            if filter_value:  # If any values are selected
                                filtered_df = filtered_df[filtered_df[column].isin(filter_value)]
                
                # Column selection for display
                selected_columns = st.multiselect(
                    "Select columns to display",
                    options=filtered_df.columns.tolist(),
                    default=filtered_df.columns.tolist()
                )
                
                # Display filtered DataFrame with selected columns
                if selected_columns:
                    st.dataframe(filtered_df[selected_columns], use_container_width=True)
                
                # Download options
                if not filtered_df.empty:
                    col1, col2 = st.columns(2)
                    with col1:
                        # Download full data
                        csv = filtered_df.to_csv(index=False)
                        st.download_button(
                            label="Download all columns as CSV",
                            data=csv,
                            file_name="filtered_geojson_data_full.csv",
                            mime="text/csv",
                        )
                    with col2:
                        # Download selected columns
                        if selected_columns:
                            csv_selected = filtered_df[selected_columns].to_csv(index=False)
                            st.download_button(
                                label="Download selected columns as CSV",
                                data=csv_selected,
                                file_name="filtered_geojson_data_selected.csv",
                                mime="text/csv",
                            )
            
            with tab2:
                # Display summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Features", len(df))
                with col2:
                    st.metric("Filtered Features", len(filtered_df))
                with col3:
                    st.metric("Number of Properties", len(df.columns))
                
                # Add more detailed statistics
                if len(df.columns) > 0:
                    st.subheader("Column Statistics")
                    stats_df = pd.DataFrame({
                        'Column': df.columns,
                        'Type': df.dtypes.astype(str),
                        'Unique Values': df.nunique(),
                        'Missing Values': df.isnull().sum()
                    })
                    st.dataframe(stats_df, use_container_width=True)

if __name__ == "__main__":
    main()
