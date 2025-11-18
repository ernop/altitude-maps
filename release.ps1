# release.ps1
# Automated release script - bumps version and deploys to production
# Usage: .\release.ps1 [-VersionType patch|minor|major] [-SkipPreview] [-DryRun] [-SkipChecks]

param(
    [ValidateSet("patch", "minor", "major")]
    [string]$VersionType = "patch",
    [switch]$SkipPreview = $false,
    [switch]$DryRun = $false,
    [switch]$SkipChecks = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Release Automation" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Version Type: $VersionType" -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "Mode: DRY RUN (no changes will be made)" -ForegroundColor Yellow
}
if ($SkipPreview) {
    Write-Host "Mode: SKIP PREVIEW (will not show preview before deploying)" -ForegroundColor Yellow
}
Write-Host ""

# Step 1: Pre-release validation
if (-not $SkipChecks) {
    Write-Host "Step 1: Pre-release Validation" -ForegroundColor Cyan
    Write-Host "-" * 70 -ForegroundColor DarkGray
    
    $validationErrors = @()
    
    # Check required files
    $requiredFiles = @(
        "interactive_viewer_advanced.html",
        "js/viewer-advanced.js",
        "css/viewer-advanced.css",
        "generated/regions/regions_manifest.json.gz",
        "bump_version.py",
        "deploy.ps1"
    )
    
    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            $validationErrors += "Required file missing: $file"
        }
    }
    
    # Check deployment config
    if (-not (Test-Path "deploy-config.ps1")) {
        $validationErrors += "deploy-config.ps1 not found - copy from deploy-config.example.ps1"
    }
    
    # Check Python
    try {
        $null = python --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            $validationErrors += "Python not found or not in PATH"
        }
    } catch {
        $validationErrors += "Python not available: $($_.Exception.Message)"
    }
    
    # Check SCP
    try {
        $null = Get-Command scp -ErrorAction Stop
    } catch {
        $validationErrors += "SCP (OpenSSH client) not found - install OpenSSH Client"
    }
    
    if ($validationErrors.Count -gt 0) {
        Write-Host "Validation FAILED:" -ForegroundColor Red
        foreach ($error in $validationErrors) {
            Write-Host "  ERROR: $error" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "Run .\check_release_status.ps1 for detailed status" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "  All validation checks passed" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "Step 1: Skipped (--SkipChecks)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 2: Get current version
Write-Host "Step 2: Reading Current Version" -ForegroundColor Cyan
Write-Host "-" * 70 -ForegroundColor DarkGray

try {
    $jsFile = Get-Content "js/viewer-advanced.js" -Raw -ErrorAction Stop
    $versionMatch = [regex]::Match($jsFile, "const VIEWER_VERSION = '([^']+)';")
    if (-not $versionMatch.Success) {
        Write-Host "ERROR: Could not find VIEWER_VERSION in js/viewer-advanced.js" -ForegroundColor Red
        exit 1
    }
    $currentVersion = $versionMatch.Groups[1].Value
    Write-Host "  Current version: $currentVersion" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "ERROR: Could not read js/viewer-advanced.js" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
    exit 1
}

# Step 3: Bump version
Write-Host "Step 3: Bumping Version ($VersionType)" -ForegroundColor Cyan
Write-Host "-" * 70 -ForegroundColor DarkGray

if ($DryRun) {
    Write-Host "  [DRY RUN] Would run: python bump_version.py $VersionType" -ForegroundColor Yellow
    Write-Host "  [DRY RUN] Would update version from $currentVersion" -ForegroundColor Yellow
    Write-Host ""
} else {
    try {
        # Run bump_version.py
        $bumpOutput = python bump_version.py $VersionType 2>&1
        $bumpExitCode = $LASTEXITCODE
        
        if ($bumpExitCode -ne 0) {
            Write-Host "ERROR: Version bump failed" -ForegroundColor Red
            Write-Host "Output:" -ForegroundColor Yellow
            Write-Host $bumpOutput -ForegroundColor DarkGray
            exit 1
        }
        
        Write-Host $bumpOutput -ForegroundColor Green
        
        # Verify version was updated
        $jsFile = Get-Content "js/viewer-advanced.js" -Raw
        $versionMatch = [regex]::Match($jsFile, "const VIEWER_VERSION = '([^']+)';")
        if ($versionMatch.Success) {
            $newVersion = $versionMatch.Groups[1].Value
            if ($newVersion -eq $currentVersion) {
                Write-Host "WARNING: Version appears unchanged ($newVersion)" -ForegroundColor Yellow
            } else {
                Write-Host "  Version updated: $currentVersion -> $newVersion" -ForegroundColor Green
            }
        }
        Write-Host ""
    } catch {
        Write-Host "ERROR: Failed to bump version" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
        exit 1
    }
}

# Step 4: Preview deployment
if (-not $SkipPreview) {
    Write-Host "Step 4: Preview Deployment" -ForegroundColor Cyan
    Write-Host "-" * 70 -ForegroundColor DarkGray
    
    if ($DryRun) {
        Write-Host "  [DRY RUN] Would run: .\deploy.ps1 -Preview" -ForegroundColor Yellow
        Write-Host ""
    } else {
        Write-Host "  Running deployment preview..." -ForegroundColor Yellow
        Write-Host ""
        
        try {
            .\deploy.ps1 -Preview
            $previewExitCode = $LASTEXITCODE
            
            if ($previewExitCode -ne 0) {
                Write-Host ""
                Write-Host "ERROR: Preview failed (exit code: $previewExitCode)" -ForegroundColor Red
                exit 1
            }
            
            Write-Host ""
            Write-Host "  Preview completed successfully" -ForegroundColor Green
            Write-Host ""
            
            # Ask for confirmation (unless DryRun)
            if (-not $DryRun) {
                $response = Read-Host "Proceed with deployment? (y/n)"
                if ($response -ne 'y' -and $response -ne 'Y') {
                    Write-Host ""
                    Write-Host "Release cancelled by user" -ForegroundColor Yellow
                    exit 0
                }
                Write-Host ""
            }
        } catch {
            Write-Host ""
            Write-Host "ERROR: Preview failed" -ForegroundColor Red
            Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
            exit 1
        }
    }
} else {
    Write-Host "Step 4: Skipped (--SkipPreview)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 5: Deploy
Write-Host "Step 5: Deploy to Production" -ForegroundColor Cyan
Write-Host "-" * 70 -ForegroundColor DarkGray

if ($DryRun) {
    Write-Host "  [DRY RUN] Would run: .\deploy.ps1 -Deploy" -ForegroundColor Yellow
    Write-Host "  [DRY RUN] No files would be uploaded" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "DRY RUN COMPLETE" -ForegroundColor Yellow
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To actually release, run without -DryRun:" -ForegroundColor Cyan
    Write-Host "  .\release.ps1 -VersionType $VersionType" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "  Deploying files to production server..." -ForegroundColor Yellow
    Write-Host ""
    
    try {
        .\deploy.ps1 -Deploy
        $deployExitCode = $LASTEXITCODE
        
        if ($deployExitCode -ne 0) {
            Write-Host ""
            Write-Host "ERROR: Deployment failed (exit code: $deployExitCode)" -ForegroundColor Red
            exit 1
        }
        
        Write-Host ""
        Write-Host "=" * 70 -ForegroundColor Green
        Write-Host "RELEASE COMPLETE" -ForegroundColor Green
        Write-Host "=" * 70 -ForegroundColor Green
        Write-Host ""
        
        # Show final version
        $jsFile = Get-Content "js/viewer-advanced.js" -Raw
        $versionMatch = [regex]::Match($jsFile, "const VIEWER_VERSION = '([^']+)';")
        if ($versionMatch.Success) {
            $finalVersion = $versionMatch.Groups[1].Value
            Write-Host "Released version: $finalVersion" -ForegroundColor Cyan
        }
        Write-Host ""
        Write-Host "Viewer is live at production server" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "ERROR: Deployment failed" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
        exit 1
    }
}

