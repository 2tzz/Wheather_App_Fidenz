# main.py
import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreateRegForm, CreateLoginForm
from cachelib import SimpleCache

load_dotenv()

my_seacret = os.getenv('APP_SECRET')
my_weather_api_key = os.getenv('API_KEY')

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = my_seacret
Bootstrap5(app)

# --- Caching Setup ---
cache = SimpleCache()
CACHE_TIMEOUT = 300  # 5 minutes in seconds

# --- OpenWeatherMap API ---
API_KEY = my_weather_api_key
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated

# --- Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create instance folder if it doesn't exist
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

db = SQLAlchemy(app)


# --- Database Models ---
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    
    # This links the User to their list of cities
    cities = relationship("UserCity", back_populates="user")


class UserCity(db.Model):
    __tablename__ = "user_cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # This is the OpenWeatherMap city ID
    city_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # This links to the user
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="cities")


# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- Helper Functions ---

def format_timestamp(timestamp_utc, offset_seconds):
    """Converts UTC timestamp + offset to formatted local time string."""
    if timestamp_utc is None or offset_seconds is None:
        return "N/A"
    try:
        local_tz = timezone(timedelta(seconds=offset_seconds))
        local_time = datetime.fromtimestamp(timestamp_utc, tz=timezone.utc).astimezone(local_tz)
        current_time_utc = datetime.now(timezone.utc).timestamp()
        
        if abs(current_time_utc - timestamp_utc) < 7200:  # 2-hour window
            return local_time.strftime("%I:%M%p, %b %d").lower().lstrip('0').replace(':00', '')
        else:  # For sunrise/sunset, just show time
            return local_time.strftime("%I:%M%p").lower().lstrip('0').replace(':00', '')
            
    except Exception as e:
        print(f"Error formatting timestamp {timestamp_utc} with offset {offset_seconds}: {e}")
        return "N/A"


def find_city_by_name(city_name):
    """Searches the API for a city name and returns its ID."""
    params = {
        "q": city_name,
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(WEATHER_URL, params=params)
        response.raise_for_status()  # Raise error for 4xx/5xx
        data = response.json()
        
        if data.get("cod") == 200:
            return data.get("id")  # Return the city ID
        else:
            return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"City not found: {city_name}")
        else:
            print(f"HTTP Error finding city {city_name}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error finding city {city_name}: {e}")
        return None


def get_weather_data(city_id):
    """Fetches weather data for a city_id, using cache, including more details."""
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
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            if data.get("cod") != 200:
                print(f"API error for city {city_id}: {data.get('message', 'Unknown error')}")
                return None  # Return None to skip this card

            main_data = data.get("main", {})
            sys_data = data.get("sys", {})
            wind_data = data.get("wind", {})
            weather_list = data.get("weather", [])
            weather_main = weather_list[0] if weather_list else {}  # Get first item or empty dict

            timezone_offset = data.get('timezone')  # Offset in seconds from UTC

            temp = main_data.get("temp")
            temp_min = main_data.get("temp_min")
            temp_max = main_data.get("temp_max")
            visibility_m = data.get("visibility")  # Visibility in meters
            wind_speed_ms = wind_data.get("speed")  # Wind speed in m/s
            dt_utc = data.get("dt")  
            sunrise_utc = sys_data.get("sunrise")
            sunset_utc = sys_data.get("sunset")

            weather_data = {
                "id": city_id,  
                "name": data.get("name", "N/A"),
                "country": sys_data.get("country", ""),
                "description": weather_main.get("description", "N/A"),
                "temp": temp,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "icon": weather_main.get("icon"),
                "pressure": main_data.get("pressure", "N/A"),
                "humidity": main_data.get("humidity", "N/A"),
                "visibility": f"{visibility_m / 1000.0:.1f}" if isinstance(visibility_m, (int, float)) else "N/A",
                "wind_speed": f"{wind_speed_ms }" if isinstance(wind_speed_ms, (int, float)) else "N/A",
                "dt_formatted": format_timestamp(dt_utc, timezone_offset),
                "sunrise_formatted": format_timestamp(sunrise_utc, timezone_offset),
                "sunset_formatted": format_timestamp(sunset_utc, timezone_offset),
            }
            
            cache.set(cache_key, weather_data, timeout=CACHE_TIMEOUT)
            print(f"Fetched from API for {city_id}")

        except requests.exceptions.RequestException as e:
            print(f"HTTP Error fetching weather for {city_id}: {e}")
            return None
        except (json.JSONDecodeError, IndexError, TypeError) as e:  # Parsing error
            print(f"Error parsing weather data for {city_id}: {e}")
            return None
    else:
        print(f"Fetched from CACHE for {city_id}")

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
            return redirect(url_for('show_weather'))  
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
        return redirect(url_for('show_weather'))  # Redirect to weather page

    return render_template("register.html", form=form)


