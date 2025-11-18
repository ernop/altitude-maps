# Simple file upload to remote server using SCP
# Usage: .\deploy.ps1 -Preview  # Show what would be uploaded
#        .\deploy.ps1 -Deploy  # Upload files

param(
    [switch]$Preview,
    [switch]$Deploy
)

if (-not $Preview -and -not $Deploy) {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\deploy.ps1 -Preview  # Preview files"
    Write-Host "  .\deploy.ps1 -Deploy   # Upload files"
    exit 0
}

# Load configuration
if (-not (Test-Path "deploy-config.ps1")) {
    Write-Host "ERROR: deploy-config.ps1 not found" -ForegroundColor Red
    Write-Host "Copy from deploy-config.example.ps1 and edit with your server details"
    exit 1
}

. .\deploy-config.ps1

if (-not $env:REMOTE_HOST -or -not $env:REMOTE_USER -or -not $env:REMOTE_PATH) {
    Write-Host "ERROR: deploy-config.ps1 not properly configured" -ForegroundColor Red
    exit 1
}

# Check SCP
try {
    $null = Get-Command scp -ErrorAction Stop
} catch {
    Write-Host "ERROR: scp not found" -ForegroundColor Red
    Write-Host "Install OpenSSH Client via Windows Settings > Apps > Optional Features"
    exit 1
}

