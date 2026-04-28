#!/usr/bin/env python3
"""
COMPLETE SUNO CODEBASE AUDIT
Comprehensive integrity check without requiring services
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env first
load_dotenv('.env')

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

def section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

def run_cmd(cmd, cwd=None):
    """Run shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=10
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

# ============================================================================
# AUDIT REPORT
# ============================================================================
report = {
    'timestamp': datetime.now().isoformat(),
    'git_commit': '',
    'environment': {},
    'dependencies': {},
    'codebase': {},
    'security': {},
    'blockers': [],
    'warnings': [],
}

section("SUNO COMPLETE SYSTEM AUDIT")

# ============================================================================
# PHASE 0: GIT STATE
# ============================================================================
section("PHASE 0: GIT REPOSITORY STATE")

code, stdout, _ = run_cmd("git log --oneline -1")
if code == 0:
    commit_hash = stdout.strip().split()[0]
    report['git_commit'] = commit_hash
    print(f"Latest commit: {stdout.strip()}")

code, stdout, _ = run_cmd("git status --porcelain")
if code == 0:
    modified = [l for l in stdout.strip().split('\n') if l]
    print(f"Modified files: {len(modified)}")
    report['git_modified_count'] = len(modified)
    if modified:
        print("  Modified files:")
        for line in modified[:10]:
            print(f"    {line}")

code, stdout, _ = run_cmd("git log --oneline | head -10")
if code == 0:
    print("\nRecent commits:")
    for line in stdout.strip().split('\n')[:5]:
        print(f"  {line}")

# ============================================================================
# PHASE 1: ENVIRONMENT VALIDATION
# ============================================================================
section("PHASE 1: ENVIRONMENT VALIDATION")

required_keys = {
    'DATABASE_URL': 'Database connection',
    'REDIS_URL': 'Redis queue',
    'ANTHROPIC_API_KEY': 'Claude AI API (Phase 8)',
    'WHOP_API_KEY': 'Whop campaign API',
    'WHOP_WEBHOOK_SECRET': 'Webhook signature validation (PROD)',
    'SUNO_API_KEY': 'SUNO provisioning (PROD)',
    'ENVIRONMENT': 'Deployment environment',
}

for key, desc in required_keys.items():
    val = os.getenv(key)
    is_set = bool(val and str(val).strip())
    prod_only = '(PROD)' in desc

    status = 'SET' if is_set else 'MISSING'
    label = f"{status} {f'(PROD ONLY)' if prod_only else ''}"

    print(f"  {key:30s} [{label:20s}] {desc}")
    report['environment'][key] = is_set

    if prod_only and not is_set:
        report['warnings'].append(f"{key} not set (required for production)")

# ============================================================================
# PHASE 2: DEPENDENCY VALIDATION
# ============================================================================
section("PHASE 2: DEPENDENCY VALIDATION")

print("\nChecking installed packages...")

required_packages = [
    'fastapi', 'uvicorn', 'sqlalchemy', 'asyncpg', 'psycopg2',
    'redis', 'rq', 'python-dotenv', 'pydantic', 'anthropic'
]

report['dependencies'] = {}

for pkg in required_packages:
    try:
        __import__(pkg)
        print(f"  {pkg:25s} [OK]")
        report['dependencies'][pkg] = 'installed'
    except ImportError:
        print(f"  {pkg:25s} [MISSING]")
        report['dependencies'][pkg] = 'missing'
        report['blockers'].append(f"Package not installed: {pkg}")

# ============================================================================
# PHASE 3: CODEBASE STRUCTURE
# ============================================================================
section("PHASE 3: CODEBASE STRUCTURE")

required_dirs = {
    'api': 'FastAPI application',
    'suno': 'SUNO core system',
    'suno/common': 'Models and configuration',
    'suno/billing': 'Membership lifecycle',
    'suno/campaigns': 'Campaign orchestration',
    'web': 'Frontend templates',
    'migrations': 'Database migrations',
}

print("\nDirectory structure:")
for dir_name, desc in required_dirs.items():
    path = Path(dir_name)
    exists = path.exists()
    status = 'EXISTS' if exists else 'MISSING'
    print(f"  {dir_name:30s} [{status:10s}] {desc}")

    if not exists and dir_name not in ['migrations']:
        report['blockers'].append(f"Critical directory missing: {dir_name}")

