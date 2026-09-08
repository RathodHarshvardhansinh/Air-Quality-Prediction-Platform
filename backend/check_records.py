import sqlite3

connection = sqlite3.connect("airsense.db")
cursor = connection.cursor()

cursor.execute(
    "SELECT COUNT(*) FROM environment_data WHERE LOWER(city) = LOWER(?)",
    ("Visnagar",)
)

count = cursor.fetchone()[0]

print("Visnagar records:", count)

connection.close()