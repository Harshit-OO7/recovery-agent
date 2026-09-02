"""
Convenience module for seeding the database.
Enables running `python -m app.data.seed` directly from Makefile / PowerShell scripts.
"""

from app.data.generate import main

if __name__ == "__main__":
    main()
