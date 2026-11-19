"""Is vimeus.com really serving its player? Its domain can expire and show a parking page
with HTTP 200, so a plain status check is not enough. Cached so playback never waits on it."""
import os
import threading
import time
import requests

PARKED_MARKERS = ('/lander', 'domain has expired', 'this domain is for sale', 'domain parking', 'parkingcrew')


class VimeusHealth:
    def __init__(self, get=requests.get, clock=time.monotonic, url='https://vimeus.com/'):
        self.get, self.clock, self.url = get, clock, url
        self.lock = threading.Lock()
        self.until, self.up = 0.0, True

    def __call__(self):
        if os.getenv('VIMEUS_DISABLED') == 'true':  # manual switch on Render
            return False
        with self.lock:
            if self.clock() < self.until:
                return self.up
            up = self.check()
            # Re-check a broken provider sooner than a healthy one.
            self.up, self.until = up, self.clock() + (600 if up else 120)
            return up

    def check(self):
        try:
            response = self.get(self.url, timeout=(1.5, 2.5), allow_redirects=False,
                                headers={'User-Agent': 'QueHay-health/1.0'})
        except requests.RequestException:
            return False
        if response.status_code >= 500:
            return False
        location = response.headers.get('Location', '') if 300 <= response.status_code < 400 else ''
        body = (response.text or '')[:20000].lower() if response.status_code < 300 else ''
        return not any(marker in body or marker in location.lower() for marker in PARKED_MARKERS)


vimeus_up = VimeusHealth()
