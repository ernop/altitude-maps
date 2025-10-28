# Deploy Command

## Quick Deploy

```powershell
# PowerShell (Windows)
.\deploy.ps1 -RemoteHost wilson.com -RemotePath /home/x.com/public/maps -RemoteUser smith

# Bash (Linux/Mac)
./deploy.sh -h wilson.com -p /home/x.com/public/maps -u smith
```

## Rsync Semantics

Script uses `rsync source/` (trailing slash) = **Contents copied directly** to remote path

**Result:**
```
/home/x.com/public/maps/
├── interactive_viewer_advanced.html  ← Files here
├── js/
├── css/
└── generated/
```

**NOT nested** under `altitude-maps/` subfolder.

## Full Documentation

See `tech/DEPLOYMENT_GUIDE.md` for complete deployment documentation.

