"""Re-export Nebraska with aspect-preserving downsampling."""
import sys
from pathlib import Path
from download_regions import process_region

# Nebraska info
nebraska_info = {
    "bounds": (-104.05, 40.00, -95.31, 43.00),
    "name": "Nebraska",
    "description": "Nebraska - Great Plains, Sand Hills"
}

# Process Nebraska
success = process_region(
    "nebraska",
    nebraska_info,
    Path("data/regions"),
    Path("generated/regions"),
    max_size=800
)

if success:
    print("\n✅ Nebraska re-exported successfully!")
    sys.exit(0)
else:
    print("\n❌ Failed to re-export Nebraska")
    sys.exit(1)

