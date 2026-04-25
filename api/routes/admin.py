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

    Returns:
    - status: SUCCESS, ERROR, TIMEOUT
    - verification: parsed JSON results (if successful)
    - stdout: raw script output
    - stderr: raw script errors
    - exit_code: process exit code
    - parse_error: if JSON parsing failed
    """
    try:
        # Run the verification script
        result = subprocess.run(
            ["python", "scripts/verify_production.py"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/opt/render/project/src"  # Run from repo root where scripts/ exists
        )

        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode

        # Try to parse JSON from output
        # Look for marked JSON section (JSON_RESULTS_START/END)
        results = None
        parse_error = None

        if stdout:
            # First, try to find the clearly marked JSON section
            if "JSON_RESULTS_START" in stdout and "JSON_RESULTS_END" in stdout:
                try:
                    start_idx = stdout.find("JSON_RESULTS_START") + len("JSON_RESULTS_START")
                    end_idx = stdout.find("JSON_RESULTS_END")
                    json_str = stdout[start_idx:end_idx].strip()
                    if json_str:
                        results = json.loads(json_str)
                except json.JSONDecodeError as e:
                    parse_error = f"Invalid JSON in marked section: {str(e)}"
            else:
                # Fallback: try to parse each line as JSON
                lines = stdout.strip().split('\n')

                for line in reversed(lines):
                    line_stripped = line.strip()
                    if line_stripped and (line_stripped.startswith('{') or line_stripped.startswith('[')):
                        try:
                            results = json.loads(line_stripped)
                            break
                        except json.JSONDecodeError:
                            continue

                # If still no results, note it
                if not results:
                    parse_error = "Could not find valid JSON in script output"

        return {
            "status": "SUCCESS" if results else "ERROR",
            "verification": results,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "parse_error": parse_error
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "message": "Verification script timed out",
            "exit_code": None
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "exit_code": None
        }