# ============================================================================
# PHASE 4: CONFIGURATION FILES
# ============================================================================
section("PHASE 4: CONFIGURATION FILES")

config_files = {
    'config.py': 'Root configuration',
    'suno/config.py': 'Application configuration',
    '.env': 'Environment variables (local)',
    'docker-compose.yml': 'Docker compose',
    'docker-compose.prod.yml': 'Production docker compose',
    'requirements.txt': 'Python dependencies',
}

print("\nConfiguration files:")
for fname, desc in config_files.items():
    path = Path(fname)
    exists = path.exists()
    status = 'EXISTS' if exists else 'MISSING'
    size = f"({path.stat().st_size} bytes)" if exists else ""
    print(f"  {fname:30s} [{status:10s}] {desc} {size}")

# ============================================================================
# PHASE 5: API ROUTES
# ============================================================================
section("PHASE 5: API ROUTES INVENTORY")

try:
    # Import app factory
    from api.app import create_app
    app = create_app()

    routes = {}
    for route in app.routes:
        if hasattr(route, 'path'):
            key = f"{route.path}"
            if not hasattr(route, 'methods'):
                methods = ['GET']  # default
            else:
                methods = list(route.methods - {'HEAD', 'OPTIONS'})

            for method in methods:
                routes[f"{method} {route.path}"] = True

    print(f"\nTotal routes: {len(routes)}")

    # Group by prefix
    prefixes = {}
    for route in routes.keys():
        parts = route.split('/')
        prefix = f"/{parts[1]}" if len(parts) > 1 else "/"
        if prefix not in prefixes:
            prefixes[prefix] = 0
        prefixes[prefix] += 1

    print("\nRoutes by prefix:")
    for prefix in sorted(prefixes.keys()):
        count = prefixes[prefix]
        print(f"  {prefix:30s} [{count:3d} routes]")

    report['api_routes_total'] = len(routes)
    report['api_route_prefixes'] = prefixes

except Exception as e:
    print(f"ERROR loading API routes: {e}")
    report['warnings'].append(f"Could not load API routes: {e}")

# ============================================================================
# PHASE 6: DATABASE SCHEMA (STATIC INSPECTION)
# ============================================================================
section("PHASE 6: DATABASE SCHEMA (STATIC)")

try:
    from suno.common.models import Base
    from sqlalchemy.inspection import inspect as inspect_class

    tables = {}
    for cls in Base.registry.mappers:
        table = cls.class_
        table_name = table.__tablename__
        columns = [col.name for col in table.__table__.columns]
        tables[table_name] = {
            'columns': len(columns),
            'column_list': columns
        }

    print(f"\nTotal tables: {len(tables)}")
    print("\nTable schema:")
    for table_name in sorted(tables.keys()):
        col_count = tables[table_name]['columns']
        print(f"  {table_name:30s} [{col_count:2d} columns]")

    report['database_tables'] = {
        name: {'columns': info['columns']} for name, info in tables.items()
    }

except Exception as e:
    print(f"ERROR inspecting schema: {e}")
    report['warnings'].append(f"Could not inspect schema: {e}")

# ============================================================================
# PHASE 7: WORKER JOBS
# ============================================================================
section("PHASE 7: WORKER JOB DEFINITIONS")

try:
    job_files = list(Path('suno').glob('**/job*.py')) + \
                list(Path('suno').glob('**/worker*.py'))

    print(f"\nJob/Worker files: {len(job_files)}")
    for f in sorted(job_files)[:15]:
        print(f"  {f}")

    report['worker_files'] = len(job_files)

except Exception as e:
    print(f"ERROR finding worker files: {e}")

# ============================================================================
# PHASE 8: SECURITY CHECK
# ============================================================================
section("PHASE 8: SECURITY SCAN")

print("\nChecking for hardcoded secrets...")

dangerous_patterns = [
    ('api_key', 'API keys'),
    ('secret', 'Secrets'),
    ('password', 'Passwords'),
]

secrets_found = {}
py_files = list(Path('.').glob('**/*.py'))

