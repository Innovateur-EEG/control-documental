"""Initialize, migrate, and seed the database in the correct order.

Run with: mise run db-setup
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import init_db
from scripts.migrate_db import main as migrate_main
from scripts.seed_db import main as seed_main


def main() -> None:
    print("Step 1/3: initialize missing tables")
    init_db()
    print("Step 2/3: apply additive schema migrations")
    migrate_main()
    print("Step 3/3: populate baseline configuration")
    seed_main()
    print("Database setup complete.")


if __name__ == "__main__":
    main()
