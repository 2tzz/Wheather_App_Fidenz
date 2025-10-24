# Flask Weather Dashboard 🌤️

A simple web application built with **Flask** that allows users to register, log in, and create a personal dashboard of weather information for cities they follow.  
It uses the **OpenWeatherMap API** and caches results for 5 minutes to reduce API calls.

---

## 🌟 Features

- **User Authentication:** Full user registration and login system (Flask-Login).  
- **Personalized Dashboard:** Users can add and delete cities to create a custom dashboard.  
- **Live Weather Data:** Fetches current weather from the OpenWeatherMap API.  
- **Detailed View:** Clickable weather cards to see a more detailed forecast view.  
- **API Caching:** Caches API results for 5 minutes to improve performance and stay within API rate limits.

---

## 🧰 Prerequisites

Before you begin, ensure you have the following installed:

- [Git](https://git-scm.com/)
- [Python 3.10+](https://www.python.org/)

---

## 🚀 Setup & Installation

Follow these steps to get your local development environment up and running.

### 1. Clone the Repository

First, clone this repository to your local machine.

```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/2tzz/Wheather_App_Fidenz.git)

```

2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies

```
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
.\venv\Scripts\activate

```
3. Install Dependencies

This project uses a requirements.txt file to manage all necessary Python packages.

```
pip install -r requirements.txt

```

4. Configure Environment Variables

The application requires API keys to function.

Create a new file named .env in the root of your project directory and add the following:
```
# Get this from your OpenWeatherMap account
API_KEY="XXXXXXXXXXXX"

# A random, long string for Flask's session security
APP_SECRET="XXXXXXXXXXXX"

```
Note: For a production environment, replace APP_SECRET with a new, securely generated random string.

🔐 Auth0 Setup (Required for Login)

This project uses Auth0 for user authentication.
Follow these steps to configure it:

Go to the Auth0 Dashboard:
https://auth0.com/

Create a new Regular Web Application

Go to:
Application → Settings

Enable the following URLs:

Allowed Callback URLs

http://127.0.0.1:5002/callback


Allowed Logout URLs

http://127.0.0.1:5002, http://127.0.0.1:5002/login


Allowed Web Origins

http://127.0.0.1:5002

🛠️ Add Auth0 Credentials to .env

Open your .env file and add these lines 👇

# --- Auth0 Credentials ---
AUTH0_DOMAIN="YOUR_AUTH0_DOMAIN"
AUTH0_CLIENT_ID="YOUR_AUTH0_CLIENT_ID"
AUTH0_CLIENT_SECRET="YOUR_AUTH0_CLIENT_SECRET"

# Example:
# AUTH0_DOMAIN="dev-xxxxxx.auth0.com"


✅ Make sure to replace the placeholders with values from your Auth0 application settings page.

🏃‍♂️ Running the Application

Once the installation and configuration are complete, you can run the app.

Run the Flask server:
```
python main.py

```

The first time you run this, the script will automatically create an instance/users.db file to store user and city data.

Now, open your browser and visit:

👉 http://127.0.0.1:5002

You should see the login page.
Register a new account and start adding cities to your personal weather dashboard!

Made with ❤️ using Flask

