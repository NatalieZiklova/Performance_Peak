"""
Spot-price interview: a short AI-led survey people open from a QR code.

Flow: consent -> 3 tap questions -> short AI follow-up chat -> thank you.
LLM: Mistral API (free "Experiment" plan). Storage: Google Sheet (free),
with a local CSV fallback for testing.
"""

import csv
import json
import os
import uuid
from datetime import datetime, timezone

import requests
import streamlit as st

# ----------------------------------------------------------------- settings
def secret(name: str, default=None):
    """Read a Streamlit secret, then an environment variable; never crash."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:  # no secrets.toml at all
        pass
    return os.environ.get(name, default)


MODEL = "mistral-small-latest"
MAX_USER_TURNS = 3  # open answers before the agent must wrap up

CONTRACT_OPTIONS = ["Fixed price", "Spot (hourly) price", "Norgespris", "Don't know"]
BILL_OPTIONS = {
    "NOK": ["Under 500 NOK", "500–1,000 NOK", "1,000–2,000 NOK",
            "2,000–3,000 NOK", "Over 3,000 NOK", "Don't know"],
    "EUR": ["Under €50", "€50–100", "€100–200", "€200–300", "Over €300", "Don't know"],
}
CURRENCY = secret("CURRENCY", "NOK")
CHECK_OPTIONS = ["Yes", "Sometimes", "No"]

SYSTEM_PROMPT = """You are a friendly research interviewer for a University of Bologna study on how people respond to electricity prices. You are chatting on a phone, so keep every message to one or two short sentences and ask only ONE question per message.

The respondent has already answered:
- Electricity contract: {contract}
- Last monthly bill: {bill}
- Checks the electricity price or adjusts when they use electricity: {checks}

Your task: {task}

Rules:
- Let them answer freely first. Never suggest motives or reasons yourself (for example money, climate or comfort) before they mention them.
- Probe at most twice, e.g. "Can you give a concrete example?" or "What would have to change?".
- Accept "don't know" without pressure. Never give advice, tips or opinions, and never judge their habits. If asked for tips, say the study will share some afterwards.
- Never ask for names, emails, addresses or other personal details.
- Reply in the language the respondent writes in.
- When you have enough (or after their third answer), write a one-sentence summary of what they told you, ask if it is correct, and thank them. Put the token [END] at the very end of that final message, and only there.
"""

TASK_YES = ("Find out their main reasons for following the price or shifting their use. "
            "Open with: 'What are the main reasons you do that?'")
TASK_NO = ("Find out what stops them from following the price or shifting their use, and what would "
           "have to change for them to start. Open with: 'What stops you from doing that?'")


# ---------------------------------------------------------------- LLM call
def ask_llm(messages: list[dict]) -> str:
    key = secret("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is not set")
    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL, "messages": messages, "temperature": 0.4, "max_tokens": 200},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ------------------------------------------------------------------ storage
def save_response(row: dict) -> None:
    """Append one row to the Google Sheet; fall back to a local CSV."""
    account, sheet = secret("gcp_service_account"), secret("SHEET_NAME")
    if account and sheet:
        import gspread  # imported here so local tests don't need it

        gc = gspread.service_account_from_dict(dict(account))
        ws = gc.open(sheet).sheet1
        if not ws.row_values(1):
            ws.append_row(list(row.keys()))
        ws.append_row(list(row.values()))
        return
    path = "responses.csv"
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------------- UI
st.set_page_config(page_title="Electricity & you", page_icon="⚡", layout="centered")
s = st.session_state
s.setdefault("stage", "consent")
s.setdefault("answers", {})
s.setdefault("chat", [])  # [{"role": "user"|"assistant", "content": str}]
s.setdefault("session_id", uuid.uuid4().hex[:10])
s.setdefault("saved", False)


def go(stage: str) -> None:
    s.stage = stage
    st.rerun()


def tap_question(key: str, question: str, options: list[str], next_stage: str) -> None:
    st.subheader(question)
    for opt in options:
        if st.button(opt, key=f"{key}-{opt}", use_container_width=True):
            s.answers[key] = opt
            go(next_stage)


st.title("⚡ Electricity & you")

if s.stage == "consent":
    st.write("A 3-minute anonymous chat about how you use electricity. "
             "Your answers are used for research only, and we never ask for your name. "
             "Answers are processed by an AI service (Mistral) to run the chat.")
    if st.button("I agree, start", type="primary", use_container_width=True):
        go("q1")

elif s.stage == "q1":
    tap_question("contract", "Do you pay a fixed price or a spot (hourly) price for electricity?",
                 CONTRACT_OPTIONS, "q2")

elif s.stage == "q2":
    tap_question("bill", "Roughly what was your last monthly electricity bill?",
                 BILL_OPTIONS.get(CURRENCY, BILL_OPTIONS["NOK"]), "q3")

elif s.stage == "q3":
    tap_question("checks", "Do you ever check the electricity price or adjust when you use electricity?",
                 CHECK_OPTIONS, "chat")

elif s.stage == "chat":
    a = s.answers
    branch_yes = a["checks"] in ("Yes", "Sometimes")
    system = SYSTEM_PROMPT.format(contract=a["contract"], bill=a["bill"], checks=a["checks"],
                                  task=TASK_YES if branch_yes else TASK_NO)

    # First AI message
    if not s.chat:
        try:
            opening = ask_llm([{"role": "system", "content": system},
                               {"role": "user", "content": "(The respondent is ready. Ask your opening question.)"}])
        except Exception:
            opening = ("What are the main reasons you do that?" if branch_yes
                       else "What stops you from doing that?")
        s.chat.append({"role": "assistant", "content": opening})

    for m in s.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"].replace("[END]", "").strip())

    finished = s.chat[-1]["role"] == "assistant" and "[END]" in s.chat[-1]["content"]
    if finished:
        if st.button("Finish", type="primary", use_container_width=True):
            go("done")
    elif reply := st.chat_input("Type your answer…"):
        s.chat.append({"role": "user", "content": reply})
        user_turns = sum(m["role"] == "user" for m in s.chat)
        msgs = [{"role": "system", "content": system}] + s.chat
        if user_turns >= MAX_USER_TURNS:
            msgs.append({"role": "system",
                         "content": "Wrap up now: one-sentence summary, ask if correct, thank them, end with [END]."})
        try:
            answer = ask_llm(msgs)
        except Exception:
            answer = "Thank you, that's really helpful! That's all our questions. [END]"
        if user_turns >= MAX_USER_TURNS and "[END]" not in answer:
            answer += " [END]"
        s.chat.append({"role": "assistant", "content": answer})
        st.rerun()

elif s.stage == "done":
    if not s.saved:
        row = {
            "session_id": s.session_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "contract": s.answers.get("contract", ""),
            "bill": s.answers.get("bill", ""),
            "checks_price": s.answers.get("checks", ""),
            "branch": "incentives" if s.answers.get("checks") in ("Yes", "Sometimes") else "constraints",
            "open_answers": " | ".join(m["content"] for m in s.chat if m["role"] == "user"),
            "transcript": json.dumps(s.chat, ensure_ascii=False),
        }
        try:
            save_response(row)
            s.saved = True
        except Exception as e:  # keep the respondent's experience clean
            st.caption(f"(Could not save: {e})")
    st.success("Thank you for taking part! 🙏")
    st.write("You can close this page now.")
