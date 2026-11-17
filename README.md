# 💬 ForeverTwo — a chat app built with Python & Django

*Two people. Forever connected.*

A clean, modern chat app you can run on your computer and put online for
your friends, classmates or team.

## ✨ Features

**Chatting**
- Public rooms, private rooms (invite only) and 1-to-1 **direct messages**
- Live updates with no page refresh, plus a **"typing…"** indicator
- **Seen ✓✓ / Sent ✓** receipts in direct messages
- **Delete for everyone** on your own messages
- Unread badges, browser-tab unread count, and green **online** dots
- Clickable links, date separators and grouping of back-to-back messages

**Media sharing**
- 📷 **Photos** (JPG, PNG, GIF, WebP) with a full-screen viewer and download
- 🎬 **Videos** (MP4, WebM, MOV) that play inside the chat, with seeking
- 📄 **Documents & files** (PDF, Word, Excel, PowerPoint, ZIP…) shown as download cards
- Preview screen with a **caption** before sending, plus an **upload progress bar**
- **Drag & drop** files onto the chat, or **paste** a screenshot into the message box
- Files are **private**: only people in that conversation can open them

**Voice & calls**
- 🎤 **Voice notes**: tap the mic, talk, send (up to 5 minutes), with a play/scrub player
- 📞 **Audio calls** and 🎥 **video calls** in direct messages: ringing, accept/decline,
  mute, camera on/off, call timer, "busy" detection
- Call history in the chat ("Video call · 4:12", "Missed audio call")

**Everything else**
- **Invite-only accounts**: no public sign-up. The admin (**Hustler**) creates every
  account on the **Manage users** page, then sends the login details by WhatsApp or
  copy-paste. New users must choose their own password at first login.
- The admin can **reset a password** or **deactivate** someone; everyone can
  **change their own password** (🔑 icon)
- 🔔 **Desktop pop-up notifications** (like WhatsApp Web) for new messages and
  incoming calls, with a notification sound
- Django **admin panel** at `/admin/` for advanced management
- Mobile-friendly design with a slide-out menu; automatic **dark mode**
- Security: CSRF protection, escaped messages, private rooms and files checked on
  the server, real-image checks on photos, dangerous file types (.exe…) blocked

---

## 📁 What's in the folder (and what each part does)

```
ForeverTwo/
├── manage.py              ← the command tool: run the server, migrate, create admin…
├── requirements.txt       ← the list of Python packages the app needs
├── .env.example           ← example settings (copy it to .env)
├── build.sh, render.yaml, Procfile  ← files used for hosting online
│
├── chatproject/           ← the PROJECT: global settings
│   ├── settings.py        ← all configuration (database, security, time zone…)
│   ├── urls.py            ← the main address book of the site
│   └── wsgi.py            ← the entry point a web server uses to run the app
│
├── chat/                  ← the APP: the chat itself
│   ├── models.py          ← database tables: Room, Message, ReadMarker, Presence, Typing, CallSignal
│   ├── media.py           ← checks uploaded files and sends them (with video seeking)
│   ├── views.py           ← Python functions that answer each page / API request
│   ├── urls.py            ← which web address goes to which view
│   ├── forms.py           ← sign-up form and create-room form
│   ├── admin.py           ← what you see in /admin/
│   ├── tests.py           ← automatic tests (python manage.py test)
│   └── migrations/        ← instructions that build the database tables
│
├── templates/             ← the HTML pages
│   ├── base.html
│   ├── registration/      ← login.html
│   └── chat/              ← room, manage_users, change_password, create_room…
│
└── static/chat/
    ├── style.css          ← all the design (colours, layout, dark mode, mobile, call screen)
    ├── app.js             ← live chat, file sharing, voice notes, typing, "Seen"
    └── call.js            ← audio & video calls (WebRTC)
```

### How "live" chat works here, in plain words

