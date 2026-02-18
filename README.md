# 🏦 Bank API Watchdog

![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![Discord.py](https://img.shields.io/badge/Discord.py-API-5865F2?style=for-the-badge&logo=discord)
![Aiohttp](https://img.shields.io/badge/AsyncIO-aiohttp-green?style=for-the-badge)

A fast, asynchronous Discord bot designed to monitor internal bank payment APIs, report transaction volumes, and track API health statuses in real-time. Built with a focus on reliability and DevOps practices.

## ✨ Features

- **🚀 Asynchronous Engine:** Utilizes `aiohttp` for non-blocking API requests, ensuring the bot remains responsive even during high-latency network events.
- **📊 Interactive Dashboard:** A persistent Discord UI (Buttons & Modals) allowing authorized users to query transaction data for Today, Yesterday, or any Custom Date.
- **⏰ Automated Reporting:** Built-in scheduled tasks (`discord.ext.tasks`) to automatically fetch and broadcast daily summaries at 07:30 AM.
- **🛡️ Secure Configuration:** Environment variable (`.env`) management to protect sensitive Bot Tokens and API endpoints.
- **🧹 Auto-Cleanup:** Smart channel management that purges old report messages to keep the monitoring channel clean and readable.

## 🛠️ Tech Stack

- **Core:** Python 3.12
- **Libraries:** `discord.py`, `aiohttp`, `python-dotenv`
- **Architecture:** Object-Oriented Programming (OOP) with distinct layers (Config, Engine, UI, Main).

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sarawutms/bank-api-watchdog.git
   cd bank-api-watchdog
   ```

2. **Set up Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
Create a .env file in the root directory and add your credentials:
   ```bash
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_id/your_webhook_token
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   DISCORD_CHANNEL_ID=your_discord_channel_id_here
   BANK_API_URL=http://your-internal-api-ip/api/v1/endpoint
   ALLOWED_USER_IDS=user_id_1,user_id_2
   TIMEZONE=Asia/Bangkok
   ```

5. **Run the Application:**
   ```bash
   python main.py
   ```

## 🚀 Deployment (Background Process)

### For a simple background deployment on a Linux server (Ubuntu/Debian):
   ```bash
   nohup python main.py > bot.log 2>&1 &
   ```

## 🔍 Monitoring & Management

### Once the bot is running in the background, you can use these essential Linux commands to monitor its status:

1. **Check if the bot is running:**

### Look for main.py in the output to confirm the bot is active. You will also see its PID (Process ID).
   ```bash
   ps aux | grep python
   ```

2. **View live logs:**

### Streams the log file in real-time to monitor activity and catch errors. (Press Ctrl+C to exit).
   ```bash
   tail -f bot.log
   ```

3. **Stop the bot:**

### (Replace <PID> with the actual Process ID found in step 1).
   ```bash
   kill <PID>
   ```python main.py
   
