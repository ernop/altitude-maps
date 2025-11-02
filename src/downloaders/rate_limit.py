"""
OpenTopography rate limit coordination using shared state file.

All download processes check and update a shared rate limit state file to
coordinate backoff when hitting API limits. This ensures good citizenship
with the OpenTopography API.

Conservative defaults based on typical API limits:
- Initial backoff: 1 hour after 401
- Max backoff: 24 hours (for repeated violations)
- Small delay between requests: 0.5s (avoid bursts)
- Assumes daily quota ~1000-2000 requests (typical free tier)

Usage:
    from src.downloaders.rate_limit import check_rate_limit, record_rate_limit_hit
    
    # Before any OpenTopography download:
    if not check_rate_limit():
        print("Rate limited - waiting...")
        return False
    
    # After receiving 401:
    record_rate_limit_hit()
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import filelock


# State file location (shared across all processes)
STATE_FILE = Path("data/.opentopography_rate_limit.json")
LOCK_FILE = Path("data/.opentopography_rate_limit.lock")

# Conservative rate limit settings (erring on the side of caution)
INITIAL_BACKOFF_SECONDS = 3600      # 1 hour initial wait after 401
MAX_BACKOFF_SECONDS = 86400         # 24 hours max wait (for repeated violations)
BACKOFF_MULTIPLIER = 2.0            # Double wait time for each subsequent 401
REQUEST_DELAY_SECONDS = 0.5         # Small delay between requests to avoid bursts
DAILY_REQUEST_LIMIT = 1000          # Conservative estimate of daily quota


def _ensure_state_dir():
    """Ensure the state file directory exists."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_state() -> Dict:
    """
    Read current rate limit state from shared file.
    
    Returns:
        Dict with keys:
        - rate_limited: bool
        - backoff_until: ISO timestamp string
        - backoff_seconds: current backoff duration
        - consecutive_violations: count of 401s in sequence
        - last_request_time: ISO timestamp of last successful request
        - requests_today: count of requests made today
        - day_started: ISO timestamp of when current day count started
    """
    _ensure_state_dir()
    
    if not STATE_FILE.exists():
        return {
            'rate_limited': False,
            'backoff_until': None,
            'backoff_seconds': INITIAL_BACKOFF_SECONDS,
            'consecutive_violations': 0,
            'last_request_time': None,
            'requests_today': 0,
            'day_started': datetime.now().isoformat()
        }
    
    try:
        with filelock.FileLock(str(LOCK_FILE), timeout=10):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # Corrupted or missing file - reset state
        return {
            'rate_limited': False,
            'backoff_until': None,
            'backoff_seconds': INITIAL_BACKOFF_SECONDS,
            'consecutive_violations': 0,
            'last_request_time': None,
            'requests_today': 0,
            'day_started': datetime.now().isoformat()
        }


def _write_state(state: Dict) -> None:
    """Write rate limit state to shared file (thread-safe with file locking)."""
    _ensure_state_dir()
    
    try:
        with filelock.FileLock(str(LOCK_FILE), timeout=10):
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
    except filelock.Timeout:
        print("WARNING: Could not acquire rate limit state file lock")


def check_rate_limit() -> Tuple[bool, Optional[str]]:
    """
    Check if it's OK to make an OpenTopography request.
    
    Returns:
        Tuple of (ok_to_proceed: bool, reason_if_blocked: Optional[str])
        
    Examples:
        ok, reason = check_rate_limit()
        if not ok:
            print(f"Rate limited: {reason}")
            return False
    """
    state = _read_state()
    
    # Check if we're in active backoff period
    if state['rate_limited'] and state['backoff_until']:
        backoff_until = datetime.fromisoformat(state['backoff_until'])
        now = datetime.now()
        
        if now < backoff_until:
            remaining = (backoff_until - now).total_seconds()
            hours = remaining / 3600
            if hours >= 1:
                time_str = f"{hours:.1f} hours"
            else:
                time_str = f"{remaining / 60:.0f} minutes"
            
            reason = (
                f"Rate limited until {backoff_until.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({time_str} remaining). "
                f"Previous 401 errors: {state['consecutive_violations']}"
            )
            return False, reason
        else:
            # Backoff period expired - clear rate limit but keep monitoring
            state['rate_limited'] = False
            state['backoff_until'] = None
            # Don't reset consecutive_violations yet - only on successful request
            _write_state(state)
    
    # Check daily request limit (very conservative)
    day_started = datetime.fromisoformat(state['day_started'])
    now = datetime.now()
    
    # Reset daily counter if it's a new day
    if now.date() > day_started.date():
        state['requests_today'] = 0
        state['day_started'] = now.isoformat()
        _write_state(state)
    
    if state['requests_today'] >= DAILY_REQUEST_LIMIT:
        reason = (
            f"Daily request limit reached ({DAILY_REQUEST_LIMIT} requests). "
            f"Will reset at midnight. Current time: {now.strftime('%H:%M:%S')}"
        )
        return False, reason
    
    # Check minimum delay between requests (avoid bursts)
    if state['last_request_time']:
        last_request = datetime.fromisoformat(state['last_request_time'])
        time_since_last = (now - last_request).total_seconds()
        
        if time_since_last < REQUEST_DELAY_SECONDS:
            # Small delay to avoid bursts
            sleep_time = REQUEST_DELAY_SECONDS - time_since_last
            time.sleep(sleep_time)
    
    return True, None


