# main.py
"""
Main entry point for the Silent Stride application.
"""

import sys
from PyQt5.QtWidgets import QApplication

# Import the application components
from graph_processor import get_graph
from main_window import MainWindow

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    
    # 1. Load or process the graph data
    G_processed = get_graph()
    
    # 2. Initialize the PyQt Application
    app = QApplication(sys.argv)
    
    # 3. Create and show the main window
    window = MainWindow(G_processed)
    window.show()
    
    # 4. Start the application's event loop
    sys.exit(app.exec())