import mysql.connector
from mysql.connector import Error

# Database config
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "block_private"
}

def create_connection():
    """Create a database connection."""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print(f"✅ Connected to MySQL database: {DB_CONFIG['database']}")
            return connection
    except Error as e:
        print("❌ Error connecting to MySQL:", e)
    return None

def close_connection(connection):
    """Close the database connection."""
    if connection and connection.is_connected():
        connection.close()
        print("🔌 Connection closed.")

# Run this file directly to test
if __name__ == "__main__":
    conn = create_connection()
    close_connection(conn)