def record_rate_limit_hit(response_code: int = 401) -> None:
    """
    Record that we received a rate limit error (401).
    Updates shared state file to coordinate backoff across all processes.
    
    Args:
        response_code: HTTP response code (default 401)
    """
    state = _read_state()
    now = datetime.now()
    
    # Increment consecutive violations
    state['consecutive_violations'] = state.get('consecutive_violations', 0) + 1
    
    # Calculate backoff duration (exponential backoff with max cap)
    violations = state['consecutive_violations']
    backoff_seconds = min(
        INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (violations - 1)),
        MAX_BACKOFF_SECONDS
    )
    
    state['rate_limited'] = True
    state['backoff_seconds'] = backoff_seconds
    state['backoff_until'] = (now + timedelta(seconds=backoff_seconds)).isoformat()
    state['rate_limit_hit_time'] = now.isoformat()
    state['response_code'] = response_code
    
    _write_state(state)
    
    # Log the event
    hours = backoff_seconds / 3600
    print(f"\n{'='*70}")
    print(f"  RATE LIMIT HIT RECORDED (violation #{violations})")
    print(f"{'='*70}")
    print(f"  Response code: {response_code}")
    print(f"  Backoff duration: {hours:.1f} hours ({backoff_seconds:.0f} seconds)")
    print(f"  Backoff until: {state['backoff_until']}")
    print(f"  All processes will respect this limit")
    print(f"{'='*70}\n")


def record_successful_request() -> None:
    """
    Record a successful request (non-401 response).
    Updates last request time and resets violation counter on success.
    """
    state = _read_state()
    now = datetime.now()
    
    state['last_request_time'] = now.isoformat()
    state['requests_today'] = state.get('requests_today', 0) + 1
    
    # Reset consecutive violations after successful request
    if state.get('consecutive_violations', 0) > 0:
        print(f"  Rate limit cleared - successful request after {state['consecutive_violations']} violations")
        state['consecutive_violations'] = 0
        state['backoff_seconds'] = INITIAL_BACKOFF_SECONDS
    
    _write_state(state)


def get_rate_limit_status() -> Dict:
    """
    Get current rate limit status for display/debugging.
    
    Returns:
        Dict with human-readable status information
    """
    state = _read_state()
    now = datetime.now()
    
    status = {
        'rate_limited': state['rate_limited'],
        'consecutive_violations': state.get('consecutive_violations', 0),
        'requests_today': state.get('requests_today', 0),
        'daily_limit': DAILY_REQUEST_LIMIT,
    }
    
    if state.get('backoff_until'):
        backoff_until = datetime.fromisoformat(state['backoff_until'])
        if now < backoff_until:
            remaining = (backoff_until - now).total_seconds()
            status['backoff_active'] = True
            status['backoff_until'] = state['backoff_until']
            status['remaining_seconds'] = remaining
        else:
            status['backoff_active'] = False
    else:
        status['backoff_active'] = False
    
    return status


def clear_rate_limit(force: bool = False) -> bool:
    """
    Clear rate limit state (admin function for manual override).
    
    Args:
        force: If True, clear even if backoff period hasn't expired
        
    Returns:
        True if cleared, False if refused (backoff still active and force=False)
    """
    state = _read_state()
    
    if not force and state.get('backoff_until'):
        backoff_until = datetime.fromisoformat(state['backoff_until'])
        if datetime.now() < backoff_until:
            print("Backoff period still active. Use force=True to override.")
            return False
    
    # Reset to clean state
    state = {
        'rate_limited': False,
        'backoff_until': None,
        'backoff_seconds': INITIAL_BACKOFF_SECONDS,
        'consecutive_violations': 0,
        'last_request_time': None,
        'requests_today': 0,
        'day_started': datetime.now().isoformat()
    }
    _write_state(state)
    
    print("Rate limit state cleared")
    return True


def wait_if_rate_limited(verbose: bool = True) -> bool:
    """
    Block until rate limit clears (useful for interactive scripts).
    
    Args:
        verbose: Print waiting messages
        
    Returns:
        True when ready to proceed
    """
    while True:
        ok, reason = check_rate_limit()
        if ok:
            return True
        
        if verbose:
            print(f"Rate limited: {reason}")
            print("Waiting for backoff period to expire...")
        
        # Wait 60 seconds and check again
        time.sleep(60)

