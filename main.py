import os
import json
import requests
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreateRegForm, CreateLoginForm
from cachelib import SimpleCache 

# --- App Configuration ---
app = Flask(__name__)

app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap5(app)

# --- Caching Setup ---
cache = SimpleCache()
CACHE_TIMEOUT = 300  

# --- OpenWeatherMap API ---
API_KEY = "c47cee32692a452f9b5663107eb0878e"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to login page if not authenticated

# --- Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
# Use a different DB name for clarity
db_path = os.path.join(basedir, 'instance', 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create instance folder if it doesn't exist
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

db = SQLAlchemy(app)

# --- User Model ---
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id)) 


# --- Helper Functions ---
def get_city_codes():
    """Reads city codes from cities.json."""
    city_codes = cache.get("city_codes")
    if city_codes is None:
        try:
            with open("cities.json", 'r', encoding='utf-8') as f: # Added encoding='utf-8' for broader compatibility
                data = json.load(f)
                # Access the list using the "List" key
                cities_list = data.get("List", []) # Use .get with a default empty list
                if not cities_list:
                     flash("Error: 'List' key not found or empty in cities.json.", "error")
                     return []

                city_codes = [city.get("CityCode") for city in cities_list if "CityCode" in city]

                cache.set("city_codes", city_codes, timeout=3600) # Cache for 1 hour
                print("City codes loaded from file and cached.") # For debugging

        except FileNotFoundError:
            flash("Error: cities.json not found.", "error")
            return []
        except json.JSONDecodeError:
            flash("Error: Could not parse cities.json.", "error")
            return []
        except KeyError:
             flash("Error: Malformed JSON structure in cities.json. Expected 'List' key.", "error")
             return []
    else:
        print("City codes retrieved from cache.") 


    if not city_codes:
        flash("Warning: No valid CityCodes found in cities.json.", "warning")

    return city_codes

def get_weather_data(city_id):
    """Fetches weather data for a city_id, using cache."""
    cache_key = f"weather_{city_id}"
    weather_data = cache.get(cache_key)

    if weather_data is None:
        params = {
            "id": city_id, 
            "appid": API_KEY, 
            "units": "metric" 
        }
        try:
            response = requests.get(WEATHER_URL, params=params)
            response.raise_for_status() 
            data = response.json()

            weather_data = {
                "id": city_id,
                "name": data.get("name"),
                "description": data["weather"][0].get("description") if data.get("weather") else "N/A",
                "temp": data["main"].get("temp") if data.get("main") else "N/A",
                "icon": data["weather"][0].get("icon") if data.get("weather") else None,
            }
            cache.set(cache_key, weather_data, timeout=CACHE_TIMEOUT) # Cache for 5 minutes
            print(f"Fetched from API for {city_id}") # For debugging
        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather for {city_id}: {e}") # Log error
            return None # Return None on error
        except (KeyError, IndexError) as e:
            print(f"Error parsing weather data for {city_id}: {e}") # Log error
            return None # Return None on error
    else:
        print(f"Fetched from CACHE for {city_id}") # For debugging

    return weather_data

# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('show_weather'))
    form = CreateLoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('show_weather')) # Redirect to weather page
        else:
            flash('Invalid email or password.', 'error')
    return render_template("login.html", form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('show_weather'))
    form = CreateRegForm()
    if form.validate_on_submit():
        existing_user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if existing_user:
            flash("Email already registered. Please log in instead.", 'warning')
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Registration successful!', 'success')
        return redirect(url_for('show_weather')) # Redirect to weather page

    return render_template("register.html", form=form)

@app.route('/logout')
@login_required
def logout():

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login')) # Redirect to login page

@app.route('/weather')
@login_required
def show_weather():
    """Displays weather cards for cities."""
    city_codes = get_city_codes()
    weather_cards = []
    if not city_codes:
        flash("Could not load city codes.", "error")
    else:
        for code in city_codes:
            weather_info = get_weather_data(code)
            if weather_info: # Only add if data was fetched successfully
                weather_cards.append(weather_info)
            else:
                 flash(f"Could not fetch weather data for city code {code}.", "warning")


    return render_template("index.html", all_weather_city=weather_cards)

@app.route('/city/<int:city_id>')
@login_required # Protect this route
def show_city_detail(city_id):
    """Displays more details for a specific city."""
    # For now, just refetch the same basic data.
    # Later, you could fetch a more detailed forecast here.
    city_data = get_weather_data(city_id)
    if not city_data:
        flash(f"Could not retrieve weather data for city ID {city_id}.", "error")
        return redirect(url_for('show_weather'))

    # You might want to fetch forecast data here in a real app
    # forecast_url = "..."
    # forecast_params = {"id": city_id, ...}
    # forecast_response = requests.get(forecast_url, params=forecast_params)
    # forecast_data = forecast_response.json()

    return render_template("city_detail.html", city=city_data) # Pass data to the detail template


# --- Main Execution ---
if __name__ == "__main__":
    with app.app_context():
        # Check if the database file exists before creating tables
        if not os.path.exists(db_path):
             db.create_all()
             print("Db/tables created.")
        else:
             print("Db found.")
    app.run(debug=True, port=5002)