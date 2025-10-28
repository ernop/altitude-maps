# Production Deployment Guide

## What Gets Deployed

The viewer is a **pure client-side web application** that only needs:

### Required Files (uploaded)
- `interactive_viewer_advanced.html` - Main 3D viewer
- `viewer.html` - Simple viewer
- `js/*.js` - Client-side JavaScript
- `css/*.css` - Stylesheets
- `generated/` - Exported elevation data (JSON files)

### External Dependencies (CDN, no upload needed)
- Three.js (3D rendering)
- jQuery (DOM manipulation)
- Select2 (dropdown UI)

### NOT Needed (stays local)
- ❌ `data/` - Raw GeoTIFF files (10+ GB!)
- ❌ `src/` - Python processing code
- ❌ `*.py` - Python scripts
- ❌ `venv/` - Virtual environment
- ❌ Documentation files

## Deployment

### Quick Start

**PowerShell (Windows):**
```powershell
# Dry run first (test, no changes)
.\deploy.ps1 -RemoteHost wilson.com -RemotePath /home/x.com/public/maps -RemoteUser smith -DryRun

# Actual deployment
.\deploy.ps1 -RemoteHost wilson.com -RemotePath /home/x.com/public/maps -RemoteUser smith
```

**Bash (Linux/Mac):**
```bash
# Make executable
chmod +x deploy.sh

# Dry run first
./deploy.sh -h wilson.com -p /home/x.com/public/maps -u smith -d

# Actual deployment
./deploy.sh -h wilson.com -p /home/x.com/public/maps -u smith
```

### Rsync Path Semantics

**The script uses rsync with trailing slash semantics:**

- Script internally: `rsync $PSScriptRoot\ user@host:/remote/path`
- Trailing slash (`source/`) = Copy **contents** of source into destination
- No trailing slash (`source`) = Copy **source folder itself** into destination

**Our script uses trailing slash**, so files appear directly in remote path:

```
/home/x.com/public/maps/
├── interactive_viewer_advanced.html  ← Files here
├── js/
├── css/
└── generated/
```

**NOT nested** like this:
```
/home/x.com/public/maps/
└── altitude-maps/  ← Does NOT create this
    └── ...
```

This matches rsync standard behavior exactly.

### What It Does

The script uses `rsync` to:
1. Upload only viewer files (HTML/JS/CSS/data)
2. Preserve directory structure (relative paths)
3. Delete old files on remote (sync)
4. Show progress bar

## Server Configuration

### No Configuration Needed!

Since all paths are relative, any web server works. Just point it at the deployment directory:

**Nginx example:**
```nginx
server {
    listen 80;
    server_name maps.example.com;
    
    root /var/www/maps;
    index interactive_viewer_advanced.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
}
```

**Apache example:**
```apache
<VirtualHost *:80>
    ServerName maps.example.com
    DocumentRoot /var/www/maps
    
    <Directory /var/www/maps>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>
</VirtualHost>
```

**Python (development only):**
```bash
cd /var/www/maps
python3 -m http.server 8001
```

## File Size Expectations

Typical deployment sizes:
- HTML/JS/CSS: ~100 KB
- Generated data: Varies by regions
  - Single US state: ~500 KB - 2 MB
  - All US states: ~50 MB
  - Global regions: ~100 MB+

Raw data (NOT deployed):
- Single US state GeoTIFF: 50-500 MB
- All US states: 10+ GB

## Directory Structure After Deploy

```
/var/www/maps/
├── interactive_viewer_advanced.html  ← Main viewer
├── viewer.html                       ← Simple viewer
├── README.md                         ← Optional
├── css/
│   ├── viewer.css
│   └── viewer-advanced.css
├── js/
│   ├── viewer-advanced.js
│   ├── camera-schemes.js
│   ├── ground-plane-camera.js
│   └── ...
└── generated/
    ├── manifest.json                 ← Region list
    └── regions/
        ├── USA_Alabama.json
        ├── USA_California.json
        └── ...
```

## Updating Data

To add new regions or update existing ones:

1. **Local: Process new data**
   ```powershell
   # Download and export new region
   python download_regions.py
   python export_for_web_viewer.py data/new_region.tif
   ```

2. **Deploy: Upload changes**
   ```powershell
   # Only changed files will be uploaded (rsync is smart)
   .\deploy.ps1 -RemoteHost example.com -RemotePath /var/www/maps -RemoteUser deploy
   ```

3. **Done!** Refresh browser to see new regions

## Troubleshooting

### Problem: Viewer loads but no data
- Check: Does `generated/manifest.json` exist?
- Check: Are region files in `generated/regions/`?
- Check browser console for 404 errors

### Problem: Can't find rsync
**Windows:**
- Install via Chocolatey: `choco install rsync`
- Or use Git Bash (includes rsync)
- Or use WSL: `wsl --install`

**Linux/Mac:**
- Should be pre-installed
- If not: `apt install rsync` or `brew install rsync`

### Problem: Large upload times
- **First deploy**: Uploads everything (~50-100 MB)
- **Subsequent deploys**: Only changed files (usually < 1 MB)
- Tip: Use `-DryRun` to preview what will change

### Problem: Permission denied
- Check SSH key is configured: `ssh user@host`
- Check remote directory is writable by deploy user
- May need: `chown -R deploy:deploy /var/www/maps`

## Security Notes

- ✅ No server-side code (static files only)
- ✅ No database or user data
- ✅ All data is public (elevation maps)
- ✅ CDN dependencies use integrity hashes (recommended)

Consider adding:
- HTTPS via Let's Encrypt
- Gzip compression for faster loads
- Cache headers for static assets

