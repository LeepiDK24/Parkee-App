from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from  math import ceil
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    reservations = db.relationship('Reservation', backref='user', lazy=True)

class ParkingLot(db.Model):
    __tablename__ = "parking_lot"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    pin_code = db.Column(db.String(10))
    price_per_hour = db.Column(db.Float, nullable=False)
    max_spots = db.Column(db.Integer, nullable=False)
    spots = db.relationship("ParkingSpot", backref="lot", cascade="all, delete", lazy=True)

class ParkingSpot(db.Model):
    __tablename__ = "parking_spot"
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.String(1), default="A")  # A: available, O: occupied
    reservations = db.relationship("Reservation", backref="spot", lazy=True)

class Reservation(db.Model):
    __tablename__ = "reservation"
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    cost = db.Column(db.Float)


def create_auto_admin():
    if not User.query.filter_by(is_admin=True).first():
        admin = User(username='admin', password='passadmin', is_admin=True)
        db.session.add(admin)
        db.session.commit()

if not os.path.exists('database.db'):
    with app.app_context():
        db.create_all()
        create_auto_admin()

    
def current_user():
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

def login_required(role=None):
    def wrapper(fn):
        from functools import wraps
        @wraps(fn)
        def decorated(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for('login'))
            if role == 'admin' and not user.is_admin:
                return redirect(url_for('user_dashboard'))
            return fn(*args, **kwargs)
        return decorated
    return wrapper

@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    username = request.form.get('Fname')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
        session['user_id'] = user.id
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('login.html', error="Invalid credentials.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "GET":
        return render_template('signup.html')
    username = request.form.get('Fname')
    password = request.form.get('password')
    if User.query.filter_by(username=username).first():
        return render_template('signup.html', error="Username already exists.")
    user = User(username=username, password=password)
    db.session.add(user)
    db.session.commit()
    return redirect(url_for('login'))


@app.route('/admin')
@login_required('admin')
def admin_dashboard():
    lots = ParkingLot.query.all()
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin_dashboard.html', lots=lots, users=users)

@app.route('/admin/parking-lots/new', methods=['GET','POST'])
@login_required('admin')
def create_parking_lot():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        pin_code = request.form.get('pin_code')
        price_per_hour = float(request.form.get('price_per_hour'))
        max_spots = int(request.form.get('max_spots'))
        lot = ParkingLot(name=name, address=address, pin_code=pin_code, price_per_hour=price_per_hour, max_spots=max_spots)
        db.session.add(lot)
        db.session.commit()
        for _ in range(max_spots):
            spot = ParkingSpot(lot_id=lot.id)
            db.session.add(spot)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('parking_lot_form.html', lot=None)

@app.route('/admin/parking-lots/<int:lot_id>/edit', methods=['GET','POST'])
@login_required('admin')
def edit_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method == 'POST':
        lot.name = request.form.get('name')
        lot.address = request.form.get('address')
        lot.pin_code = request.form.get('pin_code')
        lot.price_per_hour = float(request.form.get('price_per_hour'))
        new_max_spots = int(request.form.get('max_spots'))
        current_spots = len(lot.spots)

        if new_max_spots > current_spots:
            for _ in range(new_max_spots - current_spots):
                db.session.add(ParkingSpot(lot_id=lot.id))
        elif new_max_spots < current_spots:
            available_spots = [spot for spot in lot.spots if spot.status == 'A']
            to_delete = min(len(available_spots), current_spots-new_max_spots)
            for spot in available_spots[:to_delete]:
                db.session.delete(spot)
        lot.max_spots = new_max_spots
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('parking_lot_form.html', lot=lot)

@app.route('/admin/parking-lots/<int:lot_id>/delete', methods=['POST'])
@login_required('admin')
def delete_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    if all(spot.status == 'A' for spot in lot.spots):
        db.session.delete(lot)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return "Cannot delete lot while any spots are occupied", 400

@app.route('/admin/users')
@login_required('admin')
def admin_users():
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin_users.html', users=users)


@app.route('/user')
@login_required()
def user_dashboard():
    user = current_user()
    reservations = Reservation.query.filter_by(user_id=user.id).all()
    return render_template('user_dashboard.html', reservations=reservations)

@app.route('/lots')
@login_required()
def user_parking_lots():
    lots = ParkingLot.query.all()
    return render_template('user_parking_lots.html', lots=lots)

@app.route('/reserve/<int:lot_id>', methods=['POST'])
@login_required()
def reserve_spot(lot_id):
    user = current_user()
    lot = ParkingLot.query.get_or_404(lot_id)
    available_spot = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').first()
    if not available_spot:
        return "No available spot in this lot.", 400
    available_spot.status = "O"
    reservation = Reservation(
        spot_id=available_spot.id,
        user_id=user.id,
        start_time=datetime.now()
    )
    db.session.add(reservation)
    db.session.commit()
    return redirect(url_for('user_dashboard'))

@app.route('/vacate/<int:reservation_id>', methods=['POST'])
@login_required()
def vacate_spot(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    spot = reservation.spot
    lot = spot.lot
    if reservation.end_time is not None:
        return "Already vacated!", 400
    reservation.end_time = datetime.now()
    duration_seconds = (reservation.end_time - reservation.start_time).total_seconds()
    duration_hours = duration_seconds / 3600
    hours_charged = max(ceil(duration_hours), 1)
    reservation.cost = round(hours_charged * lot.price_per_hour, 2)
    spot.status = 'A'
    db.session.commit()
    return redirect(url_for('user_dashboard'))

@app.route('/history')
@login_required()
def reservation_history():
    user = current_user()
    reservations = Reservation.query.filter_by(user_id=user.id).all()
    return render_template('reservation_history.html', reservations=reservations)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_auto_admin()
    app.run(debug=True)

