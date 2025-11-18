# check_release_status.ps1
# Report current release readiness status
# Usage: .\check_release_status.ps1

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Release Status Check" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

$allChecksPassed = $true

# 1. Check current version
Write-Host "Version Information:" -ForegroundColor Yellow
try {
    $jsFile = Get-Content "js/viewer-advanced.js" -Raw -ErrorAction Stop
    $versionMatch = [regex]::Match($jsFile, "const VIEWER_VERSION = '([^']+)';")
    if ($versionMatch.Success) {
        $currentVersion = $versionMatch.Groups[1].Value
        Write-Host "  Current Version: $currentVersion" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Could not find VIEWER_VERSION in js/viewer-advanced.js" -ForegroundColor Red
        $allChecksPassed = $false
    }
} catch {
    Write-Host "  ERROR: Could not read js/viewer-advanced.js" -ForegroundColor Red
    Write-Host "    $($_.Exception.Message)" -ForegroundColor DarkGray
    $allChecksPassed = $false
}
Write-Host ""

# 2. Check required files exist
Write-Host "Required Files:" -ForegroundColor Yellow
$requiredFiles = @(
    @{Path="interactive_viewer_advanced.html"; Name="Main HTML viewer"},
    @{Path="js/viewer-advanced.js"; Name="Main JavaScript"},
    @{Path="css/viewer-advanced.css"; Name="Main stylesheet"},
    @{Path="generated/regions/regions_manifest.json.gz"; Name="Regions manifest"}
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file.Path) {
        $size = (Get-Item $file.Path).Length
        $sizeKB = [math]::Round($size / 1KB, 1)
        Write-Host "  [OK] $($file.Name): $sizeKB KB" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $($file.Name): $($file.Path)" -ForegroundColor Red
        $allChecksPassed = $false
    }
}
Write-Host ""

# 3. Count deployable files
Write-Host "Deployable Files:" -ForegroundColor Yellow
try {
    $jsFiles = (Get-ChildItem "js/*.js" -ErrorAction Stop).Count
    Write-Host "  JavaScript files: $jsFiles" -ForegroundColor Cyan
} catch {
    Write-Host "  JavaScript files: ERROR - js/ directory not found" -ForegroundColor Red
    $allChecksPassed = $false
}

try {
    $cssFiles = (Get-ChildItem "css/*.css" -ErrorAction Stop).Count
    Write-Host "  CSS files: $cssFiles" -ForegroundColor Cyan
} catch {
    Write-Host "  CSS files: ERROR - css/ directory not found" -ForegroundColor Red
    $allChecksPassed = $false
}

try {
    $regionFiles = (Get-ChildItem "generated/regions/*.json.gz" -Exclude "*manifest*", "*adjacency*" -ErrorAction Stop).Count
    Write-Host "  Region data files: $regionFiles" -ForegroundColor Cyan
} catch {
    Write-Host "  Region data files: ERROR - generated/regions/ directory not found" -ForegroundColor Red
    $allChecksPassed = $false
}

try {
    $manifestFiles = (Get-ChildItem "generated/regions/*manifest*.json.gz" -ErrorAction Stop).Count
    Write-Host "  Manifest files: $manifestFiles" -ForegroundColor Cyan
} catch {
    Write-Host "  Manifest files: ERROR" -ForegroundColor Red
    $allChecksPassed = $false
}
Write-Host ""

# 4. Check deployment configuration
Write-Host "Deployment Configuration:" -ForegroundColor Yellow
if (Test-Path "deploy-config.ps1") {
    Write-Host "  [OK] deploy-config.ps1 exists" -ForegroundColor Green
    
    # Try to load it (but don't fail if it has errors - just warn)
    try {
        $null = . .\deploy-config.ps1 2>&1
        if ($env:REMOTE_HOST -and $env:REMOTE_USER -and $env:REMOTE_PATH) {
            Write-Host "  [OK] Configuration loaded: $env:REMOTE_USER@$env:REMOTE_HOST:$env:REMOTE_PATH" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] Configuration file exists but may not be fully configured" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  [WARN] Could not load deploy-config.ps1: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [MISSING] deploy-config.ps1 not found" -ForegroundColor Red
    Write-Host "    Copy from deploy-config.example.ps1 and configure" -ForegroundColor DarkGray
    $allChecksPassed = $false
}
Write-Host ""

# 5. Check Python environment
Write-Host "Python Environment:" -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Python: $pythonVersion" -ForegroundColor Green
        
        # Check if bump_version.py exists
        if (Test-Path "bump_version.py") {
            Write-Host "  [OK] bump_version.py available" -ForegroundColor Green
        } else {
            Write-Host "  [MISSING] bump_version.py not found" -ForegroundColor Red
            $allChecksPassed = $false
        }
    } else {
        Write-Host "  [ERROR] Python not found or not in PATH" -ForegroundColor Red
        $allChecksPassed = $false
    }
} catch {
    Write-Host "  [ERROR] Could not check Python: $($_.Exception.Message)" -ForegroundColor Red
    $allChecksPassed = $false
}
Write-Host ""

# 6. Check SCP availability
Write-Host "Deployment Tools:" -ForegroundColor Yellow
try {
    $null = Get-Command scp -ErrorAction Stop
    Write-Host "  [OK] SCP (OpenSSH client) available" -ForegroundColor Green
} catch {
    Write-Host "  [MISSING] SCP not found - install OpenSSH Client" -ForegroundColor Red
    $allChecksPassed = $false
}

if (Test-Path "deploy.ps1") {
    Write-Host "  [OK] deploy.ps1 available" -ForegroundColor Green
} else {
    Write-Host "  [MISSING] deploy.ps1 not found" -ForegroundColor Red
    $allChecksPassed = $false
}
Write-Host ""

# 7. Git status (informational)
Write-Host "Git Status:" -ForegroundColor Yellow
try {
    $gitStatus = git status --short 2>&1
    if ($LASTEXITCODE -eq 0) {
        if ($gitStatus) {
            Write-Host "  [INFO] Uncommitted changes detected:" -ForegroundColor Yellow
            $gitStatus | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        } else {
            Write-Host "  [OK] Working directory clean" -ForegroundColor Green
        }
    } else {
        Write-Host "  [INFO] Not a git repository or git not available" -ForegroundColor DarkGray
    }
} catch {
    Write-Host "  [INFO] Could not check git status" -ForegroundColor DarkGray
}
Write-Host ""

# Summary
Write-Host "=" * 70 -ForegroundColor Cyan
if ($allChecksPassed) {
    Write-Host "Status: READY FOR RELEASE" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Run: .\release.ps1 -VersionType patch" -ForegroundColor Yellow
    Write-Host "  2. Review preview output" -ForegroundColor Yellow
    Write-Host "  3. Confirm deployment" -ForegroundColor Yellow
} else {
    Write-Host "Status: NOT READY - Fix errors above" -ForegroundColor Red
    exit 1
}
Write-Host "=" * 70 -ForegroundColor Cyan

