from backend.database.mongodb import (
    books_collection,
    book_categories_collection
)


# ============================================================
# SUBJECTS THAT SHOULD NOT APPEAR AS HOME PAGE CATEGORIES
# ============================================================

EXCLUDED_SUBJECTS = {
    "General",
    "Congresses",
    "Exhibitions",
    "United States",
    "Large type books",
    "Early works to 1800",
    "Handbooks, manuals",
    "Dictionaries",
    "Catalogs",
    "Sources",
    "History and criticism",
    "Social life and customs",
    "Social conditions",
    "Social aspects",
    "Criticism and interpretation",
    "Pictorial works",
    "Description and travel",
    "Histoire",
    "Study and teaching",
    "Bibliography",
    "Religious aspects",
    "Antiquities",
    "Nonfiction",
    "English language",
    "Foreign relations",
    "Man-woman relationships"
}


# ============================================================
# BUILD CATEGORY CACHE
# ============================================================

def build_categories():

    print()
    print("=" * 60)
    print("LUMINA R CATEGORY CACHE BUILDER")
    print("=" * 60)
    print()

    print(
        "Starting category aggregation..."
    )

    print(
        "The first build may take a while "
        "because the database contains "
        "approximately 5 million books."
    )

    print()

    pipeline = [

        # ----------------------------------------------------
        # 1. Only books containing subjects
        # ----------------------------------------------------

        {
            "$match": {
                "subjects": {
                    "$exists": True,
                    "$nin": [
                        None,
                        ""
                    ]
                }
            }
        },

        # ----------------------------------------------------
        # 2. Keep only fields required by aggregation
        # ----------------------------------------------------

        {
            "$project": {
                "subjects": 1,
                "book_id": 1,
                "work_id": 1,
                "title": 1,
                "authors": 1
            }
        },

        # ----------------------------------------------------
        # 3. Split subject string
        #
        # Example:
        #
        # "AI | Machine learning | Neural networks"
        #
        # becomes:
        #
        # [
        #   "AI",
        #   "Machine learning",
        #   "Neural networks"
        # ]
        # ----------------------------------------------------

        {
            "$project": {
                "subjects": {
                    "$split": [
                        "$subjects",
                        "|"
                    ]
                },

                "book_id": 1,
                "work_id": 1,
                "title": 1,
                "authors": 1
            }
        },

        # ----------------------------------------------------
        # 4. Turn every subject into its own document
        # ----------------------------------------------------

        {
            "$unwind": "$subjects"
        },

        # ----------------------------------------------------
        # 5. Trim whitespace
        # ----------------------------------------------------

        {
            "$project": {
                "subject": {
                    "$trim": {
                        "input": "$subjects"
                    }
                },

                "book_id": 1,
                "work_id": 1,
                "title": 1,
                "authors": 1
            }
        },

        # ----------------------------------------------------
        # 6. Remove empty and generic subjects
        # ----------------------------------------------------

        {
            "$match": {
                "subject": {
                    "$nin": list(
                        EXCLUDED_SUBJECTS
                    ),

                    "$ne": ""
                }
            }
        },

        # ----------------------------------------------------
        # 7. Group by subject
        # ----------------------------------------------------

        {
            "$group": {

                "_id": "$subject",

                "count": {
                    "$sum": 1
                },

                "preview_book": {
                    "$first": {

                        "work_id": "$work_id",

                        "title": "$title",

                        "authors": "$authors",

                        "book_id": "$book_id"
                    }
                }
            }
        },

        # ----------------------------------------------------
        # 8. Sort by popularity
        # ----------------------------------------------------

        {
            "$sort": {
                "count": -1
            }
        },

        # ----------------------------------------------------
        # 9. Convert output format
        # ----------------------------------------------------

        {
            "$project": {

                "_id": 0,

                "name": "$_id",

                "count": 1,

                "preview_book": 1
            }
        }
    ]

    # --------------------------------------------------------
    # Run expensive aggregation ONLY during cache building.
    #
    # allowDiskUse=True prevents MongoDB from failing if
    # intermediate aggregation data exceeds memory limits.
    # --------------------------------------------------------

    categories = list(
        books_collection.aggregate(
            pipeline,
            allowDiskUse=True
        )
    )

    print()
    print(
        f"Aggregation complete."
    )

    print(
        f"Categories discovered: "
        f"{len(categories)}"
    )

    # --------------------------------------------------------
    # Replace existing category cache
    # --------------------------------------------------------

    print(
        "Replacing existing category cache..."
    )

    book_categories_collection.delete_many({})

    # --------------------------------------------------------
    # Insert new cache
    # --------------------------------------------------------

    if categories:

        book_categories_collection.insert_many(
            categories
        )

    # --------------------------------------------------------
    # Create index used by the API
    # --------------------------------------------------------

    print(
        "Creating category count index..."
    )

    book_categories_collection.create_index(
        [
            (
                "count",
                -1
            )
        ],
        name="category_count_desc"
    )

    print()

    print(
        f"Inserted categories: "
        f"{len(categories)}"
    )

    print(
        "Category cache built successfully."
    )

    print("=" * 60)
    print()


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    build_categories()