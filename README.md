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

### Email (FR39, FR15)

Without any setup, emails (password recovery and notifications) are printed in the terminal where `runserver` is running.

To send real emails through Gmail:

1. Turn on 2-Step Verification in the Gmail account that will send the emails.
2. Create an app password at https://myaccount.google.com/apppasswords.
3. Copy `email.env.example` as `email.env` and fill in the account and the app password.
4. Restart the server.

`email.env` is in `.gitignore`, so the password never reaches GitHub.

### Tests

```bash
python manage.py test --settings=backtoyou.test_settings
```
