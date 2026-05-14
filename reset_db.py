"""One-time script to drop and recreate the database (clears all listings)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db

with app.app_context():
    db.drop_all()
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("✅ Database reset complete. All listings cleared.")
    print("   Tables created:", db.engine.table_names() if hasattr(db.engine, 'table_names') else "users, cars, car_images")
