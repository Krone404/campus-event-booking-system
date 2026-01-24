import os
from flask import Flask

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-change-me")

@app.get("/")
def home():
    return "Campus Events system is running ✅"
