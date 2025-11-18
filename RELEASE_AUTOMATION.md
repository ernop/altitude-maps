# Release Automation Documentation

This document explains the release automation scripts for the Altitude Maps project.

## Overview

Two PowerShell scripts automate the release process:

1. **`check_release_status.ps1`** - Check if everything is ready for release
2. **`release.ps1`** - Automate the full release process (version bump + deploy)

## Script 1: check_release_status.ps1

### What It Does

Checks the current state of your project to see if it's ready for release. This is a **read-only** check - it doesn't make any changes.

### What It Checks

1. **Version Information**
   - Reads current version from `js/viewer-advanced.js`
   - Displays the version number

2. **Required Files**
   - Checks that critical files exist:
     - `interactive_viewer_advanced.html` (main viewer)
     - `js/viewer-advanced.js` (main JavaScript)
     - `css/viewer-advanced.css` (main stylesheet)
     - `generated/regions/regions_manifest.json.gz` (region manifest)
   - Shows file sizes for each

3. **Deployable Files**
   - Counts JavaScript files in `js/` directory
   - Counts CSS files in `css/` directory
   - Counts region data files (`.json.gz` files)
   - Counts manifest files

4. **Deployment Configuration**
   - Checks if `deploy-config.ps1` exists
   - Tries to load it and verify it's configured
   - Shows server connection details if available

5. **Python Environment**
   - Verifies Python is installed and accessible
   - Checks that `bump_version.py` exists

6. **Deployment Tools**
   - Verifies SCP (OpenSSH client) is installed
   - Checks that `deploy.ps1` exists

7. **Git Status** (informational only)
   - Shows uncommitted changes if any
   - Doesn't fail if git isn't available

### Usage

```powershell
.\check_release_status.ps1
```

### Output

- **Green [OK]** = Everything looks good
- **Red [ERROR]** = Problem found - fix before releasing
- **Yellow [WARN]** = Warning - might work but check it
- **Cyan [INFO]** = Informational message

At the end, it shows:
- **"READY FOR RELEASE"** = All checks passed, safe to proceed
- **"NOT READY"** = Fix errors before releasing

### Exit Code

- **0** = All checks passed (ready for release)
- **1** = One or more checks failed (not ready)

---

## Script 2: release.ps1

### What It Does

Automates the complete release process:
1. Validates everything is ready
2. Bumps the version number
3. Shows preview of what will be deployed
4. Deploys files to production server

### Step-by-Step Process

#### Step 1: Pre-release Validation

Checks the same things as `check_release_status.ps1`:
- Required files exist
- Deployment config exists
- Python is available
- SCP is installed

**If validation fails:** Script stops immediately with error messages.

#### Step 2: Read Current Version

Reads the current version from `js/viewer-advanced.js` and displays it.

**If version can't be read:** Script stops with error.

#### Step 3: Bump Version

Runs `python bump_version.py` with the specified version type:
- **patch** = Increment last number (1.370 → 1.371)
- **minor** = Increment middle number (1.370 → 1.371)
- **major** = Increment first number (1.370 → 2.0)

Also automatically syncs HTML cache busters via `update_version.py`.

**If bump fails:** Script stops with error. Version is not changed.

**After bump:** Verifies the version was actually updated.

#### Step 4: Preview Deployment

Runs `.\deploy.ps1 -Preview` to show:
- What files will be uploaded
- File sizes
- Total size
- Upload order (manifests first, then code, then data)

**If preview fails:** Script stops with error.

**After preview:** Asks for confirmation: "Proceed with deployment? (y/n)"
- Type **y** or **Y** to continue
- Type anything else to cancel

#### Step 5: Deploy to Production

Runs `.\deploy.ps1 -Deploy` to actually upload files:
- Tests SSH connection
- Checks remote files (skips unchanged files)
- Uploads changed files only
- Shows progress for each file
- Reports final statistics

**If deployment fails:** Script stops with error. Some files may have been uploaded.

**On success:** Shows final version number and confirms release is complete.

### Command-Line Options

```powershell
.\release.ps1 [options]
```

**Options:**

- **`-VersionType <type>`** - Version bump type (default: `patch`)
  - `patch` = Bug fixes, minor tweaks (1.370 → 1.371)
  - `minor` = New features (1.370 → 1.371)
  - `major` = Breaking changes (1.370 → 2.0)

