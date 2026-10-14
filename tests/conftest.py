"""Test isolation: importing the application's database module must never target Supabase."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
