"""
CLI utility to check and manage OpenTopography rate limit state.

Usage:
    python check_rate_limit.py               # Show current status
    python check_rate_limit.py --clear       # Clear rate limit (manual override)
    python check_rate_limit.py --force-clear # Force clear even if backoff active
    python check_rate_limit.py --wait        # Wait until rate limit clears
"""

import sys
import argparse
from pathlib import Path

from src.downloaders.rate_limit import (
    get_rate_limit_status,
    clear_rate_limit,
    wait_if_rate_limited,
    check_rate_limit,
    STATE_FILE
)


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds >= 3600:
        hours = seconds / 3600
        return f"{hours:.1f} hours"
    elif seconds >= 60:
        minutes = seconds / 60
        return f"{minutes:.0f} minutes"
    else:
        return f"{seconds:.0f} seconds"


def show_status():
    """Display current rate limit status."""
    status = get_rate_limit_status()
    
    print("\n" + "="*70)
    print("  OpenTopography Rate Limit Status")
    print("="*70)
    
    if status['rate_limited']:
        print("  Status: RATE LIMITED")
        print(f"  Consecutive violations: {status['consecutive_violations']}")
        
        if status.get('backoff_active'):
            remaining = status['remaining_seconds']
            print(f"  Backoff active: YES")
            print(f"  Backoff until: {status['backoff_until']}")
            print(f"  Time remaining: {format_time(remaining)}")
        else:
            print(f"  Backoff active: NO (expired)")
    else:
        print("  Status: OK - No active rate limits")
    
    # Check if state file exists
    if STATE_FILE.exists():
        file_size = STATE_FILE.stat().st_size
        print(f"  State file: {STATE_FILE} ({file_size} bytes)")
    else:
        print(f"  State file: Not created yet")
    
    print("="*70 + "\n")
    
    # Show recommendation
    ok, reason = check_rate_limit()
    if not ok:
        print("Recommendation: Downloads are currently blocked")
        print(f"Reason: {reason}\n")
    else:
        print("Recommendation: OK to proceed with downloads\n")


def main():
    parser = argparse.ArgumentParser(
        description="Check and manage OpenTopography rate limit state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_rate_limit.py                  # Show current status
  python check_rate_limit.py --clear          # Clear rate limit
  python check_rate_limit.py --force-clear    # Force clear (override backoff)
  python check_rate_limit.py --wait           # Wait until rate limit clears
        """
    )
    
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear rate limit state (only if backoff expired)'
    )
    
    parser.add_argument(
        '--force-clear',
        action='store_true',
        help='Force clear rate limit even if backoff still active'
    )
    
    parser.add_argument(
        '--wait',
        action='store_true',
        help='Wait until rate limit clears (blocks until ready)'
    )
    
    args = parser.parse_args()
    
    if args.clear or args.force_clear:
        force = args.force_clear
        print("\n" + "="*70)
        print(f"  {'Force ' if force else ''}Clearing rate limit state...")
        print("="*70 + "\n")
        
        if clear_rate_limit(force=force):
            print("Rate limit state cleared successfully\n")
            show_status()
        else:
            print("Could not clear rate limit (backoff still active)")
            print("Use --force-clear to override\n")
            show_status()
            return 1
    
    elif args.wait:
        print("\n" + "="*70)
        print("  Waiting for rate limit to clear...")
        print("="*70 + "\n")
        
        wait_if_rate_limited(verbose=True)
        print("\nRate limit cleared - ready to proceed!\n")
        show_status()
    
    else:
        # Default: just show status
        show_status()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