1. When you open a room, Django sends the page with the last 100 messages.
2. Every **2 seconds**, `app.js` quietly asks the server: *"any messages newer
   than number X?"* (`/api/rooms/<room>/messages/?after=X`). This is called
   **polling**.
3. When you press Enter, `app.js` sends your message to `/api/rooms/<room>/send/`.
4. Every **5 seconds** it also asks for unread counts and who is online
   (`/api/sidebar/`).

Polling is simple and works on **every** host, including free ones. (The
more advanced alternative is *WebSockets* with *Django Channels*. Look into
it once you are comfortable with this version.)

### How calls work, in plain words

The voice and video **do not pass through your server**. They travel directly
between the two browsers using a built-in browser technology called **WebRTC**.
To connect, the browsers first swap two small "letters":

1. The caller's browser writes an **offer**: "here is what I can send, and here
   are my network addresses."
2. Django stores it, and the other person's browser picks it up within about
   a second (`/api/calls/poll/`) and starts ringing.
3. If they accept, their browser writes an **answer** back.
4. The browsers connect to each other and the call starts.

**STUN** servers (free, already set up) help each browser discover its public
address. Some networks, especially mobile data and strict Wi-Fi, block direct
connections. Then you need a **TURN** server, which relays the call (see
section 6).

### How files are stored

Uploaded files go into the `media/` folder with random names. They are **not**
public: every download goes through the `message_file` view in `views.py`,
which checks that you belong to that conversation.

---

## 🖥️ 1. Run it on your computer

