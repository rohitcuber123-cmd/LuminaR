"""
Bug Condition Exploration Test for Search History Duplicate ID Race Condition

CRITICAL: This test MUST FAIL on unfixed code to prove the race condition exists.
When it fails with DuplicateKeyError, that confirms the bug.
After the fix is implemented, this same test should PASS.

This test validates Property 1: Bug Condition - Concurrent Search ID Generation Race Condition
Requirements validated: 1.1, 1.2, 1.3, 1.4
"""

import unittest
import threading
import time
from datetime import datetime, timezone

# Import the search history service functions
from backend.services.search_history_service import (
    get_next_search_id,
    create_search_history,
    search_history_collection
)

from pymongo.errors import DuplicateKeyError


class TestSearchHistoryRaceCondition(unittest.TestCase):
    """
    Bug Condition Exploration: Concurrent Search ID Generation
    
    This test simulates the race condition where multiple concurrent requests
    attempt to create search history records simultaneously.
    
    Expected behavior on UNFIXED code: FAILS with DuplicateKeyError
    Expected behavior on FIXED code: PASSES with all unique IDs
    """
    
    def setUp(self):
        """Clean up any test data before each test"""
        # Use a test user_id to avoid polluting production data
        self.test_user_id = 999999
        # Clean up any existing test records
        search_history_collection.delete_many({"user_id": self.test_user_id})
    
    def tearDown(self):
        """Clean up test data after each test"""
        search_history_collection.delete_many({"user_id": self.test_user_id})
    
    def test_concurrent_search_id_generation_race_condition(self):
        """
        BUG CONDITION TEST: Concurrent calls to get_next_search_id() produce duplicate IDs
        
        This test spawns multiple threads that simultaneously attempt to:
        1. Call get_next_search_id() to get the next available ID
        2. Create a search history record with that ID
        
        On UNFIXED code:
        - Multiple threads will read the same maximum search_id
        - They will all calculate the same next_id value
        - The second (and subsequent) inserts will fail with E11000 DuplicateKeyError
        - This test will FAIL (which is CORRECT - it proves the bug exists)
        
        On FIXED code:
        - MongoDB's atomic $inc operator ensures each thread gets a unique ID
        - All inserts succeed
        - This test will PASS
        
        Validates: Requirements 1.1, 1.2, 1.3, 1.4
        """
        num_threads = 20  # Spawn 20 concurrent threads to increase race condition probability
        generated_ids = []
        exceptions = []
        lock = threading.Lock()
        
        # Barrier to ensure all threads start at approximately the same time
        barrier = threading.Barrier(num_threads)
        
        def worker(thread_id):
            """Worker function that attempts to create a search history record"""
            try:
                # Wait for all threads to be ready
                barrier.wait()
                
                # Attempt to create a search history record
                # This internally calls get_next_search_id()
                result = create_search_history(
                    user_id=self.test_user_id,
                    query=f"test query {thread_id}",
                    top_k=10,
                    results=[
                        {"work_id": f"work_{thread_id}_1", "title": "Test Book 1"},
                        {"work_id": f"work_{thread_id}_2", "title": "Test Book 2"}
                    ]
                )
                
                with lock:
                    if result is not None:
                        generated_ids.append(result["search_id"])
                        
            except DuplicateKeyError as e:
                # Expected on unfixed code: race condition causes duplicate IDs
                with lock:
                    exceptions.append(e)
            except Exception as e:
                # Unexpected errors
                with lock:
                    exceptions.append(e)
        
        # Create and start all threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        
        for t in threads:
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # ========================================
        # ASSERTIONS - This is what we're testing
        # ========================================
        
        print(f"\n{'='*60}")
        print("Bug Condition Exploration Test Results")
        print(f"{'='*60}")
        print(f"Threads spawned: {num_threads}")
        print(f"Successful inserts: {len(generated_ids)}")
        print(f"DuplicateKeyErrors caught: {len([e for e in exceptions if isinstance(e, DuplicateKeyError)])}")
        print(f"Other exceptions: {len([e for e in exceptions if not isinstance(e, DuplicateKeyError)])}")
        
        if exceptions:
            print(f"\nExceptions encountered:")
            for i, exc in enumerate(exceptions[:5], 1):  # Show first 5 exceptions
                print(f"  {i}. {type(exc).__name__}: {str(exc)[:100]}")
        
        if generated_ids:
            print(f"\nGenerated IDs: {sorted(generated_ids)[:20]}")  # Show first 20 IDs
            print(f"Unique IDs: {len(set(generated_ids))}")
            print(f"Total IDs: {len(generated_ids)}")
            
            # Check for duplicates
            duplicate_ids = [id for id in set(generated_ids) if generated_ids.count(id) > 1]
            if duplicate_ids:
                print(f"DUPLICATE IDs DETECTED: {duplicate_ids}")
        
        print(f"{'='*60}\n")
        
        # ========================================
        # EXPECTED BEHAVIOR
        # ========================================
        
        # On UNFIXED code: We expect DuplicateKeyErrors
        # On FIXED code: All IDs should be unique and all inserts should succeed
        
        # ASSERTION 1: All IDs must be unique (no duplicates)
        self.assertEqual(
            len(generated_ids),
            len(set(generated_ids)),
            f"DUPLICATE IDs DETECTED: {len(generated_ids)} IDs generated but only {len(set(generated_ids))} unique. "
            f"This indicates the race condition is NOT fixed."
        )
        
        # ASSERTION 2: No DuplicateKeyErrors should occur (on fixed code)
        duplicate_errors = [e for e in exceptions if isinstance(e, DuplicateKeyError)]
        self.assertEqual(
            len(duplicate_errors),
            0,
            f"DuplicateKeyError exceptions occurred: {len(duplicate_errors)}. "
            f"This indicates the race condition still exists in get_next_search_id()."
        )
        
        # ASSERTION 3: All threads should succeed (total = num_threads)
        total_operations = len(generated_ids) + len(exceptions)
        self.assertEqual(
            total_operations,
            num_threads,
            f"Not all operations completed. Expected {num_threads}, got {total_operations}"
        )
        
        # ASSERTION 4: IDs should be sequential (no gaps or skips)
        if generated_ids:
            sorted_ids = sorted(generated_ids)
            for i in range(1, len(sorted_ids)):
                self.assertEqual(
                    sorted_ids[i],
                    sorted_ids[i-1] + 1,
                    f"Non-sequential IDs detected: {sorted_ids[i-1]} -> {sorted_ids[i]}. "
                    f"IDs should increment by exactly 1."
                )
        
        print("✓ All assertions passed: No race condition detected!")
        print("  - All IDs are unique")
        print("  - No DuplicateKeyErrors occurred")
        print("  - All threads completed successfully")
        print("  - IDs are sequential with no gaps")
    
    def test_high_concurrency_stress_test(self):
        """
        STRESS TEST: Even higher concurrency to maximize race condition probability
        
        This test uses 50 threads with a very tight timing window to increase
        the likelihood of exposing the race condition on unfixed code.
        
        On UNFIXED code: High failure rate (50-80% of inserts may fail)
        On FIXED code: All operations succeed with unique IDs
        """
        num_threads = 50
        generated_ids = []
        exceptions = []
        lock = threading.Lock()
        barrier = threading.Barrier(num_threads)
        
        def worker(thread_id):
            try:
                barrier.wait()  # Synchronize all threads
                
                # Direct call to get_next_search_id to test the function in isolation
                new_id = get_next_search_id()
                
                with lock:
                    generated_ids.append(new_id)
                    
            except Exception as e:
                with lock:
                    exceptions.append(e)
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        print(f"\n{'='*60}")
        print("High Concurrency Stress Test Results")
        print(f"{'='*60}")
        print(f"Threads: {num_threads}")
        print(f"IDs generated: {len(generated_ids)}")
        print(f"Unique IDs: {len(set(generated_ids))}")
        print(f"Exceptions: {len(exceptions)}")
        
        if generated_ids:
            duplicate_ids = [id for id in set(generated_ids) if generated_ids.count(id) > 1]
            if duplicate_ids:
                print(f"\nDUPLICATE IDs: {duplicate_ids}")
                for dup_id in duplicate_ids:
                    count = generated_ids.count(dup_id)
                    print(f"  ID {dup_id} appeared {count} times")
        
        print(f"{'='*60}\n")
        
        # ASSERTION: All IDs must be unique
        self.assertEqual(
            len(generated_ids),
            len(set(generated_ids)),
            f"Duplicate IDs detected in high concurrency test: {len(generated_ids)} total, "
            f"{len(set(generated_ids))} unique"
        )
        
        print("✓ High concurrency test passed: All IDs are unique under stress")


if __name__ == "__main__":
    # Run the tests
    print("\n" + "="*80)
    print("SEARCH HISTORY RACE CONDITION - BUG CONDITION EXPLORATION TEST")
    print("="*80)
    print("\nIMPORTANT:")
    print("- On UNFIXED code: This test SHOULD FAIL with DuplicateKeyError")
    print("- Failure confirms the race condition exists (this is expected)")
    print("- After implementing the fix: This test SHOULD PASS")
    print("="*80 + "\n")
    
    unittest.main(verbosity=2)
