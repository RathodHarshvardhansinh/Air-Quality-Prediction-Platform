import sqlite3

DATABASE = "airsense.db"


NEW_COLUMNS = {
    "pm25": "REAL",
    "pm10": "REAL",
    "no2": "REAL",
    "co": "REAL",
    "o3": "REAL",
    "so2": "REAL",
}


connection = sqlite3.connect(DATABASE)

cursor = connection.cursor()


# Get existing columns
cursor.execute(
    "PRAGMA table_info(environment_data)"
)

existing_columns = {
    row[1]
    for row in cursor.fetchall()
}


print("Existing columns:")
print(existing_columns)


# Add missing columns
for column, data_type in NEW_COLUMNS.items():

    if column not in existing_columns:

        cursor.execute(
            f"""
            ALTER TABLE environment_data
            ADD COLUMN {column} {data_type}
            """
        )

        print(f"Added column: {column}")

    else:

        print(f"Already exists: {column}")


connection.commit()

connection.close()


print("\nDatabase migration completed!")