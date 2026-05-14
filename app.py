import os
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-a-long-random-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///accidrive.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64 MB (multiple images)
x
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    cars = db.relationship('Car', backref='owner', lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Car(db.Model):
    __tablename__ = 'cars'

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    driveable = db.Column(db.Boolean, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    images = db.relationship('CarImage', backref='car', lazy=True,
                             cascade='all, delete-orphan')

    @property
    def cover_image(self):
        """Returns the filename of the first image, or None."""
        if self.images:
            return self.images[0].filename
        return None


class CarImage(db.Model):
    __tablename__ = 'car_images'

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    if q:
        cars = Car.query.filter(
            db.or_(
                Car.model_name.ilike(f'%{q}%'),
                Car.location.ilike(f'%{q}%'),
            )
        ).all()
    else:
        cars = Car.query.order_by(Car.id.desc()).all()
    return render_template('index.html', cars=cars, q=q)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            flash('Invalid email or password.', 'danger')

        elif action == 'signup':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            phone = request.form.get('phone', '').strip()
            if User.query.filter_by(email=email).first():
                flash('Email already registered. Please log in.', 'danger')
            else:
                user = User(email=email, phone=phone)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash('Account created! Welcome to CarVex.', 'success')
                return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/add-car', methods=['GET', 'POST'])
@login_required
def add_car():
    if request.method == 'POST':
        model_name = request.form.get('model_name', '').strip()
        price = request.form.get('price', '0')
        location = request.form.get('location', '').strip()
        driveable = request.form.get('driveable') == 'yes'

        car = Car(
            model_name=model_name,
            price=float(price),
            location=location,
            driveable=driveable,
            user_id=current_user.id,
        )
        db.session.add(car)
        db.session.flush()  # get car.id before commit

        # Handle multiple images
        _save_images(request.files.getlist('images'), car)

        db.session.commit()
        flash('Car listed successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('add_car.html')


@app.route('/car/<int:car_id>')
def car_details(car_id):
    car = Car.query.get_or_404(car_id)
    return render_template('details.html', car=car)


@app.route('/my-listings')
@login_required
def my_listings():
    cars = Car.query.filter_by(user_id=current_user.id).order_by(Car.id.desc()).all()
    return render_template('my_listings.html', cars=cars)


@app.route('/car/<int:car_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_car(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        car.model_name = request.form.get('model_name', '').strip()
        car.price      = float(request.form.get('price', 0))
        car.location   = request.form.get('location', '').strip()
        car.driveable  = request.form.get('driveable') == 'yes'

        # Delete images the user chose to remove
        remove_ids = request.form.getlist('remove_images')  # list of CarImage ids
        for img_id in remove_ids:
            img = CarImage.query.get(int(img_id))
            if img and img.car_id == car.id:
                _delete_image_file(img.filename)
                db.session.delete(img)

        # Add newly uploaded images
        new_files = request.files.getlist('images')
        _save_images(new_files, car)

        db.session.commit()
        flash('Listing updated successfully!', 'success')
        return redirect(url_for('car_details', car_id=car.id))

    return render_template('edit_car.html', car=car)


@app.route('/car/<int:car_id>/delete', methods=['POST'])
@login_required
def delete_car(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id != current_user.id:
        abort(403)

    # Delete image files from disk
    for img in car.images:
        _delete_image_file(img.filename)

    db.session.delete(car)
    db.session.commit()
    flash('Listing deleted.', 'success')
    return redirect(url_for('my_listings'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_images(files, car):
    """Save a list of uploaded image files and attach them to car."""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    existing_count = len(car.images)
    for idx, file in enumerate(files):
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_name = f"car_{car.id}_{existing_count + idx}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            db.session.add(CarImage(car_id=car.id, filename=unique_name))


def _delete_image_file(filename):
    """Remove an image file from disk if it exists."""
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
