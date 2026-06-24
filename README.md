# Compass · Company Bookmarks Wiki

Internal resource directory — a dynamic, searchable wiki of bookmarks and links organized by department.

## How it works

- Reads data from a **Google Sheet** (via service account) every hour
- **Google OAuth login** gated to `@roofstock.com` emails + whitelist
- Sleek dark-themed UI with search, grouped by department/section header
- Hosted on **Render**, kept warm by **UptimeRobot**
- Data refreshed hourly via **cron-job.org**

## Tech Stack

- **Flask** (Python) — web server
- **Gunicorn** — production WSGI
- **Google Sheets API** — data source
- **pyjwt** — JWT-based service account auth (bundled, no heavy deps)

## Sheet Structure

| Column | Field           | Notes                     |
|--------|-----------------|---------------------------|
| A      | Section Header  | Grouping / department     |
| B      | Title           | Bookmark name             |
| C      | Link            | URL                       |
| D      | Owner           | (ignored)                 |
| E      | Approved to Push| Only `TRUE` rows shown    |
| F      | Long Description| Shown on the card         |

## Environment Variables (Render)

| Variable                 | Description                                      |
|--------------------------|--------------------------------------------------|
| `GOOGLE_CLIENT_ID`       | Google OAuth client ID                           |
| `GOOGLE_CLIENT_SECRET`   | Google OAuth client secret                       |
| `SESSION_SECRET`         | Flask session key (auto-generated if unset)      |
| `GOOGLE_SERVICE_ACCOUNT` | Full service account JSON as a single-line string |
| `SLACK_WEBHOOK_URL`      | (Optional) Slack webhook for access requests      |

## Deployment

1. Push this repo to GitHub
2. Create a **Web Service** on Render
3. Set the environment variables above
4. Deploy — the app reads the sheet on startup and refreshes every hour

## Keeping Warm

- **cron-job.org**: Hit `https://your-app.onrender.com/health` every 5 minutes
- **UptimeRobot**: Monitor same URL to prevent Render cold starts