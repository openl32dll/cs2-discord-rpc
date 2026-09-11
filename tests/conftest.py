import os
import sys

# Allow "import cs2_discord_rpc" without installing the package first —
# it's a single top-level module living at the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
