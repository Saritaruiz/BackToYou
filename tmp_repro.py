import http.client
import urllib.parse
import uuid

base = '127.0.0.1'
port = 8000

conn = http.client.HTTPConnection(base, port)
login_data = urllib.parse.urlencode({
    'institutionalEmail': 'sruizo@eafit.edu.co',
    'password': 'nieveshermosa',
    'next': '/report/create?type=Lost'
})
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Content-Length': str(len(login_data))
}
conn.request('POST', '/login', login_data.encode('utf-8'), headers)
resp = conn.getresponse()
print('LOGIN', resp.status, resp.reason)
cookie = resp.getheader('Set-Cookie')
print('COOKIE', cookie)
print('LOCATION', resp.getheader('Location'))
resp.read()
conn.close()

cookie_header = cookie.split(';', 1)[0] if cookie else ''
conn = http.client.HTTPConnection(base, port)
conn.request('GET', '/report/create?type=Lost', headers={'Cookie': cookie_header})
resp = conn.getresponse()
print('GET create', resp.status, resp.reason)
print('GET location', resp.getheader('Location'))
print(resp.read().decode('utf-8', 'replace')[:500])
conn.close()

boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
fields = {
    'title': 'Test report',
    'description': 'Test description',
    'category': 'Electronics',
    'itemDate': '2026-08-07',
    'itemLocation': 'Test location',
    'type': 'Lost'
}
lines = []
for name, value in fields.items():
    lines.append('--' + boundary)
    lines.append(f'Content-Disposition: form-data; name="{name}"')
    lines.append('')
    lines.append(value)
lines.append('--' + boundary + '--')
lines.append('')
body = '\r\n'.join(lines).encode('utf-8')
headers = {
    'Cookie': cookie_header,
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'Content-Length': str(len(body))
}
conn = http.client.HTTPConnection(base, port)
conn.request('POST', '/report/create', body, headers)
resp = conn.getresponse()
print('POST create', resp.status, resp.reason)
print('POST location', resp.getheader('Location'))
print(resp.read().decode('utf-8', 'replace')[:1000])
conn.close()
