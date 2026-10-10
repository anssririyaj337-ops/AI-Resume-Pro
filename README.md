# AI Resume Pro

An AI-powered resume builder with ATS analysis, built with Flask, MySQL and the Gemini API.

## Features
- Register, login, logout (password hashing, CSRF protection)
- Create, edit, delete resumes with 3 templates and PDF download
- AI summary, ATS match score, cover letter, interview questions

## Tech stack
Python, Flask, SQLAlchemy, MySQL (local) / PostgreSQL (online), Jinja2, Gemini API

## Run locally
1. python -m venv venv, then venv\Scripts\activate
2. pip install -r requirements.txt
3. Create a .env file with GEMINI_API_KEY, SECRET_KEY and DATABASE_URL
4. python app.py, then open http://127.0.0.1:5000

## Author
[Riyaz Ansari], [B.Tech CSE], [DR.KNMIET]