"""Loaded automatically in Python child processes when NX2A payload is on PYTHONPATH."""
try:
    import network_log  # installs the urllib.request.urlopen audit hook
except Exception:
    pass
