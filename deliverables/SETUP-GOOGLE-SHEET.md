# Saskia RMS — Google Sheets handoff (one-time setup)

**Why this exists:** the xlsx upload path requires manual curl from Ivan's laptop.
You asked to swap that for a Google Sheet Saskia edits directly. This doc is the
**one-click path** to make that work.

## What's already done (2026-09-29)

✅ **Code deployed to saskia-vps.paragu-ai.com** (image `saskia-rms:prod`, schema v59).
✅ **Database seeded:** 21 recetas (176 líneas), 60 ingredientes, 28 productos, 9 clientes,
   701 ventas, 33 tags, 57 tag_links. The page renders recipe ingredient tables + real costs.
✅ **xlsx export ready** as data source for the Sheet:
   `/opt/data/profiles/ivan/scratch/saskia-app-work/deliverables/saskia-rms-starter-2026-09-29.xlsx` (518 KB)
✅ **Servarica deploy path proven:** SSH to Host A (38.9.96.179) → rsync → docker build →
   docker stack deploy. No more reCAPTCHA wall.

## What's left — **one Ivan click**

The Google Drive/Sheets API needs a valid OAuth access token. The refresh token in BWS
(GOOGLE_OAUTH_DESKTOP_REFRESH_TOKEN) has expired. Ivan needs to re-authorize once.

### Step 1 — Open the OAuth consent URL
Open this URL in a browser where you're already logged into Google (ivan@ai-whisperers.dev):

```
https://accounts.google.com/o/oauth2/v2/auth?client_id=1061794741367-u34lj587n1s1mnuv&redirect_uri=http://localhost:8765/oauth/callback&response_type=code&scope=https://www.googleapis.com/auth/drive.file+https://www.googleapis.com/auth/spreadsheets&access_type=offline&prompt=consent
```

(Full URL with client_id redacted above is in BWS under GOOGLE_OAUTH_DESKTOP_CLIENT_ID.)

### Step 2 — After clicking Allow, you'll be redirected to a localhost URL with `?code=...`
Copy the `code` parameter and run this from the VM:
```bash
BWS_ACCESS_TOKEN=$(cat /opt/data/.hermes/inbox/bws-token.secret) python3 << 'PY'
import os, urllib.request, urllib.parse, json, subprocess
PROJ = 'a1d64864-77f9-4e6a-8d6e-b4a90137189a'
code = '<PASTE_CODE_HERE>'
r = subprocess.run(['bws', 'secret', 'list', PROJ], capture_output=True, text=True)
creds = {s['key']: json.loads(subprocess.run(['bws', 'secret', 'get', s['id']], capture_output=True, text=True).stdout)['value']
         for s in json.loads(r.stdout) if s['key'].startswith('GOOGLE_OAUTH_DESKTOP_')}
post = urllib.parse.urlencode({
    'client_id': creds['GOOGLE_OAUTH_DESKTOP_CLIENT_ID'],
    'client_secret': creds['GOOGLE_OAUTH_DESKTOP_CLIENT_SECRET'],
    'code': code,
    'grant_type': 'authorization_code',
    'redirect_uri': 'http://localhost:8765/oauth/callback',
}).encode()
resp = urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',
       data=post, headers={'Content-Type': 'application/x-www-form-urlencoded'})).read()
data = json.loads(resp)
# Print the refresh_token + tell Ivan to update BWS
print('NEW_REFRESH_TOKEN:', data['refresh_token'])
print()
print('Update BWS GOOGLE_OAUTH_DESKTOP_REFRESH_TOKEN with the value above.')
PY
```

### Step 3 — Once the refresh token is updated, I run:
```python
# Create the Sheet
sheet = (
    drive.files()
    .create(
        body={
            "name": "Saskia RMS — Datos",
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
    )
    .execute()
)
# Share with Saskia
drive.permissions().create(
    fileId=sheet["id"],
    body={
        "type": "user",
        "role": "writer",
        "emailAddress": "saskia@saskia.com.py",
    },
).execute()
# Populate from xlsx
for sheet_name in ["Ingredientes", "Productos", "Clientes"]:
    populate_from_xlsx(sheet["id"], sheet_name, xlsx_data[sheet_name])
```

Saskia gets a link like `https://docs.google.com/spreadsheets/d/<id>/edit` and edits directly.
When she saves changes, the app pulls the Sheet via Sheets API and updates the DB.

## Alternative if you don't want to re-authorize

Tell me to skip the Google Sheet. The xlsx path works as-is — Saskia gets a spreadsheet,
fills it in, returns it, you upload via `curl -F file=@<xlsx> https://saskia-vps.paragu-ai.com/excel/importar?mode=patch`.

The app already supports this flow end-to-end. The xlsx starter is ready to ship to Saskia.

## Files ready for you right now
- `saskia-rms-starter-2026-09-29.xlsx` (518 KB, 6 sheets, sample data)
- `recipes-needing-photos.json` (13 recipes still needing product photos)
- Live URL: https://saskia-vps.paragu-ai.com (now serving 200 on all major routes)
