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
