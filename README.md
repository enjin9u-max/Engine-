# Telegram Media Downloader Bot — Admin Build

## Security first
The bot token previously pasted into chat must be treated as exposed. Open @BotFather, select this bot, use `/revoke` to invalidate the old token, then issue a new token. Put the new token only in your hosting provider's secret/environment-variable settings. Do not commit it to GitHub or send it in chat.

## Admin
- Owner numeric ID: `8899247188`
- Display username: `@Ezjxz`
- Open the panel with `/admin`.
- `/stats` shows runtime statistics.
- `/setmax 49` changes the upload cap for the current running session (1–49 MB).
- The panel lets the owner view stats, change default video quality, and enable/disable user downloads.
- Admin authorization checks the numeric Telegram ID, not the username.

## Deploy
Set `BOT_TOKEN` as a secret environment variable on the host. `ADMIN_IDS` is optional because the owner ID is built into `bot.py`.

For Docker:
```bash
docker build -t media-bot .
docker run -d --name media-bot --restart unless-stopped \
  -e BOT_TOKEN='YOUR_NEW_TOKEN' media-bot
```

## Android browser + GitHub
1. Open GitHub in Chrome and open your private repository.
2. Replace `bot.py`, `requirements.txt`, and `Dockerfile` with these versions.
3. Commit changes.
4. In your cloud host, set the new token as a secret named `BOT_TOKEN`, then redeploy.
5. In Telegram, send `/admin` to your bot.

## Limits
The bot supports yt-dlp-compatible public URLs for content you own or are authorized to download. It does not bypass DRM, paywalls, private content, or access controls. 4K depends on source availability and Telegram upload limits; this build caps uploads at 49 MB.
