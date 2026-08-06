#!/usr/bin/env python3
"""Beer Notes — Entry point for running the application directly."""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from beernotes.main import main

if __name__ == "__main__":
    main()
