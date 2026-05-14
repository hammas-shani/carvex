"""Delete Muzammil's Toyota Corolla listing from DB."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Car, CarImage, User

with app.app_context():
    # Find muzammil's user account
    muzammil = User.query.filter(User.email.ilike('%muzammil%')).first()

    if not muzammil:
        print("❌ Muzammil ka account nahi mila. Sab users:")
        for u in User.query.all():
            print(f"   id={u.id}  email={u.email}")
    else:
        print(f"✅ Muzammil mila: id={muzammil.id}, email={muzammil.email}")

        # Find Toyota Corolla listing belonging to muzammil
        car = Car.query.filter(
            Car.user_id == muzammil.id,
            Car.model_name.ilike('%corolla%')
        ).first()

        if not car:
            print("❌ Toyota Corolla listing nahi mili. Muzammil ki saari listings:")
            for c in Car.query.filter_by(user_id=muzammil.id).all():
                print(f"   id={c.id}  model={c.model_name}")
        else:
            print(f"🗑  Deleting: Car #{car.id} — {car.model_name}")

            # Delete image files from disk
            for img in car.images:
                path = os.path.join(app.config['UPLOAD_FOLDER'], img.filename)
                if os.path.isfile(path):
                    os.remove(path)
                    print(f"   Deleted file: {img.filename}")

            db.session.delete(car)   # cascade deletes CarImage rows too
            db.session.commit()
            print("✅ Listing successfully deleted!")
