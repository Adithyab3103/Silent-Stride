# graph_processor.py
"""
Handles all data downloading, processing, and caching (GraphML save/load)
for the Silent Stride application.
"""

import os
import networkx as nx
import osmnx as ox
import geopandas as gpd

# Import settings from config.py
from config import CITY_NAME, DEFAULT_SPEED, GRAPH_FILE

# =============================================================================
# PHASE 1: DATA LOADING AND PROCESSING
# =============================================================================

def load_and_process_graph(city_name):
    """
    Downloads and processes the city graph.
    """
    print(f"Starting data download for {city_name}...")
    
    # 1. Download the road network (Graph G) - Keep unprojected for now
    G = ox.graph_from_place(city_name, network_type="drive")
    
    # 2. Download park polygons
    tags_parks = {"leisure": "park"}
    gdf_parks = ox.features_from_place(city_name, tags=tags_parks)

    # Project graph and parks to UTM
    print("Projecting data to a meter-based coordinate system...")
    G_proj = ox.project_graph(G)
    gdf_parks_proj = gdf_parks.to_crs(G_proj.graph['crs'])

    # Filter for valid park polygons
    park_polygons = gdf_parks_proj[
        (gdf_parks_proj.geom_type.isin(['Polygon', 'MultiPolygon'])) &
        (gdf_parks_proj.is_valid)
    ]
    park_geometries = park_polygons.geometry.reset_index(drop=True)
    
    # Create spatial index for parks
    sindex_parks = park_geometries.sindex
    print(f"Created spatial index with {len(park_polygons)} park polygons.")

    # Identify junction nodes (traffic signals)
    print("Identifying major junction nodes (traffic signals)...")
    nodes = G_proj.nodes(data=True)
    junction_nodes = set()
    for node_id, data in nodes:
        if data.get('highway') == 'traffic_signals':
            junction_nodes.add(node_id)
    print(f"Identified {len(junction_nodes)} traffic signal nodes.")
    
    print("Graph download complete. Processing custom costs...")

    # 3. Process the graph edges: Add custom costs
    for u, v, key, edge_data in G_proj.edges(keys=True, data=True):
        
        # Ensure numeric types BEFORE assignment
        speed_kmh = float(edge_data.get('speed_kph', DEFAULT_SPEED))
        length_m = float(edge_data.get('length', 0.0))
        
        if speed_kmh == 0:
            current_time_cost = float('inf')
        else:
            current_time_cost = (length_m / 1000) / speed_kmh * 3600
        edge_data['time_cost'] = float(current_time_cost)

        road_type = edge_data.get('highway', 'residential')
        noise_score = 5
        if road_type in ['motorway', 'primary', 'trunk']: noise_score = 10
        elif road_type in ['secondary', 'tertiary']: noise_score = 7
        elif road_type in ['residential', 'living_street', 'unclassified']: noise_score = 3
        edge_data['noise_cost'] = float(noise_score * length_m)

        edge_data['length'] = float(length_m)

        road_geom = edge_data.get('geometry')
        edge_data['green_cover'] = False
        if road_geom:
            buffered_road = road_geom.buffer(20)
            possible_matches_index = list(sindex_parks.intersection(buffered_road.bounds))
            if possible_matches_index:
                possible_matches = park_geometries.iloc[possible_matches_index]
                if possible_matches.intersects(buffered_road).any():
                    edge_data['green_cover'] = True
            
        if u in junction_nodes or v in junction_nodes:
            edge_data['is_junction'] = True
        else:
            edge_data['is_junction'] = edge_data.get('junction', False) # Fallback


    # Normalize the costs
    print("Normalizing costs (scaling to 0-1)...")
    
    times = [float(data['time_cost']) for u, v, k, data in G_proj.edges(keys=True, data=True) if float(data['time_cost']) != float('inf')]
    noises = [float(data['noise_cost']) for u, v, k, data in G_proj.edges(keys=True, data=True)]
    
    min_time, max_time = min(times), max(times)
    min_noise, max_noise = min(noises), max(noises)

    range_time = max_time - min_time if (max_time - min_time) > 0 else 1.0
    range_noise = max_noise - min_noise if (max_noise - min_noise) > 0 else 1.0

    for u, v, key, edge_data in G_proj.edges(keys=True, data=True):
        current_time_cost = float(edge_data['time_cost'])
        current_noise_cost = float(edge_data['noise_cost'])

        if current_time_cost == float('inf'):
            edge_data['time_cost_norm'] = 1.0
        else:
            edge_data['time_cost_norm'] = float((current_time_cost - min_time) / range_time)
            
        edge_data['noise_cost_norm'] = float((current_noise_cost - min_noise) / range_noise)
    
    print("Cost normalization complete.")

    # 4. Save the processed graph
    ox.save_graphml(G_proj, GRAPH_FILE)
    print(f"Processed graph saved to {GRAPH_FILE}")
    return G_proj

def get_graph():
    """
    Loads the graph from the file if it exists,
    otherwise downloads and processes it.
    """
    if os.path.exists(GRAPH_FILE):
        print(f"Loading pre-processed graph from {GRAPH_FILE}...")
        G = ox.load_graphml(GRAPH_FILE)
        print("Graph loaded from file.")
        # Safety check for loaded data types
        print("Verifying loaded graph data types...")
        needs_resave = False
        for u, v, k, data in G.edges(keys=True, data=True):
            if not isinstance(data.get('time_cost'), (int, float)):
                 data['time_cost'] = float(data.get('time_cost', float('inf')))
                 needs_resave = True
        if needs_resave:
            print("Corrected data types in loaded graph. Re-saving...")
            ox.save_graphml(G, GRAPH_FILE)
            print(f"Re-saved graph to {GRAPH_FILE}")
        else:
            print("Graph data types look correct.")
        return G
    else:
        print("No pre-processed graph file found.")
        return load_and_process_graph(CITY_NAME)