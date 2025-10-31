# routing_engine.py
"""
Contains the core routing logic for the Silent Stride application.
Handles geocoding, A* pathfinding, and route analysis.
"""

import networkx as nx
import osmnx as ox
import math
from datetime import datetime
from shapely.geometry import Point
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Import helper
from utils import _is_truthy

class RoutingEngine:
    def __init__(self, graph):
        self.G = graph
        self.graph_crs = self.G.graph['crs']
        self.graph_init_crs = self.G.graph.get('init_crs', 'EPSG:4326')
        self.geolocator = Nominatim(user_agent="silent_stride")
        
        # Default preferences
        self.w_time = 1.0
        self.w_noise = 0.0
        self.prefer_parks = False
        self.avoid_junctions = False

    def set_preferences(self, w_time, w_noise, prefer_parks, avoid_junctions):
        """Updates the routing preferences."""
        self.w_time = w_time
        self.w_noise = w_noise
        self.prefer_parks = prefer_parks
        self.avoid_junctions = avoid_junctions

    def _euclidean_heuristic(self, u, v):
        """Heuristic function for A* (Euclidean distance)."""
        node_u_x = self.G.nodes[u]['x']
        node_u_y = self.G.nodes[u]['y']
        node_v_x = self.G.nodes[v]['x']
        node_v_y = self.G.nodes[v]['y']
        return math.dist((node_u_x, node_u_y), (node_v_x, node_v_y))

    def _get_edge_cost(self, u, v, edge_data_dict):
        """ 
        Custom cost function for A* weight.
        Used ONLY for Balanced/Peace modes during NORMAL HOURS.
        """
        time_cost = float(edge_data_dict.get('time_cost_norm', 1.0))
        noise_cost = float(edge_data_dict.get('noise_cost_norm', 0.0))
        
        if self.w_noise == 1.0: # 100% Peace
            base_cost = noise_cost
        else: # Balanced mode
            base_cost = (self.w_time * time_cost) + (self.w_noise * noise_cost)
        
        if self.prefer_parks and _is_truthy(edge_data_dict.get('green_cover')):
            base_cost *= 0.7 # 30% discount
            
        if self.avoid_junctions and _is_truthy(edge_data_dict.get('is_junction')):
            base_cost *= 2.0 # 100% penalty
        
        if base_cost == 0 and (time_cost > 0 or noise_cost > 0):
             return 1e-9
             
        return base_cost

    def find_route(self, start_address, end_address, selected_hour):
        """
        Main workflow: Geocodes, finds path, and analyzes it.
        Returns a dictionary with results, or raises an error.
        """
        
        # 1. Geocode
        if not start_address or not end_address:
            raise ValueError("Start and end addresses are required.")
        
        start_loc = self.geolocator.geocode(start_address)
        end_loc = self.geolocator.geocode(end_address)
        
        if not start_loc or not end_loc:
            raise ValueError("Could not geocode one or both addresses.")

        # 2. Find nearest graph nodes
        start_point_geom = Point(start_loc.longitude, start_loc.latitude)
        end_point_geom = Point(end_loc.longitude, end_loc.latitude)
        
        start_point_proj, _ = ox.projection.project_geometry(start_point_geom, crs=self.graph_init_crs, to_crs=self.graph_crs)
        end_point_proj, _ = ox.projection.project_geometry(end_point_geom, crs=self.graph_init_crs, to_crs=self.graph_crs)
        
        start_node = ox.nearest_nodes(self.G, X=start_point_proj.x, Y=start_point_proj.y)
        end_node = ox.nearest_nodes(self.G, X=end_point_proj.x, Y=end_point_proj.y)

        # 3. A* Search Logic
        if selected_hour is not None:
            current_hour = selected_hour
            print(f"Using manually selected hour: {current_hour}:00")
        else:
            current_hour = datetime.now().hour
            print(f"Using current system hour: {current_hour}:00")

        # Updated Quiet Hours: 0-7 AM, 10-11 AM, 3-4 PM (15-16), 10-11 PM (22-23)
        is_quiet_hours = (0 <= current_hour <= 7) or \
                         (10 <= current_hour <= 11) or \
                         (15 <= current_hour <= 16) or \
                         (22 <= current_hour <= 23)

        if is_quiet_hours:
            print(f"Quiet Hours ({current_hour}:00). Calculating fastest route using 'time_cost'...")
            weight_function = 'time_cost'
        else:
            if self.w_time >= 0.70: # Speed >= 70% during Normal Hours
                print(f"Normal Hours ({current_hour}:00), Speed >= 70%. Calculating fastest route using 'time_cost'...")
                weight_function = 'time_cost'
            else: # Balanced or Peace modes (< 70% Speed) during Normal Hours
                print(f"Normal Hours ({current_hour}:00), Speed < 70%. Calculating route using custom 'get_edge_cost'...")
                weight_function = self._get_edge_cost
        
        path_nodes = nx.astar_path(
            self.G, start_node, end_node,
            heuristic=self._euclidean_heuristic,
            weight=weight_function
        )
            
        # 4. Analyze Path
        path_edges = list(zip(path_nodes[:-1], path_nodes[1:]))
        total_time_sec = 0.0
        total_noise_weighted = 0.0
        total_length_m = 0.0
        time_in_green = 0.0
        
        # --- THIS IS THE FIX ---
        # Determine the noise multiplier for analytics based on the hour
        analytics_noise_multiplier = 1.0 # Default (for Normal Hours)
        if is_quiet_hours:
            analytics_noise_multiplier = 0.7 # 30% reduction for Quiet Hours
            print("...Applying 30% noise reduction to analytics due to Quiet Hours.")
        # --- END OF FIX ---
        
        for u, v in path_edges:
            edge_data = self.G.get_edge_data(u, v)[0]
            current_time = float(edge_data.get('time_cost', 0.0))
            current_noise = float(edge_data.get('noise_cost', 0.0))
            current_length = float(edge_data.get('length', 0.0))
            
            total_time_sec += current_time
            # --- Apply the multiplier to the noise score before summing ---
            total_noise_weighted += (current_noise * analytics_noise_multiplier)
            total_length_m += current_length
            
            if _is_truthy(edge_data.get('green_cover')):
                time_in_green += current_time
        
        # 5. Format Analytics
        avg_noise = total_noise_weighted / total_length_m if total_length_m > 0 else 0.0
        green_percent = (time_in_green / total_time_sec) * 100 if total_time_sec > 0 else 0.0
        
        analytics = {
            "time": total_time_sec,
            "distance": total_length_m,
            "avg_noise": avg_noise,
            "green_percent": green_percent
        }
        
        # 6. Get Route Geometry
        route_gdf = ox.routing.route_to_gdf(self.G, path_nodes, weight='length')
        route_gdf_4326 = route_gdf.to_crs(self.graph_init_crs)
        
        # 7. Return all results
        return {
            "analytics": analytics,
            "route_gdf": route_gdf_4326,
            "start_location": (start_loc.latitude, start_loc.longitude),
            "map_bounds": route_gdf_4326.total_bounds
        }