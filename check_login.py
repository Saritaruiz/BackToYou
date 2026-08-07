import urllib.request
import urllib.error

url = 'http://127.0.0.1:8000/login'
req = urllib.request.Request(url, method='GET')

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print('STATUS', resp.status)
        body = resp.read().decode('utf-8', errors='replace')
        print(body[:800])
except urllib.error.HTTPError as e:
    print('HTTPERROR', e.code)
    print(e.read().decode('utf-8', errors='replace')[:800])
except Exception as e:
    print('ERROR', e)
