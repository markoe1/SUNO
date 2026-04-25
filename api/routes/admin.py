"""
Admin verification endpoints
Protected by ADMIN_VERIFY_TOKEN

DO NOT expose these in production without authentication
"""

import os
import json
import subprocess
from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_token(authorization: Optional[str] = Header(None)):
    """Verify admin token from Authorization header"""
    expected_token = os.getenv("ADMIN_VERIFY_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_VERIFY_TOKEN not configured"
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )

    token = authorization.replace("Bearer ", "").strip()

    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token"
        )


@router.get("/verify-production")
async def verify_production(token=Depends(verify_admin_token)):
    """
    Run production verification script
    Checks:
    - Database connectivity
    - Redis connectivity
    - Worker availability

    Protected by ADMIN_VERIFY_TOKEN
    """
    try:
        # Run the verification script
        result = subprocess.run(
            ["python", "scripts/verify_production.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout
        errors = result.stderr

        # Parse the JSON results (last line of output)
        lines = output.strip().split('\n')
        results = None

        for line in reversed(lines):
            if line.strip().startswith('{'):
                try:
                    results = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

        if not results:
            return {
                "status": "ERROR",
                "message": "Could not parse verification results",
                "output": output,
                "errors": errors
            }

        return {
            "status": "SUCCESS",
            "verification": results,
            "output": output
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "message": "Verification script timed out"
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e)
        }
