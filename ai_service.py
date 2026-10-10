import os
import re
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-3.5-flash-lite"

SYSTEM = ("You are an expert career coach and professional resume writer. "
          "Be concise, specific, and honest. Never invent facts the candidate did not provide.")


def ask(prompt, max_tokens=1000):
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM),
    )
    return resp.text.strip()

def resume_text(r):
    return (f"Name: {r.name}\nEmail: {r.email}\nPhone: {r.phone}\nLinks: {r.links}\n"
            f"Education:\n{r.education}\n\nSkills:\n{r.skills}\n\n"
            f"Experience:\n{r.experience}\n\nProjects:\n{r.projects}")


def improve_summary(r):
    return ask("Write a professional resume summary of 3-4 lines for this candidate. "
               "Return only the summary text, nothing else.\n\n" + resume_text(r), 400)


def ats_check(r, jd):
    out = ask(
        "Compare this resume against the job description. Return ONLY valid JSON with keys: "
        "score (integer 0-100), matched_keywords (list of strings), "
        "missing_keywords (list of strings), suggestions (list of 5 short, actionable strings).\n\n"
        f"RESUME:\n{resume_text(r)}\n\nJOB DESCRIPTION:\n{jd}", 900)
    m = re.search(r"\{.*\}", out, re.S)
    data = json.loads(m.group(0))
    data["score"] = max(0, min(100, int(data.get("score", 0))))
    return json.dumps(data)


def cover_letter(r, jd):
    return ask("Write a professional cover letter (under 250 words) for this candidate "
               f"applying to the job below.\n\nRESUME:\n{resume_text(r)}\n\nJOB DESCRIPTION:\n{jd}", 700)


def interview_questions(r, jd):
    return ask("List 8 likely interview questions (mix of technical and HR) for this candidate "
               "and job. For each question add a one-line tip on how to answer.\n\n"
               f"RESUME:\n{resume_text(r)}\n\nJOB DESCRIPTION:\n{jd}", 900)