@app.route('/logout')
@login_required
def logout():
    """Logs the user out."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))  # Redirect to login page


@app.route('/add_city', methods=['POST'])
@login_required
def add_city():
    city_name = request.form.get("city_name")
    if not city_name:
        flash("You must enter a city name.", "error")
        return redirect(url_for('show_weather'))

    city_id = find_city_by_name(city_name)
    
    if city_id:
        # Check if user already has this city
        existing = db.session.execute(db.select(UserCity).where(
            UserCity.user_id == current_user.id,
            UserCity.city_id == city_id
        )).scalar()
        
        if existing:
            flash(f"{city_name} is already in your list.", "warning")
        else:
            # Add new city to database for this user
            new_city_for_user = UserCity(
                city_id=city_id,
                user_id=current_user.id
            )
            db.session.add(new_city_for_user)
            db.session.commit()
            flash(f"Added {city_name} to your dashboard.", "success")
            
    else:
        flash(f"Could not find a city named '{city_name}'.", "error")
        
    return redirect(url_for('show_weather'))


@app.route('/delete_city/<int:city_id>')
@login_required
def delete_city(city_id):
    # Find the specific city entry for this user
    city_to_delete = db.session.execute(db.select(UserCity).where(
        UserCity.user_id == current_user.id,
        UserCity.city_id == city_id
    )).scalar_one_or_none()
    
    if city_to_delete:
        db.session.delete(city_to_delete)
        db.session.commit()
        flash("City removed.", "success")
    else:
        flash("City not found or you do not have permission to remove it.", "error")
        
    return redirect(url_for('show_weather'))


@app.route('/weather')
@login_required  # Protect this route
def show_weather():
    """Displays weather cards for the logged-in user's cities."""
    
    user_cities = db.session.execute(
        db.select(UserCity).where(UserCity.user_id == current_user.id)
    ).scalars().all()
    

    city_codes = [city.city_id for city in user_cities]

    weather_cards = []
    if not city_codes:
        # Updated flash message
        flash("Your dashboard is empty. Add a city using the search bar!", "info")
    else:
        for code in city_codes:
            weather_info = get_weather_data(code)
            if weather_info:  
                weather_cards.append(weather_info)
            else:
                flash(f"Could not fetch weather data for city code {code}.", "warning")

    return render_template("index.html", all_weather_city=weather_cards)


@app.route('/city/<int:city_id>')
@login_required  # Protect this route
def show_city_detail(city_id):
    """Displays more details for a specific city."""
    city_data = get_weather_data(city_id)
    if not city_data:
        flash(f"Could not retrieve weather data for city ID {city_id}.", "error")
        return redirect(url_for('show_weather'))

    return render_template("city_detail.html", city=city_data)


# --- Main Execution ---
if __name__ == "__main__":
    with app.app_context():
        if not os.path.exists(db_path):
            print("Database not found, creating tables...")
            db.create_all()  
            print("Database and tables created.")
        else:
            db.create_all()  
            print("Database found. Ensured all tables exist.")
    app.run(debug=True, port=5002)