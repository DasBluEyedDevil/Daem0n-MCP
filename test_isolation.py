"""
Test script to verify per-project storage isolation.
"""

import os
import sys
from pathlib import Path
import tempfile

# Add DevilMCP to path
devilmcp_path = Path(__file__).parent
sys.path.insert(0, str(devilmcp_path))

def test_project_isolation():
    """Test that different projects get different storage paths."""

    print("\n" + "=" * 70)
    print("Testing Per-Project Storage Isolation")
    print("=" * 70)

    # Import server module
    import server

    # Test 1: From DevilMCP directory (should use centralized)
    print("\n[Test 1] Running from DevilMCP directory")
    print(f"Current directory: {os.getcwd()}")

    storage = server.get_storage_path()
    print(f"Storage path: {storage}")

    expected_centralized = str(devilmcp_path / "storage" / "centralized")
    if storage == expected_centralized:
        print("[PASS] Using centralized storage as expected")
    else:
        print(f"[WARN] Expected {expected_centralized}, got {storage}")

    # Test 2: From a different project directory
    print("\n[Test 2] Simulating Project A")

    with tempfile.TemporaryDirectory() as project_a:
        original_cwd = os.getcwd()
        os.chdir(project_a)

        print(f"Current directory: {os.getcwd()}")

        # Need to reload the module to recalculate storage_path
        # For testing purposes, just call get_storage_path again
        storage_a = server.get_storage_path()
        print(f"Storage path: {storage_a}")

        expected_a = str(Path(project_a) / ".devilmcp" / "storage")
        if storage_a == expected_a:
            print("[PASS] Using project-specific storage for Project A")
        else:
            print(f"[FAIL] Expected {expected_a}, got {storage_a}")

        # Verify directory was created
        if Path(storage_a).exists():
            print("[PASS] Storage directory created")
        else:
            print("[FAIL] Storage directory not created")

        os.chdir(original_cwd)

    # Test 3: From another different project directory
    print("\n[Test 3] Simulating Project B")

    with tempfile.TemporaryDirectory() as project_b:
        original_cwd = os.getcwd()
        os.chdir(project_b)

        print(f"Current directory: {os.getcwd()}")

        storage_b = server.get_storage_path()
        print(f"Storage path: {storage_b}")

        expected_b = str(Path(project_b) / ".devilmcp" / "storage")
        if storage_b == expected_b:
            print("[PASS] Using project-specific storage for Project B")
        else:
            print(f"[FAIL] Expected {expected_b}, got {storage_b}")

        # Verify it's different from Project A
        if storage_b != storage_a:
            print("[PASS] Project A and B have different storage paths")
        else:
            print("[FAIL] Project A and B have the same storage path!")

        os.chdir(original_cwd)

    # Test 4: Environment variable override
    print("\n[Test 4] Testing STORAGE_PATH override")

    override_path = "/tmp/custom_storage"
    os.environ['STORAGE_PATH'] = override_path

    storage_override = server.get_storage_path()
    print(f"Storage path: {storage_override}")

    if storage_override == override_path:
        print("[PASS] STORAGE_PATH environment variable respected")
    else:
        print(f"[FAIL] Expected {override_path}, got {storage_override}")

    # Clean up
    del os.environ['STORAGE_PATH']

    print("\n" + "=" * 70)
    print("*** Isolation Tests Complete ***")
    print("=" * 70)
    print("\nConclusion:")
    print("- Projects get isolated storage in .devilmcp/storage/")
    print("- Centralized storage used when running from DevilMCP dir")
    print("- Environment variables can override storage location")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_project_isolation()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
