# Native PowerShell deployment using SCP (built into Windows 10+)
# No rsync needed - uses Windows OpenSSH client
#
# Usage:
#   .\deploy.ps1 -Preview  # Show what would be uploaded
#   .\deploy.ps1 -Deploy   # Actually deploy

param(
    [switch]$Preview,
    [switch]$Deploy
)

if (-not $Preview -and -not $Deploy) {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\deploy.ps1 -Preview  # Preview files (dry run)"
    Write-Host "  .\deploy.ps1 -Deploy   # Deploy to server"
    exit 0
}

# Load configuration
if (-not (Test-Path "deploy-config.ps1")) {
    Write-Host "ERROR: deploy-config.ps1 not found" -ForegroundColor Red
    Write-Host "Copy from deploy-config.example.ps1 and edit with your server details"
    exit 1
}

. .\deploy-config.ps1

if (-not $env:REMOTE_HOST) {
    Write-Host "ERROR: deploy-config.ps1 not properly configured" -ForegroundColor Red
    exit 1
}

# Check SCP (built into Windows 10+)
try {
    $null = Get-Command scp -ErrorAction Stop
} catch {
    Write-Host "ERROR: scp not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install OpenSSH Client:" -ForegroundColor Yellow
    Write-Host "  1. Open Settings > Apps > Optional Features"
    Write-Host "  2. Click 'Add a feature'"
    Write-Host "  3. Search for 'OpenSSH Client'"
    Write-Host "  4. Install it"
    Write-Host ""
    Write-Host "Or via PowerShell (as admin):" -ForegroundColor Yellow
    Write-Host "  Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
    exit 1
}

