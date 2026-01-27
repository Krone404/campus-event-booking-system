# Cloud Event Booking System (Flask + Google Cloud)

A cloud-hosted web application for creating and booking events, deployed on **Google App Engine**.  
It includes **user authentication**, **admin-only event creation**, **PostgreSQL (Cloud SQL)** for core data, **Firestore** for audit logging, **REST endpoints**, an **HTTP Cloud Function integration**, and **Google Maps** support for event location display.

---

## Features

- User registration, login, logout
- Role-based access (admin-only event creation)
- Create events with time, capacity, description, and map location (lat/lng)
- Book events (capacity enforced)
- Ticket codes generated per booking
- Audit logging to Firestore (e.g., user_registered, event_created, booking_created)
- Cloud deployment on App Engine Standard
- Cloud Function call integration (for extended functionality)
- REST API routes (where implemented)

---

## Tech Stack

- **Backend:** Python, Flask, Jinja2
- **Auth:** Flask-Login
- **SQL DB:** PostgreSQL (Google Cloud SQL) via SQLAlchemy
- **NoSQL DB:** Google Firestore (audit/event logging)
- **Cloud Hosting:** Google App Engine Standard
- **Cloud Functions:** HTTP-triggered function (used by the app)
- **Maps:** Google Maps API (JavaScript API for map display)

---

## Project Structure

```

├── app
│   ├── config.py
│   ├── extensions.py
│   ├── __init__.py
│   ├── models.py
│   ├── __pycache__
│   │   ├── config.cpython-312.pyc
│   │   ├── extensions.cpython-312.pyc
│   │   ├── __init__.cpython-312.pyc
│   │   ├── models.cpython-312.pyc
│   │   └── security.cpython-312.pyc
│   ├── routes
│   │   ├── api.py
│   │   ├── auth.py
│   │   ├── debug.py
│   │   ├── events.py
│   │   └── __pycache__
│   │       ├── api.cpython-312.pyc
│   │       ├── auth.cpython-312.pyc
│   │       ├── debug.cpython-312.pyc
│   │       ├── events.cpython-312.pyc
│   │       └── __init__.cpython-312.pyc
│   ├── security.py
│   ├── services
│   │   ├── logging_service.py
│   │   └── __pycache__
│   │       └── logging_service.cpython-312.pyc
│   ├── static
│   │   └── style.css
│   └── templates
│       ├── auth
│       │   ├── login.html
│       │   ├── me.html
│       │   └── register.html
│       ├── base.html
│       └── events
│           ├── detail.html
│           ├── list.html
│           └── new.html
├── app.yaml
├── app.yaml.example
├── cloud-sql-proxy
├── functions
│   ├── checkin_validate
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── generate_ticket_qr
│   │   ├── main.py
│   │   └── requirements.txt
│   └── send_booking_email
│       ├── main.py
│       └── requirements.txt
├── main.py
├── __pycache__
│   └── main.cpython-312.pyc
├── README.md
├── requirements.txt
└── tests
    ├── base.py
    ├── __init__.py
    ├── __pycache__
    │   ├── base.cpython-312.pyc
    │   ├── __init__.cpython-312.pyc
    │   ├── test_api.cpython-312.pyc
    │   ├── test_auth.cpython-312.pyc
    │   └── test_booking.cpython-312.pyc
    ├── test_api.py
    ├── test_auth.py
    └── test_booking.py

````

---

## Getting Started (Local Development)

### 1) Create a virtual environment & install dependencies

```bash
# Cloud Shell / macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell): .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
````

### 2) Set environment variables

Create a `.env` file locally (do **not** commit it), or export environment variables in your shell.

Minimum recommended variables (names may vary depending on your config):

```bash
export FLASK_SECRET_KEY="change-me"
export DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME"
export MAPS_API_KEY="your-google-maps-key"
export SHOW_DEBUG="0"
```

If your app calls a Cloud Function, you will also need:

```bash
export CHECKIN_FUNCTION_URL="https://REGION-PROJECT.cloudfunctions.net/FUNCTION_NAME"
```

> If your code uses different variable names, update the values to match `app/config.py` and any route/service modules.

### 3) Run the app locally

```bash
python main.py
```

Then open:

* `http://127.0.0.1:8080/` (or the port shown in your terminal)

---

## Database Setup

### Cloud SQL (PostgreSQL)

This project expects a PostgreSQL database with tables for:

* `users`
* `events`
* `bookings`

How you create tables depends on how your repo currently handles schema:

* If you have a `schema.sql`, apply it with `psql`.
* If you use SQLAlchemy model creation, ensure you run the relevant init step (if present).

> Tip: If you need to wipe `events` + `bookings` and reset IDs:

```sql
TRUNCATE TABLE bookings, events RESTART IDENTITY CASCADE;
```

---

## Admin Access

Event creation is restricted to users with:

* `role == "admin"`

How you set an admin depends on your database and models:

* You can update a user’s role directly in SQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your-email@example.com';
```

---

## Deployment (Google App Engine)

### 1) Configure App Engine

Copy `app.yaml.example` → `app.yaml` and update settings as required:

```bash
cp app.yaml.example app.yaml
```

### 2) Deploy

```bash
gcloud app deploy
gcloud app browse
```

> Ensure required environment variables are configured for the deployed service (App Engine settings / runtime env).

---

## Firestore Logging

Audit logs are written to Firestore via `app/services/logging_service.py`.
Typical event types:

* `user_registered`
* `user_login`
* `user_logout`
* `event_created`
* `booking_created`

---

## REST API

API routes live in:

* `app/routes/api.py`

Use Postman or curl for testing (example):

```bash
curl -i http://127.0.0.1:8080/api/health
```

(Replace with your actual endpoints implemented in `api.py`.)

---

## Testing

If tests are included in your repo, run them with:

```bash
pytest
```

---

## Common Issues

### Maps not showing

* Ensure `MAPS_API_KEY` is set
* Ensure the event has `lat` and `lng` stored
* Confirm the Maps API is enabled in Google Cloud Console

### Cloud SQL connection errors

* Confirm `DATABASE_URL` is correct
* Ensure Cloud SQL instance is reachable (connector/proxy if required)
* Verify firewall/authorized networks if using IP access
