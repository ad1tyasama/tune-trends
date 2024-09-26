import sqlite3

# Define the database filename
database_filename = 'sessions.db'

# Connect to the SQLite database (this will create the file if it doesn't exist)
conn = sqlite3.connect(database_filename)

# Create a cursor object to execute SQL commands
cursor = conn.cursor()

# Define the SQL command to create a table for session data
create_table_sql = """
CREATE TABLE IF NOT EXISTS session_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    data BLOB NOT NULL
)
"""

# Execute the SQL command to create the table
cursor.execute(create_table_sql)

# Commit the changes and close the database connection
conn.commit()
conn.close()

print(f"SQLite database '{database_filename}' and 'session_data' table created.")