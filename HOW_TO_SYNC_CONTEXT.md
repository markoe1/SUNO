# How to sync context quickly (for new sessions)

Run these in the repo root to get a fast, accurate project recap:

```powershell
# 1) High-level summary
Get-Content -Path README.md -TotalCount 60

# 2) Recent commits
git --no-pager log --oneline -n 15

# 3) Open decisions + session notes
Get-Content DECISIONS.md
Get-ChildItem PROJECT_NOTES | Sort-Object Name -Descending | Select-Object -First 1 | ForEach-Object { Get-Content $_.FullName | Select-Object -First 60 }
```

Optional: keep notes per day in `PROJECT_NOTES/SESSION_NOTES_YYYY-MM-DD.md`.