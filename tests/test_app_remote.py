"""Run the dashboard in remote mode (against the API) via AppTest."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SMART_CAM_API_URL"] = "http://localhost:8000"

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), default_timeout=120)
at.run()
print("exceptions:", len(at.exception))
for e in at.exception:
    print("ERR:", e.message)
print("REMOTE APP TEST PASSED" if len(at.exception) == 0 else "REMOTE APP TEST FAILED")
