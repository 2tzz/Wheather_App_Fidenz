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
- An API Key from [OpenWeatherMap](https://openweathermap.org/api)

---

## 🚀 Setup & Installation

Follow these steps to get your local development environment up and running.

### 1. Clone the Repository

First, clone this repository to your local machine.

```bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/2tzz/Wheather_App_Fidenz.git)

# Navigate into the project directory
cd your-repo-name
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
API_KEY="c47cee32692a452f9b5663107eb0878e"

# A random, long string for Flask's session security
APP_SECRET="8BYkEfBA6O6donzWlSihBXox7C0sKR6b"

```
Note: For a production environment, replace APP_SECRET with a new, securely generated random string.

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

