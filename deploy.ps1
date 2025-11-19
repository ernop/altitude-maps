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
        # Open master connection with explicit timeout to prevent hanging
        $multiplexArgs = @(
            "-o", "ControlMaster=yes",
            "-o", "ControlPath=$controlPath",
            "-o", "ControlPersist=300",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "-f", "-N",
            "$remote"
        )
        ssh $multiplexArgs 2>&1 | Out-Null
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
    # Use explicit timeout and batch mode to prevent hanging
    $sshArgs = @(
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=no"
    )
    
    if ($useMultiplexing) {
        $sshArgs += "-o", "ControlMaster=auto", "-o", "ControlPath=$controlPath"
    }
    
    $sshArgs += "$remote", "echo 'connected'"
    
    $sshTest = & ssh $sshArgs 2>&1
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -ne 0) {
        Write-Host "ERROR: SSH connection failed (exit code: $exitCode)" -ForegroundColor Red
        if ($sshTest) {
            Write-Host "Output: $sshTest" -ForegroundColor DarkGray
        }
        Write-Host "Test manually with: ssh $remote" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  Connection OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: SSH connection test failed" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
    exit 1
}

Write-Host ""

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

# Check remote file modification dates and sizes to skip unchanged files
Write-Host "Checking remote file modification dates and sizes..." -ForegroundColor Yellow
$remoteFileInfo = @{}
$filesToCheck = @()

foreach ($localFile in $filesToDeploy) {
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\', ''
    $relativePath = $relativePath -replace '\\', '/'
    $remoteFile = "$remotePath/$relativePath"
    $filesToCheck += $remoteFile
}

# Helper function to run SSH with PowerShell-level timeout
function Invoke-SSHWithTimeout {
    param(
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 15
    )
    
    $output = ""
    $exitCode = 0
    
    $job = Start-Job -ScriptBlock {
        param($sshArgs)
        $output = & ssh $sshArgs 2>&1
        $exitCode = $LASTEXITCODE
        return @{
            Output = $output
            ExitCode = $exitCode
        }
    } -ArgumentList (,$Arguments)
    
    $result = Wait-Job -Job $job -Timeout $TimeoutSeconds
    
    if ($result) {
        $jobResult = Receive-Job -Job $job
        Remove-Job -Job $job -Force
        return $jobResult
    } else {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force
        throw "SSH command timed out after $TimeoutSeconds seconds"
    }
}

