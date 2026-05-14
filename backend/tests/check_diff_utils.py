"""Quick sanity check for diff_utils."""
import sys
sys.path.insert(0, ".")
from services.diff_utils import parse_diff_positions, find_closest_position

test_diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,5 @@
 import os
+
+SECRET = "abc123"
 
 def main():
"""

result = parse_diff_positions(test_diff)
print("Position map:", result)

# Line 3 in the new file should be mapped to a position
if "test.py" in result:
    print("test.py positions:", result["test.py"])
    pos = find_closest_position(result["test.py"], 3)
    print(f"Line 3 -> Position {pos}")
    print("OK - diff_utils works!")
else:
    print("ERROR: test.py not found in position map")
