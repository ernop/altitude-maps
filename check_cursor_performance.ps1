# Cursor Performance Diagnostic Script
Write-Host "`n=== CURSOR PERFORMANCE DIAGNOSTICS ===`n" -ForegroundColor Cyan

# 1. Memory Usage
Write-Host "1. MEMORY USAGE BY PROCESS:" -ForegroundColor Green
$cursorProcesses = Get-Process | Where-Object {$_.ProcessName -like "*Cursor*"}
$totalMemory = 0
foreach ($proc in $cursorProcesses) {
    $memMB = [math]::Round($proc.WorkingSet64/1MB, 0)
    $totalMemory += $memMB
    Write-Host "  PID $($proc.Id): $memMB MB" -NoNewline
    if ($memMB -gt 500) {
        Write-Host " ⚠️ HIGH" -ForegroundColor Red
    } elseif ($memMB -gt 200) {
        Write-Host " ⚠️ ELEVATED" -ForegroundColor Yellow
    } else {
        Write-Host " ✓" -ForegroundColor Green
    }
}
Write-Host "`n  TOTAL: $totalMemory MB`n" -ForegroundColor Cyan

# 2. Node.js Memory Limit
Write-Host "2. NODE.JS MEMORY CONFIGURATION:" -ForegroundColor Green
$nodeOptions = $env:NODE_OPTIONS
if ($nodeOptions) {
    Write-Host "  Current: $nodeOptions" -ForegroundColor Yellow
} else {
    Write-Host "  Current: Not set (default ~1400 MB per process)" -ForegroundColor White
}
Write-Host ""

# 3. Extension Count
Write-Host "3. INSTALLED EXTENSIONS:" -ForegroundColor Green
$extPath = "$env:USERPROFILE\.cursor\extensions"
if (Test-Path $extPath) {
    $extensions = Get-ChildItem $extPath -Directory
    Write-Host "  Total: $($extensions.Count) extensions" -ForegroundColor White
    
    # Check for duplicates
    $extNames = @{}
    foreach ($ext in $extensions) {
        $baseName = $ext.Name -replace '-\d+\.\d+\.\d+.*$', ''
        if ($extNames.ContainsKey($baseName)) {
            $extNames[$baseName] += 1
        } else {
            $extNames[$baseName] = 1
        }
    }
    
    $duplicates = $extNames.GetEnumerator() | Where-Object {$_.Value -gt 1}
    if ($duplicates) {
        Write-Host "`n  ⚠️ DUPLICATES FOUND:" -ForegroundColor Red
        foreach ($dup in $duplicates) {
            Write-Host "    - $($dup.Key): $($dup.Value) versions installed" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  Extension directory not found" -ForegroundColor Red
}
Write-Host ""

# 4. Cache Size
Write-Host "4. CACHE DIRECTORY SIZES:" -ForegroundColor Green
$cacheLocations = @(
    "$env:APPDATA\Cursor\Cache",
    "$env:APPDATA\Cursor\CachedData",
    "$env:APPDATA\Cursor\logs",
    "$env:LOCALAPPDATA\Cursor\Cache"
)

foreach ($cachePath in $cacheLocations) {
    if (Test-Path $cachePath) {
        $size = (Get-ChildItem $cachePath -Recurse -File -ErrorAction SilentlyContinue | 
                 Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size/1MB, 0)
        Write-Host "  $cachePath"
        Write-Host "    Size: $sizeMB MB" -NoNewline
        if ($sizeMB -gt 500) {
            Write-Host " ⚠️ LARGE - Consider clearing" -ForegroundColor Yellow
        } else {
            Write-Host " ✓" -ForegroundColor Green
        }
    }
}
Write-Host ""

# 5. Recommendations
Write-Host "5. RECOMMENDATIONS:" -ForegroundColor Green
if ($totalMemory -gt 2000) {
    Write-Host "  ⚠️ High total memory usage ($totalMemory MB) - Consider restarting Cursor" -ForegroundColor Yellow
}
if ($duplicates) {
    Write-Host "  ⚠️ Remove duplicate extension versions" -ForegroundColor Yellow
}

$largeProcesses = $cursorProcesses | Where-Object {$_.WorkingSet64/1MB -gt 500}
if ($largeProcesses) {
    Write-Host "  ⚠️ Some processes using >500MB - Check Process Explorer (Help > Open Process Explorer)" -ForegroundColor Yellow
}

Write-Host "`n=== END DIAGNOSTICS ===`n" -ForegroundColor Cyan

