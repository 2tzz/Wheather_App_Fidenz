import os
import json
import requests
import dotenv
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, abort, request, session, g
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from cachelib import SimpleCache
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode, quote

# --- Load Environment Variables ---
dotenv.load_dotenv()

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('APP_SECRET')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
Bootstrap5(app)

# --- Caching Setup ---
cache = SimpleCache()
CACHE_TIMEOUT = 300  # seconds

# --- OpenWeatherMap API ---
API_KEY = os.getenv("API_KEY")
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

# --- Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'users.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
db = SQLAlchemy(app)

# --- Auth0 OAuth Configuration ---
oauth = OAuth(app)
oauth.register(
    "auth0",
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{os.getenv("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)

# --- Database Models ---

class User(db.Model):
    __tablename__ = "users"
    sub: Mapped[str] = mapped_column(String(250), primary_key=True)
    username: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    cities = relationship("UserCity", back_populates="user", cascade="all, delete-orphan")


class UserCity(db.Model):
    __tablename__ = "user_cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(250), ForeignKey("users.sub"))
    user = relationship("User", back_populates="cities")


# --- Auth0 Helper Functions ---

def get_or_create_user(auth0_user_info):
    user_sub = auth0_user_info['sub']
    user = db.session.get(User, user_sub)

    if not user:
        user = User(
            sub=user_sub,
            username=auth0_user_info.get('name', auth0_user_info.get('email')),
            email=auth0_user_info.get('email')
        )
        db.session.add(user)
        db.session.commit()
    return user


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))

        auth0_user_info = session["user"]
        user = db.session.get(User, auth0_user_info['sub'])
        if not user:
            session.clear()
            flash("User not found, please log in again.", "warning")
            return redirect(url_for('login'))

        g.user = user
        return f(*args, **kwargs)
    return decorated


@app.before_request
def load_current_user():
    g.user = None
    if "user" in session:
        auth0_user_info = session["user"]
        user = db.session.get(User, auth0_user_info['sub'])
        if user:
            g.user = user


# --- Helper Functions (Weather) ---

def format_timestamp(timestamp_utc, offset_seconds):
    if timestamp_utc is None or offset_seconds is None:
        return "N/A"
    try:
        local_tz = timezone(timedelta(seconds=offset_seconds))
        local_time = datetime.fromtimestamp(timestamp_utc, tz=timezone.utc).astimezone(local_tz)
        formatted = local_time.strftime("%I:%M%p, %b %d").lower().lstrip('0')
        formatted = formatted.replace(":00", "")
        return formatted
    except Exception as e:
        print(f"Error formatting timestamp {timestamp_utc} with offset {offset_seconds}: {e}")
        return "N/A"


def find_city_by_name(city_name):
    params = {"q": city_name, "appid": API_KEY, "units": "metric"}
    try:
        response = requests.get(WEATHER_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        try:
            cod = int(data.get("cod", 0))
        except (TypeError, ValueError):
            cod = 0

        if cod == 200:
            return data.get("id")
        else:
            return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error finding city {city_name}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Network error finding city {city_name}: {e}")
        return None


def get_weather_data(city_id):
    cache_key = f"weather_{city_id}"
    weather_data = cache.get(cache_key)
    if weather_data is None:
        params = {"id": city_id, "appid": API_KEY, "units": "metric"}
        try:
            response = requests.get(WEATHER_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            try:
                cod = int(data.get("cod", 0))
            except (TypeError, ValueError):
                cod = 0

            if cod != 200:
                return None

            main_data = data.get("main", {})
            sys_data = data.get("sys", {})
            wind_data = data.get("wind", {})
            weather_list = data.get("weather", [])
            weather_main = weather_list[0] if weather_list else {}
            timezone_offset = data.get('timezone', 0)
            temp = main_data.get("temp")
            temp_min = main_data.get("temp_min")
            temp_max = main_data.get("temp_max")
            visibility_m = data.get("visibility")
            wind_speed_ms = wind_data.get("speed")
            dt_utc = data.get("dt")
            sunrise_utc = sys_data.get("sunrise")
            sunset_utc = sys_data.get("sunset")

            weather_data = {
                "id": data.get("id", city_id),
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
                "wind_speed": f"{wind_speed_ms}" if isinstance(wind_speed_ms, (int, float)) else "N/A",
                "dt_formatted": format_timestamp(dt_utc, timezone_offset),
                "sunrise_formatted": format_timestamp(sunrise_utc, timezone_offset),
                "sunset_formatted": format_timestamp(sunset_utc, timezone_offset),
            }
            cache.set(cache_key, weather_data, timeout=CACHE_TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(f"HTTP Error fetching weather for {city_id}: {e}")
            return None
        except (json.JSONDecodeError, IndexError, TypeError) as e:
            print(f"Error parsing weather data for {city_id}: {e}")
            return None
            
    return weather_data


# --- Routes ---

@app.route('/')
def index():
    if g.user:
        return redirect(url_for('show_weather'))
    return redirect(url_for('login'))


@app.route('/login')
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route('/callback', methods=['GET', 'POST'])
def callback():
    token = oauth.auth0.authorize_access_token()
    auth0_user_info = token.get('userinfo') or token.get('id_token_claims') or {}
    
    if not auth0_user_info:
        flash("Could not retrieve user info from Auth0.", "error")
        return redirect(url_for('index'))

    user = get_or_create_user(auth0_user_info)
    session["user"] = auth0_user_info

    flash('Logged in successfully.', 'success')
    return redirect(url_for('show_weather'))


@app.route('/logout')
def logout():
    session.clear() 

    domain = os.getenv('AUTH0_DOMAIN')
    client_id = os.getenv('AUTH0_CLIENT_ID')
    return_to = url_for('login', _external=True) 

    logout_url = f'https://{domain}/v2/logout?' + urlencode(
        {'returnTo': return_to, 'client_id': client_id},
        quote_via=quote
    )
    return redirect(logout_url)


@app.route('/add_city', methods=['POST'])
@requires_auth
def add_city():
    city_name = request.form.get("city_name")
    if not city_name:
        flash("You must enter a city name.", "error")
        return redirect(url_for('show_weather'))

    city_id = find_city_by_name(city_name)

    if city_id:
        existing = db.session.execute(
            db.select(UserCity).where(
                UserCity.user_id == g.user.sub,
                UserCity.city_id == city_id
            )
        ).scalar_one_or_none()

        if existing:
            flash(f"{city_name} is already in your list.", "warning")
        else:
            new_city_for_user = UserCity(
                city_id=city_id,
                user_id=g.user.sub
            )
            db.session.add(new_city_for_user)
            db.session.commit()
            flash(f"Added {city_name} to your dashboard.", "success")
    else:
        flash(f"Could not find a city named '{city_name}'.", "error")
    return redirect(url_for('show_weather'))


@app.route('/delete_city/<int:city_id>')
@requires_auth
def delete_city(city_id):
    city_to_delete = db.session.execute(
        db.select(UserCity).where(
            UserCity.user_id == g.user.sub,
            UserCity.city_id == city_id
        )
    ).scalar_one_or_none()

    if city_to_delete:
        db.session.delete(city_to_delete)
        db.session.commit()
        flash("City removed.", "success")
    else:
        flash("City not found or you do not have permission to remove it.", "error")
    return redirect(url_for('show_weather'))


@app.route('/weather')
@requires_auth
def show_weather():
    user_cities = db.session.execute(
        db.select(UserCity).where(UserCity.user_id == g.user.sub)
    ).scalars().all()

    city_codes = [city.city_id for city in user_cities]
    weather_cards = []

    if not city_codes:
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
@requires_auth
def show_city_detail(city_id):
    city_data = get_weather_data(city_id)
    if not city_data:
        flash(f"Could not retrieve weather data for city ID {city_id}.", "error")
        return redirect(url_for('show_weather'))
    return render_template("city_detail.html", city=city_data)


# --- Main Execution ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all() 
    app.run(port=5002)