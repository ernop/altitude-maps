# Production Compression Setup

## Problem Identified (October 2025)

Testing revealed that the production server at `fuseki.net` is **NOT compressing JSON files** during transfer:

```
Content-Encoding: (NONE)
Actual bytes: 8,031,256 bytes (7.66 MB) - FULL SIZE TRANSFERRED
```

This means:
- Users download 7-12 MB per state **uncompressed**
- Slow page loads, especially on mobile/slow connections
- Wasted bandwidth for both server and users

## Solution: Apache .htaccess File

Since the server is Dreamhost (Apache), we can enable compression with an `.htaccess` file.

### What the .htaccess Does

1. **Enables gzip compression** for JSON files using `mod_deflate`
2. **Reduces transfer size by 85-95%** (8 MB → 0.5-1 MB typical)
3. **Adds browser caching** to avoid re-downloading unchanged files
4. **Sets security headers** for better security

### Deployment

**Option 1: Automated (using rsync/SSH)**
```bash
# From venv
python deploy_htaccess.py
```

**Option 2: Manual (FTP/SFTP)**
1. Upload `.htaccess` file to: `/home/username/fuseki.net/altitude-maps/`
2. Ensure file is named exactly `.htaccess` (with leading dot)
3. Check file permissions: should be readable (644)

**Option 3: Dreamhost File Manager**
1. Log into Dreamhost panel
2. Navigate to: `fuseki.net/altitude-maps/`
3. Upload `.htaccess` file
4. Verify it appears in the directory

### Verification

After deploying, test compression:

```bash
python test_nebraska_compression.py
```

**Expected results:**
```
Content-Encoding: gzip
Actual bytes: 500,000-1,000,000 bytes (0.5-1 MB)
[SUCCESS] Server IS using gzip compression!
```

### Troubleshooting

If compression still not working after deploying `.htaccess`:

1. **Check mod_deflate is enabled**
   - Log into Dreamhost panel
   - Check PHP/Apache settings
   - mod_deflate should be enabled by default on Dreamhost

2. **Check .htaccess syntax**
   - Use online `.htaccess` checker
   - Ensure file uses Unix line endings (LF, not CRLF)

3. **Check file location**
   - Must be in the root of `altitude-maps/` directory
   - Not in subdirectories

4. **Check file permissions**
   - Should be 644 (readable by web server)

5. **Browser cache**
   - Clear browser cache or use incognito mode
   - Old uncompressed version may be cached

6. **Contact Dreamhost support**
   - They can verify mod_deflate is working
   - They can check for conflicts in server config

### Performance Impact

**Before (NO compression):**
- Nebraska: 7.66 MB transferred
- California: ~12 MB transferred
- All 50 states: ~300-500 MB total

**After (WITH compression):**
- Nebraska: ~0.6 MB transferred (92% reduction)
- California: ~1.2 MB transferred (90% reduction)
- All 50 states: ~30-50 MB total (85-90% reduction)

**User experience:**
- 5-10x faster load times
- Works well on mobile/slow connections
- Reduced hosting bandwidth costs

## Browser DevTools Verification

To verify in the browser:

1. Open https://fuseki.net/altitude-maps/interactive_viewer_advanced.html
2. Open DevTools (F12) → Network tab
3. Load a region (e.g., select "Nebraska")
4. Find the JSON file in Network tab
5. Check:
   - **Size column**: Should show `600 KB / 7.6 MB` (transferred / actual)
   - **Response Headers**: Should include `content-encoding: gzip`

If you see `7.6 MB / 7.6 MB`, compression is NOT working.

## Related Files

- `.htaccess` - Apache configuration (deploy this)
- `test_nebraska_compression.py` - Test compression on production
- `deploy_htaccess.py` - Automated deployment script
- `serve_viewer.py` - Dev server with compression (already working)

