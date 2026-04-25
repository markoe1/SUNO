#!/usr/bin/env python3
"""
Standalone test script to verify Render infrastructure (DB, Redis)
Runs with Render environment variables directly
This tests the actual infrastructure without needing the app deployed
"""

import os
import sys

def test_database():
    """Test PostgreSQL (Neon) connectivity"""
    print("\n" + "="*60)
    print("DATABASE TEST (Neon PostgreSQL)")
    print("="*60)

    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        print("[FAIL] psycopg2 not installed")
        print("       Install with: pip install psycopg2-binary")
        return False

    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("[FAIL] DATABASE_URL environment variable not set")
            return False

        print(f"[INFO] DATABASE_URL found (length: {len(db_url)})")

        # Parse connection string
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))

        print(f"[INFO] Parsed - Host: {parsed.hostname}, DB: {parsed.path.lstrip('/')}")

        # Connect with SSL (required by Neon)
        conn = psycopg2.connect(
            dbname=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432,
            sslmode='require'
        )

        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        if result and result[0] == 1:
            print("[PASS] PostgreSQL connection successful")

            # Check tables
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            if tables:
                print(f"[PASS] Found {len(tables)} tables")

                # Check webhook_events table specifically
                if "webhook_events" in tables:
                    cursor.execute("SELECT COUNT(*) FROM webhook_events")
                    count = cursor.fetchone()[0]
                    print(f"[PASS] webhook_events table found ({count} rows)")
                    cursor.close()
                    conn.close()
                    return True
                else:
                    print("[WARN] webhook_events table not found (may not be created yet)")
                    cursor.close()
                    conn.close()
                    return True  # Still a pass if other tables exist
            else:
                print("[WARN] No tables found (database may be empty)")
                cursor.close()
                conn.close()
                return True  # Empty database is ok
        else:
            print("[FAIL] SELECT 1 returned unexpected result")
            cursor.close()
            conn.close()
            return False

    except Exception as e:
        print(f"[FAIL] Database error: {str(e)}")
        return False


def test_redis():
    """Test Redis (Upstash) connectivity"""
    print("\n" + "="*60)
    print("REDIS TEST (Upstash)")
    print("="*60)

    try:
        import redis
    except ImportError:
        print("[FAIL] redis-py not installed")
        print("       Install with: pip install redis")
        return False

    try:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("[FAIL] REDIS_URL environment variable not set")
            return False

        print(f"[INFO] REDIS_URL found")

        # Connect to Redis (Upstash provides rediss:// URL with TLS)
        r = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs="required")

        # Test PING
        pong = r.ping()
        if pong:
            print("[PASS] Redis PING successful")

            # Test write
            test_key = f"verify_test_{os.getpid()}"
            test_value = "test_data"
            r.set(test_key, test_value)
            print("[PASS] Redis WRITE successful")

            # Test read
            read_value = r.get(test_key)
            if read_value == test_value:
                print("[PASS] Redis READ successful")

                # Clean up
                r.delete(test_key)
                print("[PASS] Redis CLEANUP successful")
                return True
            else:
                print(f"[FAIL] Redis READ mismatch (expected '{test_value}', got '{read_value}')")
                r.delete(test_key)
                return False
        else:
            print("[FAIL] Redis PING failed")
            return False

    except Exception as e:
        print(f"[FAIL] Redis error: {str(e)}")
        return False


def main():
    """Run all infrastructure tests"""
    print("\n" + "="*60)
    print("SUNO RENDER INFRASTRUCTURE VERIFICATION")
    print("="*60)

    db_pass = test_database()
    redis_pass = test_redis()

    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Database:  {'PASS ✓' if db_pass else 'FAIL ✗'}")
    print(f"Redis:     {'PASS ✓' if redis_pass else 'FAIL ✗'}")

    overall = db_pass and redis_pass
    print(f"\nOverall:   {'PASS ✓ - Production Ready' if overall else 'FAIL ✗ - Issues Detected'}")
    print("="*60 + "\n")

    return overall


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
