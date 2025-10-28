# main_window.py
"""
Defines the MainWindow class (the PyQt5 UI) and all its associated
event-handling methods (slots).
"""

import sys
from datetime import datetime
import networkx as nx
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Import PyQt5 components
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QSlider, QCheckBox, QTabWidget,
    QMessageBox, QGroupBox, QSpinBox
)
from PyQt5.QtCore import Qt, QUrl

from PyQt5.QtWebEngineWidgets import QWebEngineView

# Import application components
from config import GRAPH_FILE # For error message
from routing_engine import RoutingEngine
from map_visualizer import create_route_map

class MainWindow(QMainWindow):
    def __init__(self, graph):
        super().__init__()
        
        # Initialize the routing engine with the loaded graph
        self.router = RoutingEngine(graph)
        
        self.selected_hour = None # Variable to store user-selected hour

        self.setWindowTitle("SILENT STRIDE: Peaceful Route Finder")
        self.setGeometry(100, 100, 1200, 800)
        
        # Build the UI
        self.init_ui()
        
        # Connect UI signals to methods
        self.connect_signals()
        
        # Set initial preference state in the router
        self.update_weights(0)
        self.update_preferences()


    def init_ui(self):
        """Create and arrange all the UI widgets."""
        
        # --- Left Panel ---
        control_panel = QWidget()
        control_layout = QVBoxLayout()
        control_panel.setLayout(control_layout)
        
        location_box = QGroupBox("Locations")
        location_layout = QVBoxLayout()
        self.start_input = QLineEdit("Times Square, NY")
        self.end_input = QLineEdit("Washington Square Fountain")
        location_layout.addWidget(self.start_input)
        location_layout.addWidget(self.end_input)
        location_box.setLayout(location_layout)

        profile_box = QGroupBox("Route Profile")
        profile_layout = QVBoxLayout()
        self.slider_label = QLabel("100% Speed, 0% Peace")
        self.profile_slider = QSlider(Qt.Horizontal)
        self.profile_slider.setMinimum(0)
        self.profile_slider.setMaximum(100)
        self.profile_slider.setValue(0)
        profile_layout.addWidget(self.slider_label)
        profile_layout.addWidget(self.profile_slider)
        profile_box.setLayout(profile_layout)

        context_box = QGroupBox("Preferences")
        context_layout = QVBoxLayout()
        self.parks_checkbox = QCheckBox("Prefer Parks / Green Zones")
        self.junctions_checkbox = QCheckBox("Avoid Major Junctions")
        context_layout.addWidget(self.parks_checkbox)
        context_layout.addWidget(self.junctions_checkbox)
        context_box.setLayout(context_layout)

        # --- Time of Day Setting ---
        time_box = QGroupBox("Time of Day (Overrides Quiet Hours Logic)")
        time_layout = QHBoxLayout()
        self.hour_label = QLabel("Set Hour (0-23):")
        self.hour_spinbox = QSpinBox()
        self.hour_spinbox.setRange(0, 23)
        self.hour_spinbox.setValue(datetime.now().hour)
        
        self.use_current_time_button = QPushButton("Use Current Time")
        time_layout.addWidget(self.hour_label)
        time_layout.addWidget(self.hour_spinbox)
        time_layout.addWidget(self.use_current_time_button)
        time_box.setLayout(time_layout)

        self.find_route_button = QPushButton("Find Quiet Route")
        self.find_route_button.setStyleSheet("font-size: 16px; padding: 10px;")

        control_layout.addWidget(location_box)
        control_layout.addWidget(profile_box)
        control_layout.addWidget(context_box)
        control_layout.addWidget(time_box)
        control_layout.addStretch(1)
        control_layout.addWidget(self.find_route_button)

        # --- Right Panel ---
        output_panel = QWidget()
        output_layout = QVBoxLayout()
        output_panel.setLayout(output_layout)
        
        self.tabs = QTabWidget()
        self.map_view = QWebEngineView()
        self.map_view.setHtml("<html><body><h1>Enter locations to find a route.</h1></body></html>")
        
        self.analytics_tab = QWidget()
        analytics_layout = QVBoxLayout()
        self.label_total_time = QLabel("Total Time: N/A")
        self.label_total_dist = QLabel("Total Distance: N/A")
        self.label_avg_noise = QLabel("Avg. Noise Score: N/A")
        self.label_green_percent = QLabel("Time near Parks: N/A")
        analytics_layout.addWidget(self.label_total_time)
        analytics_layout.addWidget(self.label_total_dist)
        analytics_layout.addWidget(self.label_avg_noise)
        analytics_layout.addWidget(self.label_green_percent)
        analytics_layout.addStretch(1)
        self.analytics_tab.setLayout(analytics_layout)

        self.tabs.addTab(self.map_view, "Route Map")
        self.tabs.addTab(self.analytics_tab, "Route Analytics")
        output_layout.addWidget(self.tabs)

        # --- Main Layout ---
        main_layout = QHBoxLayout()
        main_layout.addWidget(control_panel, 1)
        main_layout.addWidget(output_panel, 2)
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def connect_signals(self):
        """Connect all UI signals to their respective slot methods."""
        self.profile_slider.valueChanged.connect(self.update_weights)
        self.parks_checkbox.stateChanged.connect(self.update_preferences)
        self.junctions_checkbox.stateChanged.connect(self.update_preferences)
        self.find_route_button.clicked.connect(self.run_route_search)
        self.hour_spinbox.valueChanged.connect(self.set_selected_hour)
        self.use_current_time_button.clicked.connect(self.reset_to_current_time)

    # --- UI Slot Functions ---

    def update_weights(self, value):
        """Called when the profile slider is moved."""
        w_noise = value / 100.0
        w_time = 1.0 - w_noise
        self.slider_label.setText(
            f"Profile ({w_time*100:.0f}% Speed, {w_noise*100:.0f}% Peace)"
        )
        # Update the routing engine with the new preferences
        self.update_preferences()

    def update_preferences(self):
        """Called when slider or checkboxes change. Updates the routing engine."""
        w_noise = self.profile_slider.value() / 100.0
        w_time = 1.0 - w_noise
        prefer_parks = self.parks_checkbox.isChecked()
        avoid_junctions = self.junctions_checkbox.isChecked()
        
        self.router.set_preferences(w_time, w_noise, prefer_parks, avoid_junctions)

    def set_selected_hour(self, hour_value):
        """Stores the hour selected by the user in the spinbox."""
        self.selected_hour = hour_value
        print(f"Manual hour set for time logic: {self.selected_hour}:00")

    def reset_to_current_time(self):
        """Resets the hour selection to use the actual current time."""
        self.selected_hour = None
        current_actual_hour = datetime.now().hour
        self.hour_spinbox.blockSignals(True)
        self.hour_spinbox.setValue(current_actual_hour)
        self.hour_spinbox.blockSignals(False)
        print(f"Time logic reset to use current time ({current_actual_hour}:00).")

    def _update_analytics_tab(self, analytics):
        """Helper function to update all analytics labels."""
        self.label_total_time.setText(f"Total Time: {analytics['time'] / 60:.1f} min")
        self.label_total_dist.setText(f"Total Distance: {analytics['distance'] / 1000:.2f} km")
        self.label_avg_noise.setText(f"Avg. Noise Score/meter: {analytics['avg_noise']:.2f}")
        self.label_green_percent.setText(f"Time near Parks: {analytics['green_percent']:.1f} %")

    # --- Main Workflow Function ---

    def run_route_search(self):
        """
        This function is called when the 'Find Quiet Route' button is clicked.
        It wraps the routing and visualization logic in UI updates and error handling.
        """
        self.find_route_button.setText("Calculating...")
        self.find_route_button.setEnabled(False)
        QApplication.processEvents() # Force UI update

        try:
            # 1. Get inputs from UI
            start_address = self.start_input.text()
            end_address = self.end_input.text()
            
            # 2. Delegate to routing engine
            results = self.router.find_route(
                start_address, 
                end_address, 
                self.selected_hour
            )
            
            # 3. Update Analytics Tab
            self._update_analytics_tab(results['analytics'])

            # 4. Delegate to map visualizer
            map_filepath = create_route_map(
                results['route_gdf'], 
                results['start_location'], 
                results['map_bounds']
            )

            # 5. Load map into web view
            self.map_view.load(QUrl.fromLocalFile(map_filepath))
            self.tabs.setCurrentIndex(0) # Switch to map tab
            
        # --- Error Handling ---
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            QMessageBox.warning(self, "Error", f"Geocoding service error: {e}")
        except (nx.NetworkXNoPath, ValueError) as e:
            QMessageBox.warning(self, "Error", f"Could not find a path: {e}")
        except TypeError as e:
            QMessageBox.critical(self, "Type Error Occurred", f"Error during A* calculation: {e}\n\nPlease check graph data types or delete {GRAPH_FILE} and restart.")
            print(f"Type Error Details during A*: {e}")
        except Exception as e:
            QMessageBox.critical(self, "An Unexpected Error Occurred", str(e))
        
        finally:
            # 6. Re-enable button
            self.find_route_button.setText("Find Quiet Route")
            self.find_route_button.setEnabled(True)