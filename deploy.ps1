# Altitude Maps - Production Deployment Script
# Deploys only the web viewer and generated data (no raw data or processing code)

param(
    [Parameter(Mandatory=$true)]
    [string]$RemoteHost,
    
    [Parameter(Mandatory=$true)]
    [string]$RemotePath,
    
    [string]$RemoteUser = "",
    
    [switch]$DryRun = $false
)

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan
Write-Host "Altitude Maps - Production Deployment" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan

# Build remote destination
$destination = if ($RemoteUser) { "${RemoteUser}@${RemoteHost}:${RemotePath}" } else { "${RemoteHost}:${RemotePath}" }

Write-Host "`nDeployment Configuration:" -ForegroundColor Yellow
Write-Host "  Local:  " -NoNewline
Write-Host "$PSScriptRoot" -ForegroundColor Green
Write-Host "  Remote: " -NoNewline
Write-Host "$destination" -ForegroundColor Green
Write-Host "  Mode:   " -NoNewline
if ($DryRun) {
    Write-Host "DRY RUN (no changes will be made)" -ForegroundColor Yellow
} else {
    Write-Host "LIVE DEPLOYMENT" -ForegroundColor Red
}

Write-Host "`nFiles to deploy:" -ForegroundColor Yellow
Write-Host "  [x] HTML viewers (interactive_viewer_advanced.html, viewer.html)"
Write-Host "  [x] JavaScript (js/)"
Write-Host "  [x] CSS (css/)"
Write-Host "  [x] Generated data (generated/)"
Write-Host "  [x] README.md (optional)"
Write-Host ""
Write-Host "  Note: External dependencies loaded from CDN (Three.js, jQuery, Select2)"

Write-Host "`nFiles excluded:" -ForegroundColor Yellow
Write-Host "  [-] Raw data (data/) - NOT NEEDED for viewer"
Write-Host "  [-] Source code (src/) - NOT NEEDED for viewer"
Write-Host "  [-] Processing scripts (*.py) - NOT NEEDED for viewer"
Write-Host "  [-] Virtual environment (venv/)"
Write-Host "  [-] Documentation (tech/, learnings/)"
Write-Host "  [-] Development files"

# Check if rsync is available
$rsyncPath = Get-Command rsync -ErrorAction SilentlyContinue
if (-not $rsyncPath) {
    Write-Host "`n[X] Error: rsync not found!" -ForegroundColor Red
    Write-Host "    Install rsync for Windows:" -ForegroundColor Yellow
    Write-Host "    - Via Chocolatey: choco install rsync" -ForegroundColor Gray
    Write-Host "    - Via Git for Windows (includes rsync)" -ForegroundColor Gray
    Write-Host "    - Via WSL: wsl --install" -ForegroundColor Gray
    exit 1
}

Write-Host "`n" -NoNewline
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 69) -ForegroundColor Cyan

# Ask for confirmation if not dry run
if (-not $DryRun) {
    Write-Host "`nThis will upload files to the remote server." -ForegroundColor Yellow
    $confirm = Read-Host "Continue? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Host "Deployment cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "`n[*] Updating version numbers..." -ForegroundColor Cyan
& python update_version.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Version update failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n[*] Starting deployment..." -ForegroundColor Green

# Build rsync command
$rsyncArgs = @(
    "-avz"                      # archive, verbose, compress
    "--progress"                # show progress
    "--delete"                  # delete files on remote that don't exist locally
    "--filter=P *.gz"           # protect .gz files from deletion (server-side compressed)
    "--include=interactive_viewer_advanced.html"
    "--include=viewer.html"
    "--include=js/"
    "--include=js/**"
    "--include=css/"
    "--include=css/**"
    "--include=generated/"
    "--include=generated/**"
    "--include=README.md"
    "--exclude=*"               # exclude everything else
    "--exclude=.*"              # exclude hidden files
    "--exclude=__pycache__/"    # exclude Python cache
    "--exclude=*.pyc"           # exclude compiled Python
    "--exclude=data/"           # exclude raw data
    "--exclude=src/"            # exclude source code
    "--exclude=venv/"           # exclude virtual environment
    "--exclude=output/"         # exclude output images
    "--exclude=rasters/"        # exclude rasters
    "--exclude=tech/"           # exclude technical docs
    "--exclude=learnings/"      # exclude learning docs
    "--exclude=*.py"            # exclude Python scripts (except serve_viewer.py)
    "--exclude=*.ps1"           # exclude PowerShell scripts (except this one)
    "--exclude=*.txt"           # exclude text files
    "--exclude=*.md"            # exclude markdown (except README.md)
    "--exclude=*.log"           # exclude logs
    "--exclude=*.png"           # exclude screenshots
    "--exclude=.git/"           # exclude git
    "--exclude=.gitignore"      # exclude gitignore
)

if ($DryRun) {
    $rsyncArgs += "--dry-run"
}

# Add source and destination
$rsyncArgs += "$PSScriptRoot\"
$rsyncArgs += $destination

# Execute rsync
Write-Host "`n[*] Running rsync..." -ForegroundColor Cyan
Write-Host "Command: rsync $($rsyncArgs -join ' ')" -ForegroundColor Gray
Write-Host ""

& rsync $rsyncArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n" -NoNewline
    Write-Host "=" -NoNewline -ForegroundColor Green
    Write-Host ("=" * 69) -ForegroundColor Green
    if ($DryRun) {
        Write-Host "[OK] Dry run completed successfully!" -ForegroundColor Green
        Write-Host "    Run without -DryRun to perform actual deployment" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Deployment completed successfully!" -ForegroundColor Green
        Write-Host "`nViewer deployed to: ${RemotePath}" -ForegroundColor Yellow
        Write-Host "  Your web server should now serve:" -ForegroundColor Gray
        Write-Host "  - ${RemotePath}/interactive_viewer_advanced.html (main viewer)" -ForegroundColor Cyan
        Write-Host "  - ${RemotePath}/viewer.html (simple viewer)" -ForegroundColor Cyan
        Write-Host "`n  All files use relative paths - no additional config needed!" -ForegroundColor Green
    }
    Write-Host "=" -NoNewline -ForegroundColor Green
    Write-Host ("=" * 69) -ForegroundColor Green
} else {
    Write-Host "`n[X] Deployment failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

