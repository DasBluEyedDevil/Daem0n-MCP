# Usage: Open PowerShell at project root and run: .\scripts\remove_nul.ps1

$proj = (Get-Location).ProviderPath
$nulPath = "\\?\$proj\nul"

Write-Host "Checking for reserved file at: $nulPath"

if (Test-Path -LiteralPath $nulPath) {
    Write-Host "Found file; attempting to remove filesystem entry..."
    Remove-Item -LiteralPath $nulPath -Force -ErrorAction Stop
    Write-Host "Filesystem entry removed."
} else {
    Write-Host "No filesystem entry found."
}

Write-Host "Attempting to remove from git index..."
# Remove from git index even if filesystem entry already removed
git update-index --force-remove -- 'nul' 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "'nul' removed from git index."
    git add .gitignore 2>$null
    git commit -m "Remove reserved file 'nul' and ignore it" 2>$null || Write-Host "No changes to commit."
} else {
    Write-Host "git update-index failed or 'nul' not present in index. Run the git commands manually if needed."
}

Write-Host "Done. Invalidate Android Studio caches and restart (File → Invalidate Caches / Restart)."

