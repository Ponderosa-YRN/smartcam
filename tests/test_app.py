"""Run the Streamlit app via AppTest and check for exceptions (e.g. duplicate IDs)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py"), default_timeout=120)
at.run()
print("exceptions:", len(at.exception))
for e in at.exception:
    print("ERR:", e.message)
if len(at.exception) == 0:
    print("APP TEST PASSED (no exceptions)")
else:
    print("APP TEST FAILED")
