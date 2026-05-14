"""Quick diagnostic – shows DB tables, car_images records, and upload dir."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Car, CarImage

with app.app_context():
    from sqlalchemy import inspect
    tables = inspect(db.engine).get_table_names()
    print("Tables in DB:", tables)

    cars = Car.query.all()
    print(f"\nTotal cars: {len(cars)}")
    for c in cars:
        imgs = CarImage.query.filter_by(car_id=c.id).all()
        print(f"  Car #{c.id} '{c.model_name}' → {len(imgs)} image(s): {[i.filename for i in imgs]}")

    print("\nFiles in static/uploads/:")
    up = os.path.join('static', 'uploads')
    if os.path.isdir(up):
        for f in os.listdir(up):
            print(f"  {f}")
    else:
        print("  (directory missing)")
