import hashlib
from pathlib import Path

tif_path = Path('data/regions/minnesota.tif')
expected_hash = "1b6b18fed30c0a7a0599bd2b45f5bdcc"

print(f"Checking: {tif_path}")
with open(tif_path, 'rb') as f:
    actual_hash = hashlib.md5(f.read()).hexdigest()

print(f"Expected hash: {expected_hash}")
print(f"Actual hash:   {actual_hash}")
print(f"Match: {actual_hash == expected_hash}")

