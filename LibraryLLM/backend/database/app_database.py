import sqlite3

DB_PATH = r"D:\SDC\LibraryLLM\datasets\library.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    return connection