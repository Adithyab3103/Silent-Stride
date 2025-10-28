# map_visualizer.py
"""
Handles the creation and saving of the Folium route map.
"""

import os
import folium

from config import HTML_MAP_FILE

def create_route_map(route_gdf, start_location, map_bounds):
    """
    Creates a Folium map, draws the route, and saves it to an HTML file.
    
    Returns the absolute path to the saved HTML file.
    """
    
    # Create the map, centered on the start location
    route_map = folium.Map(location=start_location, zoom_start=14, tiles="CartoDB.positron")
    
    # Add the route geometry as a blue line
    route_geojson = folium.GeoJson(
        route_gdf,
        style_function=lambda x: {'color': 'blue', 'weight': 5, 'opacity': 0.7}
    )
    route_geojson.add_to(route_map)
    
    # Fit the map to the bounds of the route
    route_map.fit_bounds([(map_bounds[1], map_bounds[0]), (map_bounds[3], map_bounds[2])])
    
    # Save the map and return its path
    filepath = os.path.abspath(HTML_MAP_FILE)
    route_map.save(filepath)
    
    return filepath