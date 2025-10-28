# utils.py
"""
Contains small, reusable utility functions.
"""

def _is_truthy(val):
    """
    Robustly checks if a value represents "True".
    Handles booleans, numbers, and common string representations.
    """
    if val is None: return False
    if isinstance(val, bool): return val
    if isinstance(val, (int, float)): return val != 0
    if isinstance(val, str): return val.lower() in ['true', '1', 'yes', 't', '1.0']
    return False