You need **Python 3.10 or newer** ([python.org](https://www.python.org/downloads/)).
On Windows, tick **"Add Python to PATH"** when you install it.

Open a terminal in the `ForeverTwo` folder and run:

**Windows (PowerShell / CMD)**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

**Mac / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open **http://127.0.0.1:8000** and log in with the admin account:

| Username | Password |
|---|---|
| `Hustler` | `Hustler@12345` |

(Use this exact address, not your IP, so the microphone, camera and
notifications are allowed.)

**To test chatting with a friend on your own computer:**
1. As Hustler, click **Manage users** → create a user (for example `grace`) and
   copy the password it shows.
2. Open a **private/incognito window** (Ctrl+Shift+N), go to the same address
   and log in as `grace`. You'll be asked to choose a new password.
3. Chat between the two windows.

> **What did those commands do?**
> `venv` makes a private box for this project's packages. `pip install`
> downloads Django and friends. `migrate` builds the database tables
> (it creates `db.sqlite3`). `runserver` starts a small test web server.

**Chat with phones on the same Wi-Fi:** run
`python manage.py runserver 0.0.0.0:8000`, add your computer's IP to
`DJANGO_ALLOWED_HOSTS` in `.env` (for example `localhost,127.0.0.1,192.168.1.20`),
then open `http://192.168.1.20:8000` on the phone.

**Run the tests:** `python manage.py test`

---

## 🐙 2. Put the code on GitHub

> ⚠️ **Important:** GitHub **stores** your code, but it cannot **run** a
> Django app. (GitHub Pages only serves plain HTML files.) To chat online you
> connect your GitHub repo to a free Python host: see step 3.

This project's repository: **https://github.com/dieu-black-hat/ForeverTwo-**

In the project folder, run:
```bash
git init
git add .
git commit -m "ForeverTwo chat app"
git branch -M main
git remote add origin https://github.com/dieu-black-hat/ForeverTwo-.git
git push -u origin main
```
If GitHub says the repository already has files (for example a README you
created on the website), run `git pull origin main --allow-unrelated-histories`
first, then push again.

When GitHub asks for a password, use a **Personal Access Token**, not your
normal password: GitHub → Settings → Developer settings → Personal access
tokens → *Generate new token (classic)* → tick **repo**.

The `.gitignore` file makes sure your database, your `.env` secrets, uploaded
media and the `venv` folder are **not** uploaded.

---

## 🌍 3. Put it online so others can chat

### Option A — PythonAnywhere (free, keeps your messages and photos) ⭐ recommended

Your link will be **https://YOUR-USERNAME.pythonanywhere.com**, so choose the
username you want your friends to see (for example `forevertwo`).

1. Create a free **Beginner** account at **pythonanywhere.com**.
2. **Web** tab → **Add a new web app** → *Next* → **Manual configuration**
   (not "Django") → **Python 3.12** → *Next*.
3. **Consoles** tab → **Bash**, and run:
   ```bash
   git clone https://github.com/dieu-black-hat/ForeverTwo-.git ForeverTwo
   cd ForeverTwo
   bash pythonanywhere_setup.sh
   ```
   The script installs everything, creates a secret key, builds the database
   and connects the website. At the end it prints what to check.
4. Back on the **Web** tab, set (one time only):
   - **Virtualenv**: `/home/YOUR-USERNAME/.virtualenvs/forevertwo`
   - **Static files**: URL `/static/` → Directory `/home/YOUR-USERNAME/ForeverTwo/staticfiles`
   - **Force HTTPS**: on

   Then click the big green **Reload** button.
5. Open **https://YOUR-USERNAME.pythonanywhere.com** and share that link 🎉

**To update the site later**, push your changes to GitHub, then in a
PythonAnywhere Bash console run:
```bash
cd ~/ForeverTwo && git pull && bash pythonanywhere_setup.sh
```

> Uploaded photos, videos and voice notes are saved in `~/ForeverTwo/media`.
> A free account has about 512 MB of disk space, so delete old media in `/admin/`
> if you run low.

> Free accounts ask you to log in about once every 3 months and click
> "Run until 3 months from today" to keep the site alive.

### Option B — Render.com (deploys straight from GitHub)

1. Push to GitHub (step 2).
2. On **render.com**: **New +** → **Blueprint** → choose your repo. Render reads
   `render.yaml` and creates the web service and a PostgreSQL database for you.
3. To get an admin account, add the environment variables
   `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD`, then redeploy.

> On Render's free plan the site "sleeps" after about 15 minutes without
> visitors (the first visit after that is slow), and the free database is
> temporary. **Uploaded files are also wiped on every redeploy**, because the
> free disk is not permanent. For a chat with photos and voice notes, PythonAnywhere
> (Option A) is the better free choice.

---

## 👑 4. Your admin account & inviting friends

`python manage.py migrate` creates the admin account automatically:
**username `Hustler`, password `Hustler@12345`**.

> ⚠️ **Change this password as soon as your site is online.** Your code is on
> public GitHub, so anyone who reads this README knows the default password.
> Log in → click the 🔑 icon at the bottom of the sidebar → choose a new
> password. (Or set `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env` **before**
> running `migrate` for the first time.)

**How the admin adds a friend:**
1. Sidebar → **Manage users** (only admins see it).
2. Type a username. Leave the password empty and a strong one is generated for you.
3. A green card shows the login details **once**. Click **Send on WhatsApp**
   or **Copy message** and send it to your friend.
4. Your friend opens the link, logs in, and must choose their own password.
   Even you won't know their new password.

In the list of users you can also **Reset password** (if someone forgets it) or
**Deactivate** an account (they can't log in any more, but their messages stay).
Tick *"Make this person an admin too"* to let someone else manage users.

---

## 🔔 5. Desktop notifications (pop-ups like WhatsApp)

The first time you log in, the sidebar shows **"Get message pop-ups → Turn on"**.
Click it and choose **Allow** when the browser asks. You can also use the 🔔
bell icon at the bottom of the sidebar (yellow = on, click it to see a test pop-up).

After that, a pop-up appears in the corner of your Windows screen for every new
message (and for incoming calls), with a short "ding". Click the pop-up to
jump straight to that chat.

- **Keep the ForeverTwo tab open.** It can be minimised or behind other windows.
  Like WhatsApp Web, if you close the tab, the pop-ups stop.
- Works on `https://` sites and on `http://127.0.0.1`.
- If you clicked *Block* by mistake: click the 🔒 icon next to the address →
  **Notifications → Allow**, then reload the page.
- No pop-ups at all? Check Windows **Settings → System → Notifications**: make
  sure notifications are on for Chrome/Edge and *Do not disturb* is off.

---

## 📞 6. Calls, voice notes & HTTPS: important

- **Browsers only allow the microphone and camera on `https://` sites**, or on
  `http://localhost` / `127.0.0.1`. PythonAnywhere and Render give you https
  for free, so it works there. On your Wi-Fi with `http://192.168.x.x`, voice
  notes and calls are blocked; text and files still work.
- **Calls on the same Wi-Fi** usually work with no extra setup. **Calls between
  different networks** (for example one person on MTN data, the other on campus
  Wi-Fi) may fail with "the network blocked the connection". Fix this by adding a
  **TURN server**. Several providers offer a free monthly allowance (for example
  Metered.ca's "Open Relay"). Sign up, then add the details they give you to `.env`:
  ```
  TURN_URLS=turn:your-turn-server:80,turn:your-turn-server:443?transport=tcp
  TURN_USERNAME=your-username
  TURN_CREDENTIAL=your-password
  ```
- Calls are **1-to-1** and are started from a **direct message** (📞 and 🎥 buttons
  at the top). Keep the chat page open: closing or reloading the page ends the call.
- Size limits (change them in `.env`): photos 10 MB (`CHAT_MAX_IMAGE_MB`), videos
  100 MB (`CHAT_MAX_VIDEO_MB`), other files 25 MB (`CHAT_MAX_FILE_MB`).

---

## 🎨 Make it yours

| What | Where |
|---|---|
| App name | `SITE_NAME` in `.env` |
| Main colour | `--accent` at the top of `static/chat/style.css` |
| Time zone | `TIME_ZONE` in `.env` (default `Africa/Kigali`) |
| Max message length / history size | bottom of `chatproject/settings.py` |
| Default rooms | `chat/migrations/0002_default_rooms.py`, or create them in `/admin/` |
| How often it checks for messages | `setTimeout(poll, … 2000)` in `static/chat/app.js` |

## 🚀 Ideas for the next version (good practice!)

- Edit messages and reply to a specific message
- Group calls (needs a media server such as LiveKit or Jitsi)
- Profile pictures
- Push notifications even when the browser is closed (Web Push + service worker)
- Real-time WebSockets with Django Channels and Redis
- Search inside messages

## 🛠️ Common problems

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'django'` | Activate the venv first (`venv\Scripts\activate` or `source venv/bin/activate`) |
| `DisallowedHost` / "Bad Request (400)" | Add your domain to `DJANGO_ALLOWED_HOSTS` in `.env` |
| "CSRF verification failed" when logging in online | Set `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain` |
| Site has no styling online | Run `python manage.py collectstatic`, then reload |
| `Set the DJANGO_SECRET_KEY…` error | You set `DEBUG=False` without a secret key: add one to `.env` |
| "Please enter a correct username and password" for Hustler | The admin is created by `migrate`. Run `python manage.py migrate`. Usernames are case-sensitive: `Hustler` |
| Forgot the admin password | `python manage.py changepassword Hustler` |
| No notification pop-ups | See section 5 (allow notifications in the browser and in Windows settings) |
| Mic/camera "blocked" | Use `https://` or `localhost`, then allow the permission in the browser (🔒 icon by the address) |
| Call says "the network blocked the connection" | Add a TURN server (section 6) |
| Big video upload fails online | The host may limit upload size: lower `CHAT_MAX_VIDEO_MB` or compress the video |
| `no such column` after updating from an older version | Delete `db.sqlite3` and run `python manage.py migrate` again (this erases old messages) |
| `psycopg` fails to install | You only need it for PostgreSQL. Delete that line in `requirements.txt` if you use SQLite |