# Batch check all remote files in one SSH call (much faster)
if ($filesToCheck.Count -gt 0) {
    # First, test that we can run commands on remote
    Write-Host "  Testing remote command execution..." -ForegroundColor Yellow
    # Test with a simple command first, then check if stat exists
    $testCmd = "which stat >/dev/null 2>&1 && echo 'stat-found' || echo 'stat-not-found'"
    
    $testArgs = @(
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes"
    )
    
    if ($useMultiplexing) {
        $testArgs += "-o", "ControlMaster=auto", "-o", "ControlPath=$controlPath"
    }
    
    $testArgs += "$remote", $testCmd
    
    try {
        $testResult = Invoke-SSHWithTimeout -Arguments $testArgs -TimeoutSeconds 15
        $testOutput = if ($testResult.Output -is [array]) { $testResult.Output -join "`n" } else { $testResult.Output }
        $testExitCode = $testResult.ExitCode
    } catch {
        Write-Host "  ERROR: SSH command timed out or failed" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
        Write-Host "  ERROR: Cannot proceed without file comparison - aborting" -ForegroundColor Red
        exit 1
    }
    
    if ($testExitCode -ne 0) {
        Write-Host "  ERROR: Cannot execute commands on remote server (exit code: $testExitCode)" -ForegroundColor Red
        if ($testOutput) {
            Write-Host "  Test output: $testOutput" -ForegroundColor DarkGray
        }
        Write-Host "  ERROR: Cannot proceed without file comparison - aborting" -ForegroundColor Red
        exit 1
    }
    
    if ($testOutput -match 'stat-not-found') {
        Write-Host "  ERROR: 'stat' command not found on remote server" -ForegroundColor Red
        Write-Host "  ERROR: Cannot proceed without file comparison - aborting" -ForegroundColor Red
        exit 1
    }
    
    # Build bash script with proper escaping
    $fileList = $filesToCheck | ForEach-Object {
        # Escape single quotes in paths: ' becomes '\''
        $escaped = $_ -replace "'", "'\''"
        "  '$escaped'"
    } | Out-String
    
    $checkScript = @"
files=(
$fileList)
for file in "`${files[@]}"; do
  if [ -f "`$file" ]; then
    stat -c "%Y|%s|%n" "`$file" 2>/dev/null || echo "0|0|`$file"
  else
    echo "0|0|`$file"
  fi
done
"@
    
    try {
        # Use temp file approach for reliability (PowerShell piping can be unreliable)
        $tempScript = [System.IO.Path]::GetTempFileName()
        $checkScript | Out-File -FilePath $tempScript -Encoding UTF8 -NoNewline
        
        try {
            # Copy script to remote, execute it, then remove it
            $randomSuffix = Get-Random -Minimum 10000 -Maximum 99999
            $remoteScriptPath = "/tmp/deploy_check_$randomSuffix.sh"
            $scpArgs = @(
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes"
            )
            
            if ($useMultiplexing) {
                $scpArgs += "-o", "ControlMaster=auto", "-o", "ControlPath=$controlPath"
            }
            
            $scpArgs += "$tempScript", "${remote}:${remoteScriptPath}"
            
            $scpOutput = & scp $scpArgs 2>&1
            $scpExitCode = $LASTEXITCODE
            
            if ($scpExitCode -ne 0) {
                Write-Host "  ERROR: Failed to copy script to remote (exit code: $scpExitCode)" -ForegroundColor Red
                if ($scpOutput) {
                    Write-Host "  SCP output: $scpOutput" -ForegroundColor DarkGray
                }
                throw "Failed to copy script to remote"
            }
            
            # Execute script on remote (always clean up script afterwards)
            $execArgs = @(
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes"
            )
            
            if ($useMultiplexing) {
                $execArgs += "-o", "ControlMaster=auto", "-o", "ControlPath=$controlPath"
            }
            
            $execCmd = "bash $remoteScriptPath; rm -f $remoteScriptPath"
            $execArgs += "$remote", $execCmd
            
            try {
                $execResult = Invoke-SSHWithTimeout -Arguments $execArgs -TimeoutSeconds 60
                $remoteStats = if ($execResult.Output -is [array]) { $execResult.Output } else { @($execResult.Output) }
                $exitCode = $execResult.ExitCode
            } catch {
                Write-Host "  ERROR: Script execution timed out or failed" -ForegroundColor Red
                Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
                throw "Failed to execute script on remote"
            }
        } finally {
            # Clean up local temp file
            Remove-Item -Path $tempScript -ErrorAction SilentlyContinue
        }
        
        if ($exitCode -eq 0) {
            $parsedCount = 0
            $remoteStats | ForEach-Object {
                $line = $_.Trim()
                if ($line -match '^(\d+)\|(\d+)\|(.+)$') {
                    $timestamp = [int64]$matches[1]
                    $fileSize = [int64]$matches[2]
                    $filePath = $matches[3]
                    if ($timestamp -gt 0) {
                        $remoteFileInfo[$filePath] = @{
                            ModDate = [DateTimeOffset]::FromUnixTimeSeconds($timestamp).DateTime
                            Size = $fileSize
                        }
                        $parsedCount++
                    }
                }
            }
            Write-Host "  Checked $parsedCount remote files" -ForegroundColor Green
        } else {
            Write-Host "  ERROR: Remote file check failed (exit code: $exitCode)" -ForegroundColor Red
            Write-Host "  Output:" -ForegroundColor Yellow
            $remoteStats | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
            Write-Host "  ERROR: Cannot proceed without file comparison - aborting" -ForegroundColor Red
            Write-Host "  Fix the SSH connection or remote path and try again" -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "  ERROR: Exception during remote file check" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  ERROR: Cannot proceed without file comparison - aborting" -ForegroundColor Red
        Write-Host "  Fix the SSH connection or remote path and try again" -ForegroundColor Yellow
        exit 1
    }
}

# Filter files that haven't changed
$filesChanged = @()
$filesSkipped = @()
$skippedSize = 0

foreach ($localFile in $filesToDeploy) {
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\', ''
    $relativePath = $relativePath -replace '\\', '/'
    $remoteFile = "$remotePath/$relativePath"
    
    $localModDate = (Get-Item $localFile).LastWriteTime
    $localSize = (Get-Item $localFile).Length
    
    if ($remoteFileInfo.ContainsKey($remoteFile)) {
        $remoteInfo = $remoteFileInfo[$remoteFile]
        $remoteModDate = $remoteInfo.ModDate
        $remoteSize = $remoteInfo.Size
        
        # Skip if modification date matches (within 1 second tolerance) AND size matches
        $timeDiff = ($localModDate - $remoteModDate).TotalSeconds
        $sizeMatches = ($localSize -eq $remoteSize)
        
        if ($timeDiff -le 1 -and $timeDiff -ge -1 -and $sizeMatches) {
            $filesSkipped += $localFile
            $skippedSize += $localSize
            Write-Host "  Skipping (identical): $relativePath" -ForegroundColor DarkGray
            continue
        }
    }
    
    $filesChanged += $localFile
}

$changedCount = $filesChanged.Count
$skippedCount = $filesSkipped.Count
$changedSizeMB = [math]::Round(($totalSize - $skippedSize) / 1MB, 2)
$skippedSizeMB = [math]::Round($skippedSize / 1MB, 2)

Write-Host "  Changed: $changedCount files ($changedSizeMB MB)" -ForegroundColor Green
if ($skippedCount -gt 0) {
    Write-Host "  Skipped (unchanged): $skippedCount files ($skippedSizeMB MB)" -ForegroundColor DarkGray
}
Write-Host ""

# Preview mode
if ($Preview) {
    Write-Host "Preview - files that would be uploaded:" -ForegroundColor Yellow
    Write-Host ""
    
    if ($filesChanged.Count -gt 0) {
        $byDirectory = $filesChanged | Group-Object { Split-Path $_ -Parent }
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
    } else {
        Write-Host "  (no files changed)" -ForegroundColor DarkGray
    }
    
    if ($filesSkipped.Count -gt 0) {
        Write-Host ""
        Write-Host "Skipped (unchanged):" -ForegroundColor DarkGray
        $byDirectory = $filesSkipped | Group-Object { Split-Path $_ -Parent }
        foreach ($group in $byDirectory | Sort-Object Name) {
            $dir = if ($group.Name) { $group.Name } else { "." }
            Write-Host "$dir/" -ForegroundColor DarkGray
            foreach ($file in $group.Group | Sort-Object) {
                $name = Split-Path $file -Leaf
                $size = (Get-Item $file).Length
                $sizeKB = [math]::Round($size / 1KB, 1)
                Write-Host "  $name ($sizeKB KB) [skipped]" -ForegroundColor DarkGray
            }
        }
    }
    
    Write-Host ""
    Write-Host "Total: $fileCount files ($totalSizeMB MB)" -ForegroundColor Cyan
    Write-Host "  Changed: $changedCount files ($changedSizeMB MB)" -ForegroundColor Green
    if ($skippedCount -gt 0) {
        Write-Host "  Skipped: $skippedCount files ($skippedSizeMB MB)" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "Run with -Deploy to upload" -ForegroundColor Yellow
    exit 0
}

# Deploy mode - upload files
if ($filesChanged.Count -eq 0) {
    Write-Host "No files to upload - all files are up to date" -ForegroundColor Green
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Green
    Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
    Write-Host "=" * 70 -ForegroundColor Green
    Write-Host ""
    Write-Host "Uploaded: 0 files" -ForegroundColor Green
    Write-Host "Skipped: $skippedCount files ($skippedSizeMB MB)" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

Write-Host "Uploading $changedCount changed files..." -ForegroundColor Yellow
Write-Host ""

# Pre-create all needed directories (one SSH call instead of 116)
Write-Host "Creating remote directories..." -ForegroundColor Yellow
$uniqueDirs = $filesChanged | ForEach-Object {
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

foreach ($localFile in $filesChanged) {
    $uploaded++
    
    # Calculate relative path
    $relativePath = Resolve-Path -Relative $localFile
    $relativePath = $relativePath -replace '^\.\\', ''
    $relativePath = $relativePath -replace '\\', '/'
    
    $remoteFile = "$remotePath/$relativePath"
    
    # Progress
    $percent = [math]::Round(($uploaded / $changedCount) * 100, 1)
    $fileSize = (Get-Item $localFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    
    Write-Host "[$uploaded/$changedCount - $percent%] " -NoNewline -ForegroundColor Cyan
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
Write-Host "Uploaded: $uploaded files ($changedSizeMB MB)" -ForegroundColor Green
if ($skippedCount -gt 0) {
    Write-Host "Skipped (unchanged): $skippedCount files ($skippedSizeMB MB)" -ForegroundColor DarkGray
}
if ($failed -gt 0) {
    Write-Host "Failed: $failed files" -ForegroundColor Red
}
Write-Host "Total size: $totalSizeMB MB" -ForegroundColor Cyan
Write-Host "Time: $elapsedSeconds seconds" -ForegroundColor Cyan
if ($useMultiplexing) {
    Write-Host "Connection multiplexing: Enabled (faster)" -ForegroundColor Green
}
Write-Host ""