for pattern, desc in dangerous_patterns:
    files_with_pattern = []
    for py_file in py_files:
        if 'venv' in str(py_file):
            continue
        try:
            content = py_file.read_text()
            if pattern in content.lower() and '=' in content:
                # Check for actual hardcoded values (not just variable names)
                if f"{pattern}=" in content.lower():
                    files_with_pattern.append(str(py_file))
        except:
            pass

    if files_with_pattern:
        print(f"  {desc:20s} found in {len(files_with_pattern)} files")
        secrets_found[desc] = files_with_pattern[:5]

if secrets_found:
    report['warnings'].append("Potential hardcoded secrets found in source")
    print("\n  WARNING: Check these files for hardcoded credentials:")
    for desc, files in secrets_found.items():
        for f in files[:3]:
            print(f"    {desc}: {f}")

# Check .env in git
code, stdout, _ = run_cmd("git ls-files .env")
if code == 0 and stdout.strip():
    report['blockers'].append("CRITICAL: .env file is tracked in git!")
    print("  CRITICAL: .env file is tracked in git (should be .gitignored)")

# ============================================================================
# PHASE 9: CRITICAL SYSTEM CHECKS
# ============================================================================
section("PHASE 9: CRITICAL SYSTEM CHECKS")

checks = {
    'Config.validate() called at startup': 'suno/config.py',
    'Webhook signature validation': 'suno/billing/webhook_routes.py',
    'Production environment flag': 'api/app.py',
    'Database ORM models defined': 'suno/common/models.py',
    'Job queue configuration': 'suno/common/job_queue.py',
}

print("\nCritical systems:")
for check, file_path in checks.items():
    p = Path(file_path)
    if p.exists():
        content = p.read_text()
        found = 'Config.validate' in content or 'validate' in file_path or \
                'webhook' in content.lower() or \
                'ENVIRONMENT' in content
        status = 'DEFINED' if found else 'CHECK_MANUALLY'
    else:
        status = 'FILE_MISSING'

    print(f"  {check:40s} [{status}]")

# ============================================================================
# FINAL REPORT
# ============================================================================
section("AUDIT SUMMARY & RECOMMENDATIONS")

print("\n[SYSTEM STATE]")
print(f"  Git commit:        {report['git_commit'][:8] if report['git_commit'] else 'unknown'}")
print(f"  Dependencies:      {sum(1 for v in report['dependencies'].values() if v == 'installed')}/{len(report['dependencies'])}")
print(f"  API routes:        {report.get('api_routes_total', '?')}")
print(f"  Database tables:   {len(report.get('database_tables', {}))}")

print("\n[BLOCKERS]")
if report['blockers']:
    for i, blocker in enumerate(report['blockers'], 1):
        print(f"  {i}. {blocker}")
else:
    print("  None found - codebase appears ready")

print("\n[WARNINGS]")
if report['warnings']:
    for i, warning in enumerate(report['warnings'], 1):
        print(f"  {i}. {warning}")
else:
    print("  None found")

print("\n[NEXT STEPS]")
if not report['blockers']:
    print("  1. Ensure all dependencies are installed:")
    print("     pip install -r requirements.txt")
    print("  2. Start Docker services:")
    print("     docker-compose up")
    print("  3. Run database migrations:")
    print("     docker-compose exec api alembic upgrade head")
    print("  4. Start API and worker in separate terminals:")
    print("     - API: uvicorn api.app:app --reload")
    print("     - Worker: python -m rq worker suno-clips --url redis://localhost:6379/0")
else:
    print("  Fix blockers before proceeding")

print("\n[ENVIRONMENT CHECK]")
print(f"  ENVIRONMENT var: {os.getenv('ENVIRONMENT', 'development')}")
if os.getenv('ENVIRONMENT') == 'production':
    print("  WARNING: Running in PRODUCTION mode")
    prod_required = ['WHOP_WEBHOOK_SECRET', 'SUNO_API_KEY']
    missing_prod = [k for k in prod_required if not os.getenv(k)]
    if missing_prod:
        print(f"  CRITICAL: Missing production credentials: {missing_prod}")
else:
    print("  Running in DEVELOPMENT mode (stubs enabled)")

# Save report
report_path = Path('COMPLETE_AUDIT_REPORT.json')
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2, default=str)
print(f"\nAudit report saved: {report_path}")

print("\n" + "="*80)
print("AUDIT COMPLETE")
print("="*80)

# Return exit code based on blockers
sys.exit(1 if report['blockers'] else 0)
