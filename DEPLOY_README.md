# Deployment Guide

## Quick Start

```powershell
# Preview what would be uploaded (dry run)
.\deploy.ps1 -Preview

# Deploy to server
.\deploy.ps1 -Deploy
```

Uses native Windows SCP (built into Windows 10+). No rsync or third-party tools needed.

## Setup (One Time)

### 1. Create Deployment Config

```powershell
# Copy template
Copy-Item deploy-config.example.ps1 deploy-config.ps1

# Edit with your server details
notepad deploy-config.ps1
```

Example `deploy-config.ps1`:
```powershell
$REMOTE_HOST = "yourserver.com"
$REMOTE_USER = "yourusername"
$REMOTE_PATH = "/path/to/web/directory"
$SSH_KEY = ""  # Leave empty to use default SSH key
```

This file is gitignored - credentials stay local.

### 2. Ensure SCP is Installed

```powershell
# Check if scp is available
scp

# If not found, install OpenSSH Client:
# Settings > Apps > Optional Features > Add a feature > OpenSSH Client

# Or via PowerShell (as admin):
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

### 3. Verify SSH Access

```powershell
# Test SSH connection
ssh $REMOTE_USER@$REMOTE_HOST

# Should connect without password (using SSH key)
```

## Daily Workflow

### When to Deploy

Deploy after:
- Adding new regions (run `ensure_region.py`)
- Updating viewer code (JS/CSS/HTML changes)
- Bumping version (run `bump_version.py`)

### Deployment Steps

```powershell
# 1. Bump version (cache bust for browser)
python bump_version.py

# 2. Preview what would be uploaded (dry run)
.\deploy.ps1 -Preview

# Review the output - check files look correct

# 3. Deploy for real
.\deploy.ps1 -Deploy
```

## What Gets Deployed

**Included** (~50-100 MB):
- `interactive_viewer_advanced.html` - Main 3D viewer
- `.htaccess` - Apache configuration (prevents double-gzip)
- `js/` - All JavaScript files
- `css/` - All stylesheets
- `generated/regions/` - JSON data (only `.json.gz` files)
- Favicon files (`.ico`, `.svg`, `.png`)

**Excluded** (stays local):
- `data/` - Raw GeoTIFF files (10+ GB)
- `src/` - Python processing code
- `*.py` - All Python scripts
- `venv/` - Virtual environment
- Raw `.json` files (only `.json.gz` deployed)

## Compression System

### Overview
- Files are pre-compressed as `.json.gz` during export
- Server serves `.gz` files WITHOUT applying compression
- Client explicitly decompresses in JavaScript
- Savings: ~75-80% reduction (e.g., 13MB → 3MB)

### Server Configuration
The `.htaccess` file (deployed automatically) prevents Apache from double-compressing:
- Disables compression for `.gz` files
- Sets MIME type without content-encoding header
- Client handles decompression explicitly

### Troubleshooting Double-Gzip Error
If you see "The compressed data was not valid: incorrect header check":
1. Ensure `.htaccess` is deployed (script includes it automatically)
2. Verify `.htaccess` exists on server
3. Check Apache allows `.htaccess` (`AllowOverride All`)

## Cache Busting

The viewer uses version-based cache busting:
- `bump_version.py` updates version in JS and HTML
- Browsers fetch new files on next visit
- Version format: `?v=1.335`

## Troubleshooting

### "scp: command not found"
Install OpenSSH Client via Settings > Apps > Optional Features > Add a feature > OpenSSH Client

### "Permission denied (publickey)"
Set up SSH key:
```powershell
ssh-keygen -t rsa -b 4096
ssh-copy-id $REMOTE_USER@$REMOTE_HOST
```

### "deploy-config.ps1 not found"
Create from template: `Copy-Item deploy-config.example.ps1 deploy-config.ps1`

### Files not uploading
Check preview: `.\deploy.ps1 -Preview` - script only uploads specific files/directories

### SSH Key Permissions (Windows)
If SSH fails with "bad permissions" error:
```powershell
icacls C:\Users\USERNAME\.ssh\id_rsa /inheritance:r
icacls C:\Users\USERNAME\.ssh\id_rsa /grant:r "$env:USERNAME`:F"
```

## Example Workflow

```powershell
# Add new region
python ensure_region.py switzerland --target-pixels 2048

# Bump version
python bump_version.py

# Preview deploy
.\deploy.ps1 -Preview

# Deploy
.\deploy.ps1 -Deploy

# Visit your site
# https://yourserver.com/path/to/viewer/interactive_viewer_advanced.html
```

## Security Notes

- `deploy-config.ps1` is gitignored - never commit it
- Use SSH keys instead of passwords
- Keep SSH keys secure
- Review preview output before deploying
- Test on server after deploy

## Manual Upload

If script doesn't work, upload manually:
```powershell
scp -r js css generated interactive_viewer_advanced.html user@server:/path/to/web/directory/
```