$remote = "$($env:REMOTE_USER)@$($env:REMOTE_HOST)"
$remotePath = $env:REMOTE_PATH

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Deploying to: $remote`:$remotePath" -ForegroundColor Cyan
if ($Preview) {
    Write-Host "MODE: PREVIEW (listing files, no upload)" -ForegroundColor Yellow
} else {
    Write-Host "MODE: DEPLOYING" -ForegroundColor Green
}
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Test SSH connection first
Write-Host "Testing SSH connection..." -ForegroundColor Yellow
try {
    $testResult = ssh -o ConnectTimeout=10 -o BatchMode=yes "$remote" "echo 'connected'" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: SSH connection failed" -ForegroundColor Red
        Write-Host ""
        Write-Host "Possible issues:" -ForegroundColor Yellow
        Write-Host "  1. SSH key not set up (run: ssh-copy-id $remote)"
        Write-Host "  2. Wrong hostname or username"
        Write-Host "  3. Server not reachable"
        Write-Host ""
        Write-Host "Test manually with: ssh $remote" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "  Connection OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: SSH connection test failed: $_" -ForegroundColor Red
    exit 1
}

# Verify remote path exists (or can be created)
Write-Host "Verifying remote path..." -ForegroundColor Yellow
try {
    $pathCheck = ssh "$remote" "test -d '$remotePath' && echo 'exists' || (mkdir -p '$remotePath' && echo 'created')" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Cannot access or create remote path: $remotePath" -ForegroundColor Red
        Write-Host "Check that you have write permissions on the server" -ForegroundColor Yellow
        exit 1
    }
    
    if ($pathCheck -match "created") {
        Write-Host "  Created remote directory: $remotePath" -ForegroundColor Green
    } else {
        Write-Host "  Remote path exists" -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Failed to verify remote path: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Files/directories to deploy
$deployItems = @(
    "interactive_viewer_advanced.html",
    "viewer.html",
    "README.md",
    "js",
    "css",
    "generated",
    "favicon.ico",
    "favicon.svg",
    "favicon-180.png",
    "favicon-192.png",
    "favicon-512.png"
)

# Get list of files that exist
$filesToDeploy = @()
$totalSize = 0
$skipped = 0

foreach ($item in $deployItems) {
    if (Test-Path $item) {
        if ((Get-Item $item) -is [System.IO.DirectoryInfo]) {
            # Directory - get all files recursively
            $files = Get-ChildItem -Path $item -Recurse -File
            foreach ($file in $files) {
                # CRITICAL: Skip raw .json files (viewer only uses .json.gz)
                # Skip: region_name.json, meta.json (but keep: file.json.gz)
                if ($file.Name -match '\.json$' -and $file.Name -notmatch '\.json\.gz$') {
                    $skipped++
                    continue  # Skip raw JSON - not used in production
                }
                
                $filesToDeploy += $file.FullName
                $totalSize += $file.Length
            }
        } else {
            # Single file
            $file = Get-Item $item
            $filesToDeploy += $file.FullName
            $totalSize += $file.Length
        }
    }
}

$totalSizeMB = [math]::Round($totalSize / 1MB, 2)
$fileCount = $filesToDeploy.Count

Write-Host "Files to deploy: $fileCount ($totalSizeMB MB)" -ForegroundColor Cyan
Write-Host ""

if ($Preview) {
    Write-Host "Preview - files that would be uploaded:" -ForegroundColor Yellow
    Write-Host ""
    
    # Group by directory for cleaner output
    $byDirectory = $filesToDeploy | Group-Object { Split-Path $_ -Parent }
    
    foreach ($group in $byDirectory | Sort-Object Name) {
        $dir = if ($group.Name) { $group.Name } else { "." }
        Write-Host "$dir/" -ForegroundColor Cyan
        foreach ($file in $group.Group | Sort-Object) {
            $name = Split-Path $file -Leaf
            $size = (Get-Item $file).Length
            $sizeKB = [math]::Round($size / 1KB, 1)
            Write-Host "  $name" -NoNewline
            Write-Host " ($sizeKB KB)" -ForegroundColor DarkGray
        }
    }
    
    Write-Host ""
    Write-Host "Total: $fileCount files, $totalSizeMB MB" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run with -Deploy to actually upload" -ForegroundColor Yellow
    exit 0
}

# Deploy mode - actually upload files
Write-Host "Uploading files..." -ForegroundColor Yellow
Write-Host ""

# Prioritize upload order: metadata/manifests/code first, raw data (.gz) last
$priorityFiles = @()
$dataFiles = @()

foreach ($localFile in $filesToDeploy) {
    if ($localFile -match '\.gz$') {
        # Raw compressed region data - upload last
        $dataFiles += $localFile
    } else {
        # Manifest, HTML, JS, CSS, JSON metadata - upload first
        $priorityFiles += $localFile
    }
}

$orderedFiles = $priorityFiles + $dataFiles

Write-Host "Upload order: $($priorityFiles.Count) metadata/code files, then $($dataFiles.Count) data files" -ForegroundColor Cyan
Write-Host ""

$uploaded = 0
$failed = 0
$startTime = Get-Date
$currentFile = 0

foreach ($localFile in $orderedFiles) {
    $currentFile++
    
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\'  # Remove leading .\
    $relativePath = $relativePath -replace '\\', '/'  # Convert to Unix paths
    
    $remoteFile = "$remotePath/$relativePath"
    $remoteDir = Split-Path $remoteFile -Parent
    
    # Progress indicator
    $percent = [math]::Round(($currentFile / $fileCount) * 100, 1)
    $fileSize = (Get-Item $localFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    
    # Ensure remote directory exists
    # ssh "$remote" "mkdir -p '$remoteDir'" 2>$null
    
    # Upload file with progress
    Write-Host "[$currentFile/$fileCount - $percent%] " -NoNewline -ForegroundColor Cyan
    Write-Host "Uploading: $relativePath " -NoNewline -ForegroundColor Gray
    Write-Host "($fileSizeMB MB)" -ForegroundColor DarkGray
    
    try {
        # Use scp with compression (-C) for faster transfers over high-latency connections
        # Cipher aes128-gcm@openssh.com is faster than default
        if ($fileSize -gt 1MB) {
            # Show per-file progress for large files
            scp -C -c aes128-gcm@openssh.com "$localFile" "${remote}:${remoteFile}" 2>$null
        } else {
            # Quiet mode for small files, with compression
            scp -C -c aes128-gcm@openssh.com -q "$localFile" "${remote}:${remoteFile}" 2>$null
        }
        
        if ($LASTEXITCODE -eq 0) {
            $uploaded++
        } else {
            Write-Host "  FAILED: $relativePath" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  FAILED: $relativePath - $_" -ForegroundColor Red
        $failed++
    }
}

$elapsed = (Get-Date) - $startTime
$elapsedSeconds = [math]::Round($elapsed.TotalSeconds, 1)

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Green
Write-Host ""
Write-Host "Uploaded: $uploaded files ($totalSizeMB MB)" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "Failed: $failed files" -ForegroundColor Red
}
Write-Host "Time: $elapsedSeconds seconds" -ForegroundColor Cyan
Write-Host ""
Write-Host "Live at: https://fuseki.net/altitude-maps/advanced-viewer.html" -ForegroundColor Cyan

