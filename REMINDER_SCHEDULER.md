# Phase11-4B Same-Day 9 AM Reminder Scheduler

## Architecture decision

The reminder engine is implemented as a dedicated Flask CLI job rather than an in-process APScheduler instance.

This avoids:
- Flask development reloader starting the scheduler twice.
- Gunicorn multiple workers each running the same scheduler.
- Deploy restarts creating overlapping scheduler instances.

Duplicate delivery is also blocked at the database layer by a unique `sms_logs.dedupe_key`. The key includes booking ID, template, recipient, and the booking start datetime. Re-running the job for the same schedule is skipped; changing the booking time creates a new valid reminder key.

## Database setup

```bash
cd /path/to/SalonDeNature_ManagementSystem
source venv/bin/activate
python create_sms_tables.py
```

## Manual verification with SMS disabled

Keep this in `.env`:

```env
SMS_ENABLED=false
```

Then run:

```bash
flask --app app reminders run
```

The default run processes bookings for today in the Asia/Seoul timezone. To process a specific booking date:

```bash
flask --app app reminders run --date 2026-07-16
```

Eligible reminders create `skipped` SMS logs without contacting Solapi. Running the same command again produces duplicate skips without creating duplicate SMS log rows.

## Recommended production scheduling: systemd timer

Create `/etc/systemd/system/salondenature-reminder.service`:

```ini
[Unit]
Description=Salon De Nature booking reminder job
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/var/www/SalonDeNature_ManagementSystem
Environment=FLASK_APP=app
ExecStart=/var/www/SalonDeNature_ManagementSystem/venv/bin/flask --app app reminders run
```

Create `/etc/systemd/system/salondenature-reminder.timer`:

```ini
[Unit]
Description=Run Salon De Nature booking reminders daily

[Timer]
OnCalendar=*-*-* 09:00:00 Asia/Seoul
Persistent=true
Unit=salondenature-reminder.service

[Install]
WantedBy=timers.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now salondenature-reminder.timer
sudo systemctl list-timers | grep salondenature-reminder
```

A cron entry calling the same Flask CLI command daily at 09:00 Asia/Seoul is also safe because database deduplication remains active.
