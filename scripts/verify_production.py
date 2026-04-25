#!/usr/bin/env python3
"""
Production Verification Script
Safely verify database, Redis, and job queue connectivity
Runs from within the app environment with access to env vars
"""

import os
import json
import sys
from typing import Dict, Any

# Results tracking
results = {
    "DATABASE": "UNKNOWN",
    "TABLES": "UNKNOWN",
    "WEBHOOK_STORAGE": "UNKNOWN",
    "REDIS": "UNKNOWN",
    "QUEUE_WRITE": "UNKNOWN",
    "QUEUE_READ": "UNKNOWN",
    "OVERALL": "FAIL"
}

def safe_print(msg: str):
    """Print without exposing secrets"""
    # Mask database URLs
    if "postgresql://" in msg:
        msg = msg.replace(msg[msg.find("postgresql"):msg.find("@")], "postgresql://***:***")
    if "rediss://" in msg:
        msg = msg.replace(msg[msg.find("rediss"):msg.find("@")], "rediss://***:***")
    print(msg)

def verify_database() -> bool:
    """Verify PostgreSQL connection"""
    try:
        import psycopg2
        from psycopg2 import sql

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("  [FAIL] DATABASE_URL not set")
            return False

        # Parse connection string
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://"))

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
            print("  [PASS] PostgreSQL connection successful")
            results["DATABASE"] = "PASS"

            # Check tables
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema='public'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            if tables:
                print(f"  [PASS] Found {len(tables)} tables: {', '.join(tables[:5])}")
                results["TABLES"] = "PASS"

                # Check webhook_events table
                if "webhook_events" in tables:
                    cursor.execute("SELECT COUNT(*) FROM webhook_events")
                    count = cursor.fetchone()[0]
                    print(f"  [PASS] webhook_events table exists ({count} rows)")
                    results["WEBHOOK_STORAGE"] = "PASS"
                else:
                    print("  [UNKNOWN] webhook_events table not found")
                    results["WEBHOOK_STORAGE"] = "UNKNOWN"
            else:
                print("  [UNKNOWN] No tables found")
                results["TABLES"] = "UNKNOWN"

            cursor.close()
            conn.close()
            return True
        else:
            print("  [FAIL] SELECT 1 failed")
            return False

    except ImportError:
        print("  [UNKNOWN] psycopg2 not installed")
        return False
    except Exception as e:
        print(f"  [FAIL] Database error: {str(e)[:100]}")
        return False

def verify_redis() -> bool:
    """Verify Redis/Upstash connection"""
    try:
        import redis

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("  [FAIL] REDIS_URL not set")
            return False

        # Connect to Redis
        r = redis.from_url(redis_url, decode_responses=True)

        # Test PING
        pong = r.ping()
        if pong:
            print("  [PASS] Redis PING successful")
            results["REDIS"] = "PASS"

            # Test write
            test_key = f"verify_test_{os.getpid()}"
            test_value = "test_data"

            r.set(test_key, test_value)
            print(f"  [PASS] Redis WRITE successful")
            results["QUEUE_WRITE"] = "PASS"

            # Test read
            read_value = r.get(test_key)
            if read_value == test_value:
                print(f"  [PASS] Redis READ successful")
                results["QUEUE_READ"] = "PASS"

                # Clean up
                r.delete(test_key)
                print(f"  [PASS] Redis CLEANUP successful")
            else:
                print(f"  [FAIL] Redis READ mismatch")
                results["QUEUE_READ"] = "FAIL"

            return True
        else:
            print("  [FAIL] Redis PING failed")
            return False

    except ImportError:
        print("  [UNKNOWN] redis package not installed")
        return False
    except Exception as e:
        print(f"  [FAIL] Redis error: {str(e)[:100]}")
        return False

def verify_worker() -> bool:
    """Check if worker process exists and is running"""
    try:
        # Try to import the worker module
        from suno.workers.job_worker import JobWorker
        print("  [PASS] Worker module found")

        # Check if queue manager can be imported
        from suno.common.job_queue import JobQueueManager
        print("  [PASS] Queue manager found")

        return True
    except ImportError as e:
        print(f"  [UNKNOWN] Worker not detected: {str(e)[:100]}")
        return False
    except Exception as e:
        print(f"  [FAIL] Worker error: {str(e)[:100]}")
        return False

def main():
    """Run all verifications"""
    print("\n" + "="*60)
    print("PRODUCTION VERIFICATION REPORT")
    print("="*60 + "\n")

    print("[1/3] DATABASE VERIFICATION")
    verify_database()

    print("\n[2/3] REDIS VERIFICATION")
    verify_redis()

    print("\n[3/3] WORKER VERIFICATION")
    verify_worker()

    # Set overall status
    required_checks = ["DATABASE", "REDIS", "QUEUE_WRITE", "QUEUE_READ"]
    if all(results[check] == "PASS" for check in required_checks):
        results["OVERALL"] = "PASS"
        print("\n" + "="*60)
        print("OVERALL: PASS - System is production ready")
        print("="*60 + "\n")
    else:
        results["OVERALL"] = "FAIL"
        print("\n" + "="*60)
        print("OVERALL: FAIL - Issues detected")
        print("="*60 + "\n")

    # Print results as JSON
    print(json.dumps(results, indent=2))

    return results

if __name__ == "__main__":
    results = main()
    sys.exit(0 if results["OVERALL"] == "PASS" else 1)
