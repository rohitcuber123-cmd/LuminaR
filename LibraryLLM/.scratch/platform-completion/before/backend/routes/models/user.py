from backend.database.app_database import get_connection


def create_users_table():

    connection = get_connection()

    try:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (

                user_id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,

                email TEXT NOT NULL UNIQUE,

                password_hash TEXT NOT NULL,

                role TEXT NOT NULL DEFAULT 'GENERAL_USER',

                is_email_verified INTEGER NOT NULL DEFAULT 0,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            )
        """)

        connection.commit()

    finally:

        connection.close()