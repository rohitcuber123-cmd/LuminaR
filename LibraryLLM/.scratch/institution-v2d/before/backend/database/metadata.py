import duckdb


DB_PATH = r"D:\SDC\LibraryLLM\datasets\ai\metadata\book_metadata.duckdb"


def get_connection():
    return duckdb.connect(
        DB_PATH,
        read_only=True
    )