- **`-SkipPreview`** - Skip the preview step (don't show what will be uploaded)
  - Use for automation/CI/CD
  - Still asks for confirmation unless also using `-DryRun`

- **`-DryRun`** - Test mode - don't make any changes
  - Shows what would happen
  - Doesn't bump version
  - Doesn't upload files
  - Safe to run anytime

- **`-SkipChecks`** - Skip validation checks (not recommended)
  - Only use if you're absolutely sure everything is ready
  - Script will fail later if something is missing

### Usage Examples

```powershell
# Standard release (patch bump, with preview, real deploy)
.\release.ps1

# Minor version bump
.\release.ps1 -VersionType minor

# Major version bump
.\release.ps1 -VersionType major

# Test without making changes (dry run)
.\release.ps1 -DryRun

# Skip preview step (for automation)
.\release.ps1 -SkipPreview

# Skip preview AND skip checks (dangerous - only if you're sure)
.\release.ps1 -SkipPreview -SkipChecks
```

### Safety Features

1. **Validation First** - Checks everything before making changes
2. **Version Verification** - Confirms version was updated after bump
3. **Preview Before Deploy** - Shows what will happen before doing it
4. **Confirmation Prompt** - Asks before deploying (unless `-DryRun`)
5. **Dry Run Mode** - Test without making changes
6. **Error Handling** - Stops immediately on any error
7. **Exit Codes** - Returns error codes for automation
8. **Clear Messages** - Explains what went wrong if something fails

### Exit Codes

- **0** = Success (release completed)
- **1** = Error (script stopped due to problem)

### What Gets Deployed

The script uses `deploy.ps1` which uploads:

- HTML files (`interactive_viewer_advanced.html`)
- JavaScript files (`js/` directory)
- CSS files (`css/` directory)
- Region data files (`generated/regions/*.json.gz`)
- Manifest files (`regions_manifest.json.gz`, `region_adjacency.json.gz`)
- Favicon files

**Does NOT deploy:**
- Raw `.json` files (only `.json.gz` files)
- Python code (`src/`, `*.py` files)
- Raw data (`data/` directory)
- Virtual environment (`venv/`)

---

## Typical Workflow

### Before First Release

1. Set up deployment config:
   ```powershell
   Copy-Item deploy-config.example.ps1 deploy-config.ps1
   # Edit deploy-config.ps1 with your server details
   ```

2. Test SSH connection:
   ```powershell
   ssh $REMOTE_USER@$REMOTE_HOST
   ```

3. Check status:
   ```powershell
   .\check_release_status.ps1
   ```

### For Each Release

1. **Check status** (optional but recommended):
   ```powershell
   .\check_release_status.ps1
   ```

2. **Test release** (dry run):
   ```powershell
   .\release.ps1 -DryRun
   ```

3. **Do the release**:
   ```powershell
   .\release.ps1
   ```
   - Review preview output
   - Type `y` when prompted
   - Wait for deployment to complete

### Quick Release (if you're confident)

```powershell
.\release.ps1 -VersionType patch
```

---

## Troubleshooting

### "deploy-config.ps1 not found"

Copy the example file and configure it:
```powershell
Copy-Item deploy-config.example.ps1 deploy-config.ps1
notepad deploy-config.ps1
```

### "SCP not found"

Install OpenSSH Client:
- Settings > Apps > Optional Features > Add a feature > OpenSSH Client
- Or: `Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0` (as admin)

### "Python not found"

Make sure Python is in your PATH, or activate the virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```

### "Version bump failed"

Check that `bump_version.py` exists and Python can run it:
```powershell
python bump_version.py --help
```

### "Preview/Deploy failed"

Check `deploy-config.ps1` is configured correctly and SSH connection works:
```powershell
ssh $REMOTE_USER@$REMOTE_HOST
```

### Script stops with error

Read the error message - it explains what went wrong. Fix the issue and try again.

---

## Integration with Existing Scripts

These scripts work with existing project scripts:

- **`bump_version.py`** - Called by `release.ps1` to bump version
- **`update_version.py`** - Called by `bump_version.py` to sync HTML cache busters
- **`deploy.ps1`** - Called by `release.ps1` to upload files

You can still use these scripts individually if needed:
- `python bump_version.py` - Just bump version
- `.\deploy.ps1 -Preview` - Just preview deployment
- `.\deploy.ps1 -Deploy` - Just deploy (without version bump)

---

## Summary

- **`check_release_status.ps1`** = Check if ready (read-only, safe to run anytime)
- **`release.ps1`** = Do the release (makes changes, use `-DryRun` to test first)

Both scripts provide clear output and stop immediately if something is wrong.

