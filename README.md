# CodeAlpha Social Media Platform

## About
A simple social media platform built for the CodeAlpha Full Stack Development Internship.

## Features
- **User Authentication**: User registration with password hashing, login, and session logout.
- **User Profiles**: Profiles with bios, profile pictures, joined date, and live counters.
- **Posts System**: Create, edit, and delete posts with optional image attachments and a reverse-chronological feed.
- **Comments**: Comment on posts and delete your own comments.
- **Likes**: Like and unlike posts with real-time database counters and duplicate prevention.
- **Follow / Following System**: Follow and unfollow users with real-time profile follower/following counts.
- **Django Admin**: Administrative dashboard to view, search, and manage users, profiles, posts, comments, likes, and follows.

## Technologies
- Python
- Django
- SQLite
- HTML
- CSS
- JavaScript

## Project Structure
```text
CodeAlpha_SocialMediaPlatform/
├── manage.py
├── requirements.txt
├── README.md
├── .gitignore
├── social_project/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── social/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── signals.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── templates/
│   └── social/
│       ├── base.html
│       ├── home.html
│       ├── login.html
│       ├── register.html
│       ├── profile.html
│       ├── edit_profile.html
│       ├── create_post.html
│       ├── edit_post.html
│       ├── delete_post.html
│       └── post_detail.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

## How to Run

### 1. Create a Python Virtual Environment
```bash
python -m venv .venv
```

### 2. Activate the Virtual Environment
- **Windows (Command Prompt / PowerShell)**:
  ```bash
  .venv\Scripts\activate
  ```
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. (Optional) Run Automated Tests
```bash
python manage.py test
```

### 6. Start the Development Server
```bash
python manage.py runserver
```

Open your browser and navigate to:
```text
http://127.0.0.1:8000/
```
