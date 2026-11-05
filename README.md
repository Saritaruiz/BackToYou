# BackToYou

**Lost. Found. Back to You.**

BackToYou is a web application for the EAFIT community that centralizes the reporting, searching, moderation, and recovery of lost and found items.

The project is developed as part of **Proyecto Integrador 1** at **Universidad EAFIT**.

## Team

- Sara Ruiz
- Isabel Acevedo Acosta

## Main Objective

BackToYou provides a single, organized, and secure space where members of the EAFIT community can:

- Register using an institutional `@eafit.edu.co` email.
- Report lost items.
- Report found items.
- Upload item images.
- Browse active reports.
- Search and filter reports.
- View report details.
- Contact report creators through internal messaging.
- Track their own reports.
- Mark recovered items.
- Receive submission confirmations.
- Receive email notifications.
- Allow administrators to moderate reports.
- Allow administrators to manage categories.

## User Roles

### Regular User

A member of the EAFIT community registered with an institutional email.

Regular users can:

- Create Lost and Found reports.
- Upload images.
- Browse and search active reports.
- View report details.
- Contact other report creators.
- Edit and delete their own reports.
- Mark active reports as recovered.
- View their report history.

### Administrator

An application-level BackToYou administrator.

Administrators can additionally:

- Access the BackToYou administration panel.
- Review pending reports.
- Approve reports.
- Reject reports.
- Manage item categories.

> BackToYou `ADMINISTRATOR` is different from Django `is_staff` and `is_superuser`.

## Report Workflow

New reports are not immediately public.

