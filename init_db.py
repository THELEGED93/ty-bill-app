"""Safely initialize the same database used by the application."""
from app import app, initialize_database

if __name__ == "__main__":
    initialize_database()
    print(f"Database ready: {app.config['DATABASE']}")
