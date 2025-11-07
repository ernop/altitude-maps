# Quick Deployment Setup

## Your Configuration

**Server:** fuseki.net  
**Path:** /home/ernop/fuseki.net/public/altitude-maps/  
**Live URL:** https://fuseki.net/altitude-maps/advanced-viewer.html

Configuration is already set up in `deploy-config.ps1` (gitignored).

## Commands

```powershell
# Preview what would be uploaded (dry run)
.\deploy.ps1 -Preview

# Deploy to your server
.\deploy.ps1 -Deploy
```

**Note:** Uses native Windows SCP (built into Windows 10+). No rsync or third-party tools needed.

## Full Workflow Example

```powershell
# 1. Add or update regions
python ensure_region.py iceland --target-pixels 2048

# 2. Bump version (cache bust)
python bump_version.py

# 3. Preview deploy
.\deploy.ps1 -Preview

# 4. Deploy
.\deploy.ps1 -Deploy

# 5. Visit your site
# https://fuseki.net/altitude-maps/advanced-viewer.html
```

## What Gets Uploaded

Only viewer files (~50-100 MB):
- HTML, JS, CSS
- Generated JSON data (`generated/regions/`)
- Favicons

Raw data (~10+ GB in `data/`) stays local and is never uploaded.

## See Also

- Full guide: `DEPLOYMENT_GUIDE.md`
- Server config template: `deploy-config.example.ps1`

