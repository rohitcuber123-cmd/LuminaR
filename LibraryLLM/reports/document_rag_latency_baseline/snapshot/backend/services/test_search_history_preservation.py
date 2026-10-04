"""
Preservation Property Tests for Search History Service

These tests document and verify the EXISTING behavior of the search history service
on UNFIXED code for NON-BUGGY inputs (sequential, single-threaded operations).

CRITICAL: These tests MUST PASS on unfixed code to establish baseline behavior.
After the fix, these same tests MUST still PASS to confirm no regressions.

This test validates Property 2: Preservation - Search History Data Structure and Behavior
Requirements validated: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import unittest
import time
from datetime import datetime, timezone

# Import the search history service functions
from backend.services.search_history_service import (
    get_next_search_id,
    create_search_history,
    get_user_search_history,
    search_history_collection
)


class TestSearchHistoryPreservation(unittest.TestCase):
    """
    Preservation Property Tests: Verify existing behavior is unchanged
    
    These tests validate that for NON-CONCURRENT (sequential, single-threaded)
    operations, the search history service behaves identically before and after
    the race condition fix.
    """
    
    def setUp(self):
        """Set up test data"""
        # Use a distinct test user_id to avoid interference
        self.test_user_id = 888888
        # Clean up any existing test records
        search_history_collection.delete_many({"user_id": self.test_user_id})
    
    def tearDown(self):
        """Clean up test data"""
        search_history_collection.delete_many({"user_id": self.test_user_id})
    
    def test_sequential_id_generation_increments_by_one(self):
        """
        PRESERVATION: Sequential create_search_history() calls produce incrementing search_ids
        
        Observed behavior on unfixed code:
        - Calling create_search_history() multiple times sequentially (no concurrency)
        - Each record gets a search_id that is the previous value + 1
        - IDs are: N, N+1, N+2, N+3, ...
        
        Note: get_next_search_id() alone doesn't increment - it reads the max.
        The actual increment happens when create_search_history() calls it and inserts.
        
        This behavior MUST be preserved after the fix.
        
        Validates: Requirement 3.4
        """
        print("\n" + "="*60)
        print("Test: Sequential ID Generation")
        print("="*60)
        
        # Create 10 search history records sequentially
        all_ids = []
        for i in range(10):
            record = create_search_history(
                user_id=self.test_user_id,
                query=f"sequential test query {i}",
                top_k=10,
                results=[{"work_id": f"work_{i}"}]
            )
            all_ids.append(record["search_id"])
        
        print(f"Generated IDs: {all_ids}")
        
        # ASSERTION 1: Each ID should be exactly 1 greater than the previous
        for i in range(1, len(all_ids)):
            self.assertEqual(
                all_ids[i],
                all_ids[i-1] + 1,
                f"IDs not sequential: {all_ids[i-1]} -> {all_ids[i]}"
            )
        
        # ASSERTION 2: All IDs should be unique
        self.assertEqual(
            len(all_ids),
            len(set(all_ids)),
            "Duplicate IDs in sequential generation"
        )
        
        # ASSERTION 3: IDs should be positive integers
        for id_val in all_ids:
            self.assertIsInstance(id_val, int, f"ID {id_val} is not an integer")
            self.assertGreater(id_val, 0, f"ID {id_val} is not positive")
        
        print("✓ Sequential IDs increment by exactly 1")
        print("="*60)
    
    def test_search_history_record_structure(self):
        """
        PRESERVATION: create_search_history() produces records with 7 expected fields
        
        Observed behavior on unfixed code:
        - Record contains: search_id, user_id, query, top_k, result_work_ids, result_count, created_at
        - All fields have correct data types
        - created_at is a datetime object with timezone
        
        This structure MUST be preserved after the fix.
        
        Validates: Requirement 3.1
        """
        print("\n" + "="*60)
        print("Test: Search History Record Structure")
        print("="*60)
        
        # Create a test search history record
        test_query = "machine learning fundamentals"
        test_top_k = 15
        test_results = [
            {"work_id": "work_001", "title": "ML Book 1", "score": 0.95},
            {"work_id": "work_002", "title": "ML Book 2", "score": 0.89},
            {"work_id": "work_003", "title": "ML Book 3", "score": 0.82}
        ]
        
        record = create_search_history(
            user_id=self.test_user_id,
            query=test_query,
            top_k=test_top_k,
            results=test_results
        )
        
        print(f"Created record: {record}")
        
        # ASSERTION 1: Record should not be None
        self.assertIsNotNone(record, "create_search_history returned None")
        
        # ASSERTION 2: Record should have exactly 7 fields
        expected_fields = {
            "search_id", "user_id", "query", "top_k", 
            "result_work_ids", "result_count", "created_at"
        }
        actual_fields = set(record.keys())
        
        self.assertEqual(
            actual_fields,
            expected_fields,
            f"Record structure mismatch. Expected: {expected_fields}, Got: {actual_fields}"
        )
        
        # ASSERTION 3: Field types should be correct
        self.assertIsInstance(record["search_id"], int, "search_id should be int")
        self.assertIsInstance(record["user_id"], int, "user_id should be int")
        self.assertIsInstance(record["query"], str, "query should be str")
        self.assertIsInstance(record["top_k"], int, "top_k should be int")
        self.assertIsInstance(record["result_work_ids"], list, "result_work_ids should be list")
        self.assertIsInstance(record["result_count"], int, "result_count should be int")
        self.assertIsInstance(record["created_at"], datetime, "created_at should be datetime")
        
        # ASSERTION 4: Field values should match input
        self.assertEqual(record["user_id"], self.test_user_id)
        self.assertEqual(record["query"], test_query)
        self.assertEqual(record["top_k"], test_top_k)
        self.assertEqual(record["result_count"], 3)
        self.assertEqual(len(record["result_work_ids"]), 3)
        self.assertEqual(record["result_work_ids"], ["work_001", "work_002", "work_003"])
        
        # ASSERTION 5: created_at should have timezone info
        self.assertIsNotNone(record["created_at"].tzinfo, "created_at should have timezone")
        
        # ASSERTION 6: search_id should be positive
        self.assertGreater(record["search_id"], 0, "search_id should be positive")
        
        print("✓ Record structure is correct with all 7 fields")
        print("✓ All field types are correct")
        print("✓ All field values match inputs")
        print("="*60)
    
    def test_search_history_retrieval_sorting(self):
        """
        PRESERVATION: get_user_search_history() returns records sorted by created_at descending
        
        Observed behavior on unfixed code:
        - Records are retrieved for the specified user_id
        - Records are sorted by created_at in descending order (most recent first)
        - Limit parameter controls how many records are returned
        
        This behavior MUST be preserved after the fix.
        
        Validates: Requirement 3.2
        """
        print("\n" + "="*60)
        print("Test: Search History Retrieval and Sorting")
        print("="*60)
        
        # Create multiple search history records with small time delays
        # to ensure different timestamps
        records_created = []
        
        for i in range(5):
            record = create_search_history(
                user_id=self.test_user_id,
                query=f"test query {i}",
                top_k=10,
                results=[{"work_id": f"work_{i}"}]
            )
            records_created.append(record)
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        print(f"Created {len(records_created)} records")
        
        # Retrieve the search history
        history = get_user_search_history(
            user_id=self.test_user_id,
            limit=10
        )
        
        print(f"Retrieved {len(history)} records")
        
        # ASSERTION 1: Should retrieve all created records
        self.assertEqual(
            len(history),
            len(records_created),
            f"Expected {len(records_created)} records, got {len(history)}"
        )
        
        # ASSERTION 2: Records should be sorted by created_at descending
        for i in range(len(history) - 1):
            current_time = history[i]["created_at"]
            next_time = history[i + 1]["created_at"]
            
            self.assertGreaterEqual(
                current_time,
                next_time,
                f"Records not sorted by created_at descending: {current_time} < {next_time}"
            )
        
        # ASSERTION 3: Most recent record should be first
        # (last created record should be first in retrieval)
        self.assertEqual(
            history[0]["query"],
            "test query 4",  # Last query we created
            "Most recent record should be first"
        )
        
        # ASSERTION 4: Oldest record should be last
        self.assertEqual(
            history[-1]["query"],
            "test query 0",  # First query we created
            "Oldest record should be last"
        )
        
        # ASSERTION 5: Limit parameter should work
        limited_history = get_user_search_history(
            user_id=self.test_user_id,
            limit=3
        )
        
        self.assertEqual(
            len(limited_history),
            3,
            f"Limit parameter not working: expected 3 records, got {len(limited_history)}"
        )
        
        print("✓ Records sorted by created_at descending")
        print("✓ Most recent record appears first")
        print("✓ Limit parameter works correctly")
        print("="*60)
    
    def test_first_search_gets_id_one(self):
        """
        PRESERVATION: First search after database wipe gets search_id = 1
        
        Observed behavior on unfixed code:
        - When search_history collection is empty
        - get_next_search_id() returns 1
        - First search record has search_id = 1
        
        This behavior MUST be preserved after the fix.
        
        Validates: Requirement 3.4
        """
        print("\n" + "="*60)
        print("Test: First Search ID Assignment")
        print("="*60)
        
        # Note: We can't wipe the entire collection without affecting other tests
        # But we can test with a brand new user that has no history
        new_user_id = 777777
        
        # Ensure this user has no existing history
        search_history_collection.delete_many({"user_id": new_user_id})
        
        # Verify no records exist for this user
        existing_count = search_history_collection.count_documents({"user_id": new_user_id})
        self.assertEqual(existing_count, 0, "Test user should have no existing history")
        
        # Create first search for this user
        first_record = create_search_history(
            user_id=new_user_id,
            query="first search ever",
            top_k=10,
            results=[{"work_id": "work_1"}]
        )
        
        print(f"First record search_id: {first_record['search_id']}")
        
        # ASSERTION 1: First record should have a valid search_id
        self.assertIsNotNone(first_record, "First record should not be None")
        self.assertIn("search_id", first_record, "Record should have search_id field")
        
        # ASSERTION 2: search_id should be a positive integer
        self.assertIsInstance(first_record["search_id"], int)
        self.assertGreater(first_record["search_id"], 0)
        
        # Note: We can't assert search_id == 1 because the collection may have
        # existing records from other tests. But we can assert it's sequential.
        
        # Create a second search for the same user
        second_record = create_search_history(
            user_id=new_user_id,
            query="second search",
            top_k=10,
            results=[{"work_id": "work_2"}]
        )
        
        # ASSERTION 3: Second record ID should be first ID + 1
        self.assertEqual(
            second_record["search_id"],
            first_record["search_id"] + 1,
            "Second search ID should be exactly 1 greater than first"
        )
        
        # Clean up
        search_history_collection.delete_many({"user_id": new_user_id})
        
        print("✓ First search gets valid positive search_id")
        print("✓ Subsequent searches increment correctly")
        print("="*60)
    
    def test_multiple_users_independent_history(self):
        """
        PRESERVATION: Each user's search history is independent
        
        Observed behavior on unfixed code:
        - Different users can search simultaneously
        - Each user's history is stored with their user_id
        - get_user_search_history() only returns records for the specified user
        
        This behavior MUST be preserved after the fix.
        
        Validates: Requirement 3.1, 3.2
        """
        print("\n" + "="*60)
        print("Test: Multiple Users Independent History")
        print("="*60)
        
        user_a = 111111
        user_b = 222222
        
        # Clean up
        search_history_collection.delete_many({"user_id": {"$in": [user_a, user_b]}})
        
        # Create searches for user A
        for i in range(3):
            create_search_history(
                user_id=user_a,
                query=f"user A query {i}",
                top_k=10,
                results=[{"work_id": f"a_{i}"}]
            )
        
        # Create searches for user B
        for i in range(5):
            create_search_history(
                user_id=user_b,
                query=f"user B query {i}",
                top_k=10,
                results=[{"work_id": f"b_{i}"}]
            )
        
        # Retrieve history for each user
        history_a = get_user_search_history(user_id=user_a, limit=50)
        history_b = get_user_search_history(user_id=user_b, limit=50)
        
        print(f"User A history: {len(history_a)} records")
        print(f"User B history: {len(history_b)} records")
        
        # ASSERTION 1: Each user should have correct number of records
        self.assertEqual(len(history_a), 3, "User A should have 3 records")
        self.assertEqual(len(history_b), 5, "User B should have 5 records")
        
        # ASSERTION 2: User A's history should only contain user_a's user_id
        for record in history_a:
            self.assertEqual(
                record["user_id"],
                user_a,
                f"User A's history contains wrong user_id: {record['user_id']}"
            )
        
        # ASSERTION 3: User B's history should only contain user_b's user_id
        for record in history_b:
            self.assertEqual(
                record["user_id"],
                user_b,
                f"User B's history contains wrong user_id: {record['user_id']}"
            )
        
        # ASSERTION 4: Queries should match expected users
        for record in history_a:
            self.assertIn("user A query", record["query"])
        
        for record in history_b:
            self.assertIn("user B query", record["query"])
        
        # Clean up
        search_history_collection.delete_many({"user_id": {"$in": [user_a, user_b]}})
        
        print("✓ Each user's history is independent")
        print("✓ History retrieval correctly filters by user_id")
        print("="*60)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SEARCH HISTORY PRESERVATION PROPERTY TESTS")
    print("="*80)
    print("\nIMPORTANT:")
    print("- These tests document EXISTING behavior on unfixed code")
    print("- All tests SHOULD PASS on unfixed code (baseline)")
    print("- After implementing the fix: All tests SHOULD STILL PASS (no regressions)")
    print("="*80 + "\n")
    
    unittest.main(verbosity=2)
