# Generate rsync commands for deployment
# Usage: .\generate_rsync_commands.ps1 > deploy.sh
#        Then run: bash deploy.sh (from Ubuntu/WSL)

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

$remote = "$($env:REMOTE_USER)@$($env:REMOTE_HOST)"
# Normalize remote path: remove trailing slash, ensure forward slashes
$remotePath = $env:REMOTE_PATH.TrimEnd('/').Replace('\', '/')

# Build SSH options
$sshOpts = ""
if ($env:SSH_KEY) {
    $sshOpts = "-e 'ssh -i $env:SSH_KEY'"
}

# Files to deploy
$deployItems = @(
    "interactive_viewer_advanced.html",
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
            }
        } else {
            $file = Get-Item $item
            $filesToDeploy += $file.FullName
        }
    }
}

# Get project root directory
$projectRoot = (Get-Location).Path

# Output bash script header
Write-Host "#!/bin/bash"
Write-Host "set -e"
Write-Host ""

# Convert Windows path to WSL path
function ConvertTo-WSLPath {
    param([string]$WindowsPath)
    # Convert D:\path\to\file -> /mnt/d/path/to/file
    if ($WindowsPath -match '^([A-Z]):') {
        $drive = $matches[1].ToLower()
        $wslPath = $WindowsPath -replace '^[A-Z]:', "/mnt/$drive"
    } else {
        $wslPath = $WindowsPath
    }
    $wslPath = $wslPath -replace '\\', '/'
    return $wslPath
}

# Get WSL project root
$wslProjectRoot = ConvertTo-WSLPath $projectRoot

# Build rsync command arguments
$rsyncSources = @()
$rsyncExcludes = @()

# Group files by their top-level directory/item
$itemsToSync = @{}

foreach ($localFile in $filesToDeploy) {
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\', ''
    
    # Get top-level item (e.g., "js", "css", "generated", or filename like "interactive_viewer_advanced.html")
    $topLevel = $relativePath.Split('\')[0]
    
    if (-not $itemsToSync.ContainsKey($topLevel)) {
        $itemsToSync[$topLevel] = @()
    }
    $itemsToSync[$topLevel] += $localFile
}

# Build single rsync command with all sources
Write-Host "echo 'Deploying files to $remote`:$remotePath'"
Write-Host ""

# Add each top-level item as a source
foreach ($topLevel in $itemsToSync.Keys | Sort-Object) {
    $localItem = Get-Item $topLevel
    $wslItemPath = ConvertTo-WSLPath $localItem.FullName
    
    if ($localItem -is [System.IO.DirectoryInfo]) {
        # For directories, sync the whole directory
        $rsyncSources += "'$wslItemPath/'"
    } else {
        # For files, add the file path
        $rsyncSources += "'$wslItemPath'"
    }
}

# Build exclude patterns for raw .json files (keep .json.gz)
# *.json pattern only matches files ending in .json, not .json.gz
$rsyncExcludes += "--exclude='*.json'"

# Build the single rsync command
$rsyncCmd = "rsync -av --checksum --mkpath"

# Add excludes
foreach ($exclude in $rsyncExcludes) {
    $rsyncCmd += " $exclude"
}

# Add SSH options if needed
if ($env:SSH_KEY) {
    $rsyncCmd += " -e `"ssh -i $env:SSH_KEY`""
}

# Add all sources
$rsyncCmd += " " + ($rsyncSources -join " ")

# Add remote destination
$rsyncCmd += " '${remote}:${remotePath}/'"

Write-Host $rsyncCmd
Write-Host ""
Write-Host "echo 'Deployment complete!'"