```text
PENDING_REVIEW
      |
      +---- Approve ----> ACTIVE ----> RECOVERED
      |
      +---- Reject -----> REJECTED
```

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_categories
python manage.py runserver
```

`seed_categories` creates the default item categories (Electronics, IDs & cards, Bottles, and others). It only adds the ones that are missing, so it is safe to run again after pulling changes.

### AI-Based Object Description (FR22)

The AI suggestion button uses a vision model that runs locally with [Ollama](https://ollama.com). No token or internet connection is needed once the model is downloaded.

1. Install Ollama from https://ollama.com/download and leave it running.
2. Download the vision model (about 3 GB):

   ```bash
   ollama pull gemma3:4b
   ```

3. Start the app. The AI button is enabled when Ollama is running and has the model.

To use another vision model or another Ollama address, copy `ollama.env.example` as `ollama.env` and change the values. If Ollama is not running or the model is missing, the rest of the application works normally and the AI button is disabled.

Instead of Ollama, the suggestion can come from the Google Gemini API, which needs no local model: create an API key at https://aistudio.google.com/apikey, copy `gemini.env.example` as `gemini.env` and paste the key. When `GEMINI_API_KEY` has a value, the application uses Gemini; when it is empty, it uses Ollama. With Gemini, the item photos are sent to Google to generate the suggestion.

### Email (FR39, FR15)

Without any setup, emails (password recovery and notifications) are printed in the terminal where `runserver` is running.

To send real emails through Gmail:

1. Turn on 2-Step Verification in the Gmail account that will send the emails.
2. Create an app password at https://myaccount.google.com/apppasswords.
3. Copy `email.env.example` as `email.env` and fill in the account and the app password.
4. Restart the server.

`email.env` is in `.gitignore`, so the password never reaches GitHub.

### Translations (Spanish / English)

The interface is available in Spanish and English. The language is part of the URL (`/es/reports/`, `/en/reports/`) and users switch it with the ES / EN selector in the header. A visit without a language prefix uses the browser language, or Spanish when it is neither.

The source texts are written in English in the templates (`{% translate %}`, `{% blocktranslate %}`) and in the Python code (`gettext`). The Spanish translations are in `locale/es/LC_MESSAGES/django.po`, and Django reads the compiled `django.mo` next to it. Both files are in the repository, so nothing needs to be compiled to run the app.

After adding or changing texts:

1. Install GNU gettext. On Windows: `winget install mlocati.GetText`.
2. Update the `.po` file with the new texts, then write their translations (a text editor or [Poedit](https://poedit.net) works):

   ```bash
   python manage.py makemessages -l es --ignore=.venv
   ```

3. Compile it (Poedit also does this when it saves):

   ```bash
   python manage.py compilemessages --ignore=.venv
   ```

The tests in `reports/tests/test_i18n.py` fail if a text has no translation or if the `.mo` was not compiled after the `.po` changed.

### Tests

```bash
python manage.py test --settings=backtoyou.test_settings
```

## NFR33 - Performance audit

Measured with Django 6.0.7, SQLite and `backtoyou.test_settings`, using the
Django test client to render complete pages. Authenticated counts include
the session and user queries. Fixture creation and login are outside the
measurement. Tests compare 1 and 21 records (26 for notifications/history).

| Page or operation | Before | After |
| --- | ---: | ---: |
| Pending moderation, 1 / 21 reports | 4 / 24 | 3 / 3 |
| Moderation detail | 5 | 3 |
| Anonymous report detail | 2 | 1 |
| Owner/sender detail with messages and replies | 9 | 6 |
| Public search | 3 | 2 |
| Contact / reply form | 4 | 3 |
| Public list | 2 | 2 |
| My Reports | 3 | 3 |
| Flagged reports | 4 | 4 |
| Notifications / moderation history | 5 | 5 |
| Lost statistics page | 5 | 5 |

Changes and reasons:

- Join categories in the pending queue to eliminate one query per report.
- Join the category in public detail, and category/creator in moderation
  detail. Compare creator IDs for permissions without loading user objects.
- Reuse the category list for translated search and its filter dropdown.
- Prefetch replies without their authors: the template uses the parent
  sender and a fixed label for the owner's replies. Visibility is unchanged.
- Remove the unused report join from moderation history; the template reads
  its stored snapshot and `report_id`.
- Match suggestions still scan every eligible candidate in one query, but
  retain only the best five in a heap. Ranking storage is O(5), instead of
  O(number of matches), and selection is O(n log 5) instead of sorting all
  matches. Scores and date/ID tie-breaks are unchanged. The test places the
  best candidate last among 100 candidates to guard against early truncation.

Existing efficient paths are protected too: statistics use three aggregate
queries (one for homepage numbers), notifications remain paginated at 20,
flags preload their open flags, and My Reports joins categories. Account
lists use three queries including authentication; homepage and administration
overview use two and three respectively. No cache or new infrastructure is used.

Run the query budgets and regression:

```bash
python manage.py test reports.tests.test_nfr33_performance --settings=backtoyou.test_settings --noinput
python manage.py test reports --settings=backtoyou.test_settings --noinput
```

Limits: fixed query counts do not guarantee fixed runtime or a production
latency SLA. Public/owner/pending lists and message threads remain unpaginated;
large result sets still cost rendering time and memory. Text search normalizes
rows in SQLite, and suggestions still score all eligible candidates in Python.
The heap bounds retained rankings, not database-driver fetch buffers. These
changes preserve current behavior; high-volume pagination, search indexing and
load/concurrency benchmarks need representative production data and targets.
No schema migration is required.

## Deployment (AWS EC2)

BackToYou runs on a single Ubuntu 24.04 server with Gunicorn and Nginx. The SQLite database and the uploaded photos stay on the server's disk, so they survive updates. They are lost if the instance is terminated, so copy `local.sqlite3` and `media_local/` before doing that.

First install, on the server:

```bash
git clone https://github.com/Saritaruiz/BackToYou.git /home/ubuntu/BackToYou
cd /home/ubuntu/BackToYou
bash deploy/setup.sh <server IP or domain>
```

To update:

```bash
cd /home/ubuntu/BackToYou
git pull
bash deploy/setup.sh
```

The secret key, `DEBUG=False`, the allowed hosts and the email account live in `/etc/backtoyou.env`, which `setup.sh` creates the first time. Edit it with `sudo nano /etc/backtoyou.env` and then run `sudo systemctl restart backtoyou`. The application log is in `journalctl -u backtoyou`.

The server has no memory to run the Ollama model, so the AI button (FR22) uses the Google Gemini API there. Add `GEMINI_API_KEY=<your key>` to `/etc/backtoyou.env` and restart the service. Without a key, the AI button stays disabled.
