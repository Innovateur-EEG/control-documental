"""Test isolation: importing application modules must never target Supabase."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
