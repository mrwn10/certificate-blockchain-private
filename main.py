from flask import Flask, render_template
from database import create_connection, close_connection
from create_cert import create_cert_bp
import os

app = Flask(__name__)

# Add secret key for session management (required for flash messages)
app.secret_key = '123'  # ← ADD THIS LINE

app.register_blueprint(create_cert_bp)

# Home route
@app.route("/")
def home():
    # test database connection
    conn = create_connection()
    if conn:
        print("Database is working inside main.py ✅")
        close_connection(conn)
    return render_template("homepage.html")

if __name__ == "__main__":
    app.run(debug=True)