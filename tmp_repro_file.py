import http.client
import urllib.parse
import uuid

base = '127.0.0.1'
port = 8000

# login
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
cookie = resp.getheader('Set-Cookie')
cookie_header = cookie.split(';', 1)[0] if cookie else ''
resp.read()
conn.close()

boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
fields = {
    'title': 'Test report with image',
    'description': 'Test description with image',
    'category': 'Electronics',
    'itemDate': '2026-08-07',
    'itemLocation': 'Test location',
    'type': 'Lost'
}
file_field = ('itemImage', 'test.png', b'PNGDATA')
lines = []
for name, value in fields.items():
    lines.append('--' + boundary)
    lines.append(f'Content-Disposition: form-data; name="{name}"')
    lines.append('')
    lines.append(value)
lines.append('--' + boundary)
lines.append(f'Content-Disposition: form-data; name="{file_field[0]}"; filename="{file_field[1]}"')
lines.append('Content-Type: image/png')
lines.append('')
body = '\r\n'.join(lines).encode('utf-8') + b'\r\n' + file_field[2] + b'\r\n' + ('--' + boundary + '--\r\n').encode('utf-8')
headers = {
    'Cookie': cookie_header,
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'Content-Length': str(len(body))
}
conn = http.client.HTTPConnection(base, port)
conn.request('POST', '/report/create', body, headers)
resp = conn.getresponse()
print('STATUS', resp.status, resp.reason)
print('LOCATION', resp.getheader('Location'))
print(resp.read().decode('utf-8', 'replace')[:1000])
conn.close()
