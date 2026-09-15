import os
import sys

ZHIXUE = os.environ.get("ZHIXUE_HOME") or r"D:\ZhixueAI"
os.environ["ZHIXUE_HOME"] = ZHIXUE
os.environ["ZHIXUE_RUNTIME_SRC"] = os.path.join(ZHIXUE, "runtime_package", "v1", "src")

# make `app` importable from the runtime-service root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
