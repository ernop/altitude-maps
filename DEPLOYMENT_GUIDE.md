# Deployment Guide

## Overview

This project uses native Windows SCP (Secure Copy Protocol) to upload the web viewer to your server. No rsync or third-party tools needed - uses the OpenSSH client built into Windows 10+.

## Setup (One Time)

### 1. Create your deployment config

```powershell
# Copy the template
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

This file is gitignored - your credentials stay local.

### 2. Ensure SCP is installed (built into Windows 10+)

```powershell
# Check if scp is available
scp

# If not found, install OpenSSH Client:
# Settings > Apps > Optional Features > Add a feature > OpenSSH Client

# Or via PowerShell (as admin):
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

### 3. Verify SSH access

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
- `viewer.html` - Simple viewer
- `js/` - All JavaScript files
- `css/` - All stylesheets  
- `generated/` - JSON data for all regions
- `README.md` - Documentation
- Favicon files (`.ico`, `.svg`, `.png`)

**Excluded** (stays local):
- `data/` - Raw GeoTIFF files (10+ GB)
- `src/` - Python processing code
- `*.py` - All Python scripts
- `venv/` - Virtual environment
- `tech/`, `learnings/` - Documentation
- `__pycache__/`, cache directories
- Development files

## Cache Busting

The viewer uses version-based cache busting:

```javascript
// In viewer HTML
<script src="js/viewer-advanced.js?v=1.335"></script>
```

When you run `bump_version.py`:
1. Updates `VIEWER_VERSION` in `js/viewer-advanced.js`
2. Updates version params in HTML files
3. Browsers fetch new files on next visit

## Troubleshooting

### "scp: command not found"

Install OpenSSH Client:

```powershell
# Via Settings UI:
# Settings > Apps > Optional Features > Add a feature > OpenSSH Client

# Or via PowerShell (as admin):
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

### "Permission denied (publickey)"

Your SSH key isn't set up. Either:

```powershell
# A) Generate SSH key
ssh-keygen -t rsa -b 4096

# B) Copy to server
ssh-copy-id $REMOTE_USER@$REMOTE_HOST

# C) Or use password auth (less secure)
# rsync will prompt for password
```

### "deploy-config.ps1 not found"

Create it from template:

```powershell
Copy-Item deploy-config.example.ps1 deploy-config.ps1
# Then edit with your server details
```

### Files not uploading

Check what would be uploaded in preview mode:

```powershell
.\deploy.ps1 -Preview
```

The script only uploads specific files/directories: HTML, JS, CSS, generated data, and favicons.

### Server path wrong

Edit `deploy-config.ps1`:

```powershell
# Make sure this matches your server's web directory
$REMOTE_PATH = "/home/user/public_html/maps"
```

## Example Workflow

```powershell
# Add new region
python ensure_region.py switzerland --target-pixels 2048

# Regenerate manifest
python regenerate_manifest.py

# Bump version
python bump_version.py

# Preview deploy
.\deploy.ps1 -Preview
# Output shows what will upload:
#   Files to deploy: 156 (52.3 MB)
#   
#   generated/regions/
#     switzerland_srtm_30m_2048px_v2.json (1.2 MB)
#     regions_manifest.json (15.3 KB)
#   js/
#     viewer-advanced.js (45.2 KB)
#   ... etc

# Looks good, deploy
.\deploy.ps1 -Deploy

# Visit your site
# https://yourserver.com/path/to/viewer/interactive_viewer_advanced.html
```

## Security Notes

- `deploy-config.ps1` is gitignored - never commit it
- Use SSH keys instead of passwords
- Keep SSH keys secure (permissions 600 on Linux)
- Review preview output before deploying
- Test on server after deploy

## Alternative: Manual SCP

If the script doesn't work, you can upload manually:

```powershell
# Upload a single file
scp interactive_viewer_advanced.html user@server:/path/to/web/directory/

# Upload entire directory
scp -r js user@server:/path/to/web/directory/

# Upload multiple items
scp -r js css generated interactive_viewer_advanced.html `
  user@server:/path/to/web/directory/
```

Replace `user@server` and `/path/to/web/directory` with your details.

