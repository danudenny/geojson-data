import streamlit as st
import pandas as pd
import json
import requests
from urllib.parse import urlparse
import geopandas as gpd
import numpy as np
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.geometry.polygon import orient

# Previous imports and helper functions remain the same...

def geojson_to_dataframe(geojson_data):
    try:
        # Convert GeoJSON to GeoDataFrame with error handling
        if not isinstance(geojson_data, dict) or "features" not in geojson_data:
            raise ValueError("Invalid GeoJSON format")
            
        # Store original GeoJSON for later use
        st.session_state.original_geojson = geojson_data
        
        # Convert to GeoDataFrame with better error handling
        features = []
        for feature in geojson_data["features"]:
            try:
                if isinstance(feature.get("geometry"), (dict, list)):
                    features.append(feature)
            except (TypeError, AttributeError):
                continue
                
        if not features:
            raise ValueError("No valid features found in GeoJSON")
            
        gdf = gpd.GeoDataFrame.from_features(features)
        
        # Extract properties as a regular DataFrame
        properties_df = pd.DataFrame([
            feature.get("properties", {}) 
            for feature in features
        ])
        
        # Add WKT representation of geometries
        properties_df['geometry_wkt'] = gdf.geometry.to_wkt()
        
        # Add CCW column with error handling
        properties_df['CCW (true/false)'] = gdf.geometry.apply(
            lambda geom: is_ccw(geom) if geom else None
        )
        
        # Add 6dec column with error handling
        def safe_check_decimals(geom):
            try:
                if isinstance(geom, Polygon):
                    return has_more_than_6_decimals([geom.exterior.coords])
                elif isinstance(geom, MultiPolygon):
                    return has_more_than_6_decimals([poly.exterior.coords for poly in geom.geoms])
                return None
            except:
                return None
                
        properties_df['6dec (true/false)'] = gdf.geometry.apply(safe_check_decimals)
        
        return properties_df
    except Exception as e:
        st.error(f"Error converting GeoJSON to DataFrame: {str(e)}")
        return None

def filter_geojson(original_geojson, filtered_df):
    """Create a new GeoJSON with only the filtered features."""
    if not original_geojson or "features" not in original_geojson:
        return None
        
    # Create a set of filtered indices based on the DataFrame
    filtered_indices = set(filtered_df.index)
    
    # Filter the original features
    filtered_features = [
        feature for i, feature in enumerate(original_geojson["features"])
        if i in filtered_indices
    ]
    
    # Create new GeoJSON with filtered features
    filtered_geojson = {
        "type": "FeatureCollection",
        "features": filtered_features
    }
    
    return filtered_geojson

def main():
    st.title("GeoJSON Checker")
    
    # Previous input section remains the same...
    
    if geojson_data:
        # Convert to DataFrame
        df = geojson_to_dataframe(geojson_data)
        
        if df is not None and not df.empty:
            # Tabs section remains the same...
            
            with tab1:
                # Previous filter and display code remains the same...
                
                # Download options
                if not filtered_df.empty:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        # Download full data as CSV
                        csv = filtered_df.to_csv(index=False)
                        st.download_button(
                            label="Download as CSV (all columns)",
                            data=csv,
                            file_name="filtered_geojson_data_full.csv",
                            mime="text/csv",
                        )
                    with col2:
                        # Download selected columns as CSV
                        if selected_columns:
                            csv_selected = filtered_df[selected_columns].to_csv(index=False)
                            st.download_button(
                                label="Download as CSV (selected columns)",
                                data=csv_selected,
                                file_name="filtered_geojson_data_selected.csv",
                                mime="text/csv",
                            )
                    with col3:
                        # Download as GeoJSON
                        if hasattr(st.session_state, 'original_geojson'):
                            filtered_geojson = filter_geojson(
                                st.session_state.original_geojson,
                                filtered_df
                            )
                            if filtered_geojson:
                                st.download_button(
                                    label="Download as GeoJSON",
                                    data=json.dumps(filtered_geojson, indent=2),
                                    file_name="filtered_data.geojson",
                                    mime="application/json",
                                )
            
            # Summary tab remains the same...

if __name__ == "__main__":
    main()