$remote = "$($env:REMOTE_USER)@$($env:REMOTE_HOST)"
$remotePath = $env:REMOTE_PATH

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Deploying to: $remote`:$remotePath" -ForegroundColor Cyan
if ($Preview) {
    Write-Host "MODE: PREVIEW" -ForegroundColor Yellow
} else {
    Write-Host "MODE: DEPLOYING" -ForegroundColor Green
}
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Setup SSH connection multiplexing (reuse connection for all SCP calls - MUCH faster)
$controlPath = "$env:TEMP\ssh_control_$($env:REMOTE_HOST.Replace('.', '_'))"
$useMultiplexing = $false

if (-not $Preview) {
    Write-Host "Setting up SSH connection multiplexing..." -ForegroundColor Yellow
    try {
        # Open master connection
        ssh -o ControlMaster=yes -o ControlPath=$controlPath -o ControlPersist=300 -f -N "$remote" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $useMultiplexing = $true
            Write-Host "  Connection multiplexing enabled (reusing connection for all files)" -ForegroundColor Green
        } else {
            Write-Host "  Multiplexing failed, using standard connections" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  Multiplexing failed, using standard connections" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Test SSH connection
Write-Host "Testing SSH connection..." -ForegroundColor Yellow
try {
    if ($useMultiplexing) {
        $sshTest = ssh -o ControlMaster=auto -o ControlPath=$controlPath -o ConnectTimeout=10 "$remote" "echo 'connected'" 2>&1
    } else {
        $sshTest = ssh -o ConnectTimeout=10 -o BatchMode=yes "$remote" "echo 'connected'" 2>&1
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: SSH connection failed" -ForegroundColor Red
        Write-Host "Test manually with: ssh $remote" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  Connection OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: SSH connection test failed" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Files to deploy
$deployItems = @(
    "interactive_viewer_advanced.html",
    "viewer.html",
    "js",
    "css",
    "generated",
    "favicon.ico",
    "favicon.svg",
    "favicon-180.png",
    "favicon-192.png",
    "favicon-512.png"
)

# Collect all files
$filesToDeploy = @()
$totalSize = 0

foreach ($item in $deployItems) {
    if (Test-Path $item) {
        if ((Get-Item $item) -is [System.IO.DirectoryInfo]) {
            $files = Get-ChildItem -Path $item -Recurse -File
            foreach ($file in $files) {
                # Skip raw .json files (only deploy .json.gz)
                if ($file.Name -match '\.json$' -and $file.Name -notmatch '\.json\.gz$') {
                    continue
                }
                $filesToDeploy += $file.FullName
                $totalSize += $file.Length
            }
        } else {
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

# Preview mode
if ($Preview) {
    Write-Host "Preview - files that would be uploaded:" -ForegroundColor Yellow
    Write-Host ""
    
    $byDirectory = $filesToDeploy | Group-Object { Split-Path $_ -Parent }
    foreach ($group in $byDirectory | Sort-Object Name) {
        $dir = if ($group.Name) { $group.Name } else { "." }
        Write-Host "$dir/" -ForegroundColor Cyan
        foreach ($file in $group.Group | Sort-Object) {
            $name = Split-Path $file -Leaf
            $size = (Get-Item $file).Length
            $sizeKB = [math]::Round($size / 1KB, 1)
            Write-Host "  $name ($sizeKB KB)" -ForegroundColor DarkGray
        }
    }
    
    Write-Host ""
    Write-Host "Total: $fileCount files, $totalSizeMB MB" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run with -Deploy to upload" -ForegroundColor Yellow
    exit 0
}

# Deploy mode - upload files
Write-Host "Uploading files..." -ForegroundColor Yellow
Write-Host ""

# Pre-create all needed directories (one SSH call instead of 116)
Write-Host "Creating remote directories..." -ForegroundColor Yellow
$uniqueDirs = $filesToDeploy | ForEach-Object {
    $relativePath = Resolve-Path -Relative $_
    $relativePath = $relativePath -replace '^\.\\', ''
    $relativePath = $relativePath -replace '\\', '/'
    $remoteFile = "$remotePath/$relativePath"
    Split-Path $remoteFile -Parent
} | Sort-Object -Unique

$dirsToCreate = $uniqueDirs | Where-Object { $_ -ne $remotePath -and $_ -ne '' }
if ($dirsToCreate.Count -gt 0) {
    $dirsCommand = ($dirsToCreate | ForEach-Object { "mkdir -p '$_'" }) -join ' && '
    if ($useMultiplexing) {
        ssh -o ControlMaster=auto -o ControlPath=$controlPath -o ConnectTimeout=10 "$remote" $dirsCommand 2>&1 | Out-Null
    } else {
        ssh -o ConnectTimeout=10 "$remote" $dirsCommand 2>&1 | Out-Null
    }
}
Write-Host "  Done" -ForegroundColor Green
Write-Host ""

$uploaded = 0
$failed = 0
$startTime = Get-Date

foreach ($localFile in $filesToDeploy) {
    $uploaded++
    
    # Calculate relative path
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\', ''
    $relativePath = $relativePath -replace '\\', '/'
    
    $remoteFile = "$remotePath/$relativePath"
    
    # Progress
    $percent = [math]::Round(($uploaded / $fileCount) * 100, 1)
    $fileSize = (Get-Item $localFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    
    Write-Host "[$uploaded/$fileCount - $percent%] " -NoNewline -ForegroundColor Cyan
    Write-Host "Uploading: $relativePath " -NoNewline -ForegroundColor Gray
    Write-Host "($fileSizeMB MB)" -ForegroundColor DarkGray
    Write-Host "  Remote: $remoteFile" -ForegroundColor DarkGray
    
    # Upload file (use multiplexing if available, -C for compression)
    if ($useMultiplexing) {
        $scpOutput = scp -C -o ControlMaster=auto -o ControlPath=$controlPath "$localFile" "${remote}:${remoteFile}" 2>&1
    } else {
        $scpOutput = scp -C "$localFile" "${remote}:${remoteFile}" 2>&1
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Done" -ForegroundColor Green
    } else {
        Write-Host "  FAILED" -ForegroundColor Red
        if ($scpOutput) {
            Write-Host "  Error: $scpOutput" -ForegroundColor Red
        }
        $failed++
    }
}

$elapsed = (Get-Date) - $startTime
$elapsedSeconds = [math]::Round($elapsed.TotalSeconds, 1)

Write-Host ""

# Clean up SSH connection multiplexing
if ($useMultiplexing) {
    ssh -o ControlMaster=auto -o ControlPath=$controlPath -O exit "$remote" 2>&1 | Out-Null
    Remove-Item -Path $controlPath -ErrorAction SilentlyContinue
}

Write-Host "=" * 70 -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Green
Write-Host ""
Write-Host "Uploaded: $uploaded files" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "Failed: $failed files" -ForegroundColor Red
}
Write-Host "Total size: $totalSizeMB MB" -ForegroundColor Cyan
Write-Host "Time: $elapsedSeconds seconds" -ForegroundColor Cyan
if ($useMultiplexing) {
    Write-Host "Connection multiplexing: Enabled (faster)" -ForegroundColor Green
}
Write-Host ""
