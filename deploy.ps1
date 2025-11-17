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

# Test SSH connection
Write-Host "Testing SSH connection..." -ForegroundColor Yellow

try {
    $sshTest = ssh -o ConnectTimeout=10 -o BatchMode=yes "$remote" "echo 'connected'" 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: SSH connection failed" -ForegroundColor Red
        Write-Host ""
        Write-Host "Output: $sshTest" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Possible issues:" -ForegroundColor Yellow
        Write-Host "  1. SSH key not set up (run: ssh-copy-id $remote)"
        Write-Host "  2. Wrong hostname or username"
        Write-Host "  3. Server not reachable"
        Write-Host ""
        Write-Host "Test manually with: ssh $remote" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "  Connection OK (parallel uploads enabled)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: SSH connection test failed: $_" -ForegroundColor Red
    exit 1
}

# Verify remote path exists (or can be created)
Write-Host "Verifying remote path..." -ForegroundColor Yellow
try {
    if ($useMultiplexing) {
        $pathCheck = ssh -o ControlMaster=auto -o "ControlPath=$controlPath" "$remote" "test -d '$remotePath' && echo 'exists' || (mkdir -p '$remotePath' && echo 'created')" 2>&1
    } else {
        $pathCheck = ssh "$remote" "test -d '$remotePath' && echo 'exists' || (mkdir -p '$remotePath' && echo 'created')" 2>&1
    }
    
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

# Function to get ALL remote file info in ONE SSH call (critical for high-latency connections)
function Get-RemoteFileInfo {
    param(
        [string[]]$RemoteFiles,
        [string]$Remote
    )
    
    # Build script to check all files at once
    $script = @"
for file in $(echo '$($RemoteFiles -join "' '")')'; do
    if [ -f "`$file" ]; then
        size=`$(stat -c '%s' "`$file" 2>/dev/null || echo 0)
        md5=`$(md5sum "`$file" 2>/dev/null | cut -d' ' -f1 || echo 'ERROR')
        echo "`$file|`$size|`$md5"
    else
        echo "`$file|MISSING|MISSING"
    fi
done
"@
    
    # Execute remote script and parse results (reuses multiplexed connection if available)
    if ($useMultiplexing) {
        $output = ssh -o ControlMaster=auto -o "ControlPath=$controlPath" "$Remote" $script 2>$null
    } else {
        $output = ssh "$Remote" $script 2>$null
    }
    
    $remoteInfo = @{}
    foreach ($line in $output) {
        $parts = $line -split '\|'
        if ($parts.Count -eq 3) {
            $remoteInfo[$parts[0]] = @{
                Size = if ($parts[1] -eq 'MISSING') { $null } else { [long]$parts[1] }
                MD5 = if ($parts[2] -eq 'MISSING') { $null } else { $parts[2] }
            }
        }
    }
    
    return $remoteInfo
}

# Files/directories to deploy
$deployItems = @(
    "interactive_viewer_advanced.html",
    "viewer.html",
    "README.md",
    # ".htaccess",  # Manual deployment only - user manages this directly on server
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
if ($skipped -gt 0) {
    Write-Host "  (Skipped $skipped raw .json files - viewer uses .json.gz)" -ForegroundColor DarkGray
}
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
Write-Host "Preparing upload..." -ForegroundColor Yellow
Write-Host ""

# Prioritize upload order: critical manifests FIRST, then code, then region data
$criticalFiles = @()  # Manifests and adjacency data
$priorityFiles = @()  # HTML, JS, CSS, other metadata
$dataFiles = @()      # Individual region .json.gz files

foreach ($localFile in $filesToDeploy) {
    $fileName = Split-Path $localFile -Leaf
    
    # CRITICAL: Upload manifests and adjacency data FIRST
    if ($fileName -match '^(regions_manifest|region_adjacency|us_state_adjacency)\.json\.gz$') {
        $criticalFiles += $localFile
    }
    # PRIORITY: Code and non-data files
    elseif ($localFile -notmatch '\.json\.gz$') {
        # HTML, JS, CSS, favicon, etc.
        $priorityFiles += $localFile
    }
    # DATA: Individual region files (upload last)
    else {
        $dataFiles += $localFile
    }
}

$orderedFiles = $criticalFiles + $priorityFiles + $dataFiles

Write-Host "Upload order:" -ForegroundColor Cyan
Write-Host "  1. Critical manifests: $($criticalFiles.Count) files (regions_manifest, adjacency)" -ForegroundColor Green
Write-Host "  2. Code/metadata: $($priorityFiles.Count) files (HTML, JS, CSS)" -ForegroundColor Yellow
Write-Host "  3. Region data: $($dataFiles.Count) files (individual regions)" -ForegroundColor DarkGray
Write-Host ""

# CRITICAL: Get ALL remote file info in ONE SSH call (fast for high-latency connections)
Write-Host "Checking remote files (one batch check)..." -ForegroundColor Yellow

$remoteFilePaths = @()
foreach ($localFile in $orderedFiles) {
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\'  # Remove leading .\
    $relativePath = $relativePath -replace '\\', '/'  # Convert to Unix paths
    $remoteFilePaths += "$remotePath/$relativePath"
}

$remoteFileInfo = Get-RemoteFileInfo -RemoteFiles $remoteFilePaths -Remote $remote

Write-Host "  Done - checked $($remoteFilePaths.Count) files" -ForegroundColor Green
Write-Host ""

$uploaded = 0
$failed = 0
$skippedIdentical = 0
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
    
    # Check if file already exists and is identical (using batch check from earlier)
    $needsUpload = $true
    $remoteInfo = $remoteFileInfo[$remoteFile]
    
    if ($remoteInfo -and $remoteInfo.Size -ne $null) {
        $localSize = (Get-Item $localFile).Length
        $localMD5 = (Get-FileHash -Path $localFile -Algorithm MD5).Hash.ToLower()
        
        if ($remoteInfo.Size -eq $localSize -and $remoteInfo.MD5 -eq $localMD5) {
            $needsUpload = $false
        }
    }
    
    Write-Host "[$currentFile/$fileCount - $percent%] " -NoNewline -ForegroundColor Cyan
    
    if (-not $needsUpload) {
        Write-Host "Skipped: $relativePath " -NoNewline -ForegroundColor DarkGray
        Write-Host "($fileSizeMB MB) - identical" -ForegroundColor DarkGray
        $skippedIdentical++
        $uploaded++  # Count as "uploaded" for progress
        continue
    }
    
    Write-Host "Uploading: $relativePath " -NoNewline -ForegroundColor Gray
    Write-Host "($fileSizeMB MB)" -ForegroundColor DarkGray
    
    try {
        # Use scp with compression + fast cipher for high-latency connections
        # Add multiplexing if available for MUCH faster transfers
        if ($useMultiplexing) {
            # With multiplexing (60x faster for many files)
            if ($fileSize -gt 1MB) {
                scp -C -c aes128-gcm@openssh.com -o ControlMaster=auto -o "ControlPath=$controlPath" "$localFile" "${remote}:${remoteFile}" 2>$null
            } else {
                scp -C -c aes128-gcm@openssh.com -o ControlMaster=auto -o "ControlPath=$controlPath" -q "$localFile" "${remote}:${remoteFile}" 2>$null
            }
        } else {
            # Without multiplexing (fallback)
            if ($fileSize -gt 1MB) {
                scp -C -c aes128-gcm@openssh.com "$localFile" "${remote}:${remoteFile}" 2>$null
            } else {
                scp -C -c aes128-gcm@openssh.com -q "$localFile" "${remote}:${remoteFile}" 2>$null
            }
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
Write-Host "Uploaded: $($uploaded - $skippedIdentical) files" -ForegroundColor Green
if ($skippedIdentical -gt 0) {
    Write-Host "Skipped: $skippedIdentical files (already up-to-date)" -ForegroundColor Cyan
}
if ($failed -gt 0) {
    Write-Host "Failed: $failed files" -ForegroundColor Red
}
Write-Host "Total size: $totalSizeMB MB" -ForegroundColor Cyan
Write-Host "Time: $elapsedSeconds seconds" -ForegroundColor Cyan
Write-Host ""

# Clean up SSH connection multiplexing (if used)
if ($useMultiplexing) {
    ssh -o ControlMaster=auto -o "ControlPath=$controlPath" -O exit "$remote" 2>$null | Out-Null
    Remove-Item -Path $controlPath -ErrorAction SilentlyContinue
}

Write-Host "Live at: https://fuseki.net/altitude-maps/advanced-viewer.html" -ForegroundColor Cyan
