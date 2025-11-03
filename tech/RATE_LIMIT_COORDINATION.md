# OpenTopography Rate Limit Coordination

## Overview

All download processes coordinate through a shared rate limit state file to be respectful of OpenTopography's API limits. This ensures that multiple scripts running simultaneously (or sequentially) respect rate limits collectively.

## How It Works

### Shared State File

Location: `data/.opentopography_rate_limit.json`

All download processes check this file before making requests and update it when they receive rate limit errors (401 responses).

### Simple Backoff Strategy

- **Initial backoff**: 10 minutes after first 401
- **Exponential backoff**: Doubles for each consecutive 401 (10min → 20min → 40min → 80min → ...)
- **Request spacing**: 0.5 second delay between requests (only for OpenTopography)


### Automatic Coordination

**Before any download:**
```python
from src.downloaders.rate_limit import check_rate_limit

ok, reason = check_rate_limit()
if not ok:
    print(f"Rate limited: {reason}")
    return False

# Proceed with download...
```

**When receiving 401:**
```python
from src.downloaders.rate_limit import record_rate_limit_hit

if response.status_code == 401:
    record_rate_limit_hit(response.status_code)
    # This updates shared state file with backoff period
    raise OpenTopographyRateLimitError("Rate limited")
```

## For Users

### Check Current Status

```bash
python check_rate_limit.py
```

Sample output:
```
======================================================================
  OpenTopography Rate Limit Status
======================================================================
  Status: RATE LIMITED
  Consecutive violations: 2
  Backoff active: YES
  Backoff until: 2025-11-02 15:30:00
  Time remaining: 20 minutes

  State file: data/.opentopography_rate_limit.json (234 bytes)
======================================================================

Recommendation: Downloads are currently blocked
Reason: Rate limited until 2025-11-02 15:30:00 (20 minutes remaining). Consecutive 401 errors: 2
```

### Clear Rate Limit (Manual Override)

```bash
# Clear if backoff period has expired
python check_rate_limit.py --clear

# Force clear even if backoff still active (use cautiously)
python check_rate_limit.py --force-clear
```

### Wait Until Ready

```bash
# Blocks until rate limit clears
python check_rate_limit.py --wait
```

## Backoff Strategy

### First 401 Response
- Wait: 10 minutes
- Next violation: 20 minutes

### Second 401 Response
- Wait: 20 minutes (doubled)
- Next violation: 40 minutes

### Third 401 Response
- Wait: 40 minutes (doubled)
- Next violation: 80 minutes (1.3 hours)

### Subsequent 401 Responses
- Continues doubling: 80min → 160min (2.7hrs) → 320min (5.3hrs) → etc.
- No maximum cap - exponential backoff continues

### Successful Request After Violations
- Resets consecutive violation counter to 0
- Returns to 10-minute initial backoff for next violation

## Implementation Details

### Thread-Safe File Locking

Uses `filelock` library to prevent race conditions when multiple processes access the state file simultaneously:

```python
import filelock

with filelock.FileLock(LOCK_FILE, timeout=10):
    # Read/write state file
    pass
```

### Request Spacing

Adds 0.5 second delay between OpenTopography requests to avoid triggering burst-detection rate limits. This is transparent to users but helps avoid limits.

## Updated Functions

All OpenTopography download functions now check rate limits:

- `src/downloaders/opentopography.py`:
  - `download_srtm()` - SRTM 30m downloads
  - `download_copernicus()` - Copernicus DEM downloads

- `src/downloaders/srtm_90m.py`:
  - `download_single_tile_90m()` - 90m tile downloads
  - `download_srtm_90m_single()` - 90m single-file downloads

- `src/tile_manager.py`:
  - `download_and_merge_tiles()` - Multi-tile downloads

## State File Format

```json
{
  "rate_limited": true,
  "backoff_until": "2025-11-02T15:30:00",
  "backoff_seconds": 1200,
  "consecutive_violations": 2,
  "last_request_time": "2025-11-02T13:25:00",
  "rate_limit_hit_time": "2025-11-02T13:30:00",
  "response_code": 401
}
```

## For Developers

### Adding Rate Limit Checks to New Downloaders

```python
from src.downloaders.rate_limit import (
    check_rate_limit,
    record_rate_limit_hit,
    record_successful_request
)

def download_from_opentopography(url, params):
    # 1. Check rate limit before request
    ok, reason = check_rate_limit()
    if not ok:
        print(f"Rate limited: {reason}")
        return False
    
    # 2. Make request
    response = requests.get(url, params=params)
    
    # 3. Check for 401
    if response.status_code == 401:
        record_rate_limit_hit(response.status_code)
        raise OpenTopographyRateLimitError("Rate limited")
    
    # 4. Download successful
    # ... download data ...
    
    # 5. Record success
    record_successful_request()
    
    return True
```

### Available Functions

```python
# Check if OK to proceed
ok, reason = check_rate_limit()

# Record 401 response
record_rate_limit_hit(response_code=401)

# Record successful request
record_successful_request()

# Get status dict
status = get_rate_limit_status()

# Clear rate limit state
clear_rate_limit(force=False)

# Wait until cleared
wait_if_rate_limited(verbose=True)
```

## Why This Approach?

### Good Citizenship
- Respects API provider's limits
- Prevents account suspension
- Ensures long-term access

### Multi-Process Coordination
- Multiple scripts can run safely
- Shared state prevents duplicate violations
- One process hitting limit protects all others

### Simple and Predictable
- Exponential backoff with no artificial caps
- Clear escalation: 10min → 20min → 40min → 80min...
- Resets completely on successful request

### User-Friendly
- Clear status messages
- Helpful recommendations
- Manual override when needed

## Troubleshooting

### "Rate limited but I haven't downloaded anything today"

Another process or previous run may have hit the limit. Check status:
```bash
python check_rate_limit.py
```

### "Want to override backoff period"

Use force clear (use cautiously):
```bash
python check_rate_limit.py --force-clear
```

### "State file corrupted"

Delete and recreate:
```bash
rm data/.opentopography_rate_limit.json
python check_rate_limit.py
```

### "Multiple scripts hitting limits"

This is expected - they're all checking the same state file. This is the correct behavior for coordination.

## References

- OpenTopography API: https://portal.opentopography.org/
- Rate Limit Module: `src/downloaders/rate_limit.py`
- CLI Utility: `check_rate_limit.py`


