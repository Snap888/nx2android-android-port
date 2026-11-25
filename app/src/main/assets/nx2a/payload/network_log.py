"""Small, low-overhead audit hook for outbound Python HTTP requests made by the launcher and Porter tools."""
import os, re, sys, time, threading
from urllib.parse import urlsplit

_LOCK = threading.Lock()
_PATH = os.environ.get('NX2A_NETWORK_LOG', '/sdcard/Switch/nx2android-network.log')
_MAX = 2 * 1024 * 1024
try:
    import urllib.request as _request
    _ORIGINAL_URLOPEN = _request.urlopen
except Exception:
    _ORIGINAL_URLOPEN = None

def _safe_url(url):
    try:
        p = urlsplit(str(url))
        # Keep host/path and query parameter names, never query values/tokens.
        query = '&'.join((part.split('=', 1)[0] + '=REDACTED') for part in p.query.split('&') if part)
        return p.scheme + '://' + p.netloc + p.path + (('?' + query) if query else '')
    except Exception:
        return '<unparseable-url>'

def _write(message):
    line = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' [NET] ' + message + '\n'
    try:
        with _LOCK:
            parent = os.path.dirname(_PATH)
            if parent: os.makedirs(parent, exist_ok=True)
            try:
                if os.path.exists(_PATH) and os.path.getsize(_PATH) > _MAX:
                    os.replace(_PATH, _PATH + '.1')
            except OSError: pass
            with open(_PATH, 'a', encoding='utf-8') as f: f.write(line)
    except Exception: pass
    try: sys.stderr.write(line); sys.stderr.flush()
    except Exception: pass

class _LoggedResponse:
    def __init__(self, response, url, method, sent, started):
        self._response, self._url, self._method = response, url, method
        self._sent, self._started, self._received, self._done = sent, started, 0, False
        try: self._status = response.status
        except Exception: self._status = '?'
    def __getattr__(self, name): return getattr(self._response, name)
    def read(self, *args, **kwargs):
        data = self._response.read(*args, **kwargs)
        self._received += len(data or b'')
        if not data or not args or (args and isinstance(args[0], int) and args[0] < 0): self._finish('complete')
        return data
    def readinto(self, b):
        n = self._response.readinto(b)
        self._received += int(n or 0)
        if not n: self._finish('complete')
        return n
    def _finish(self, result):
        if self._done: return
        self._done = True
        ms = int((time.monotonic() - self._started) * 1000)
        _write(f'{result} method={self._method} status={self._status} sent={self._sent}B received={self._received}B elapsed={ms}ms url={self._url}')
    def close(self):
        try: self._response.close()
        finally: self._finish('closed')
    def __enter__(self): self._response.__enter__(); return self
    def __exit__(self, typ, value, tb):
        try: return self._response.__exit__(typ, value, tb)
        finally: self._finish('complete' if typ is None else 'error')

def logged_urlopen(url, data=None, timeout=... , *, context=None, cafile=None, capath=None, cadefault=False, context2=None):
    if _ORIGINAL_URLOPEN is None: raise RuntimeError('urllib is unavailable')
    request = url
    try:
        method = request.get_method() if hasattr(request, 'get_method') else ('POST' if data is not None else 'GET')
        target = request.full_url if hasattr(request, 'full_url') else str(request)
        body = request.data if hasattr(request, 'data') else data
        sent = len(body) if isinstance(body, (bytes, bytearray, str)) else 0
    except Exception:
        method, target, sent = 'GET', str(url), 0
    safe = _safe_url(target); started = time.monotonic()
    _write(f'start method={method} sent={sent}B url={safe}')
    try:
        kwargs = {}
        if timeout is not ...: kwargs['timeout'] = timeout
        if context is not None: kwargs['context'] = context
        if cafile is not None: kwargs['cafile'] = cafile
        if capath is not None: kwargs['capath'] = capath
        if cadefault: kwargs['cadefault'] = cadefault
        response = _ORIGINAL_URLOPEN(url, data=data, **kwargs)
        return _LoggedResponse(response, safe, method, sent, started)
    except Exception as error:
        ms = int((time.monotonic() - started) * 1000)
        _write(f'error method={method} sent={sent}B elapsed={ms}ms url={safe} error={type(error).__name__}:{str(error)[:180]}')
        raise

if _ORIGINAL_URLOPEN is not None:
    _request.urlopen = logged_urlopen
