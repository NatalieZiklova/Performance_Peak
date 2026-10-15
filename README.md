# Spot-price AI interviewer: free setup

A 3-minute survey people open by scanning a QR code. It asks three tap questions, then an AI asks follow-up questions about incentives (if they follow the price) or constraints (if they don't), and saves everything to a Google Sheet.

Total cost: 0 €. You need a Google account, a GitHub account and a phone number for Mistral.

## 1. Get a free Mistral API key (5 min)
1. Sign up at console.mistral.ai and choose the free **Experiment** plan (no credit card; phone verification).
2. Create an API key and copy it.

Note: on the free plan, Mistral may use requests to train its models. The answers are anonymous and the consent screen says an AI service processes them, but mention it to your supervisor or ethics contact if the data will be used for research.

## 2. Set up the Google Sheet (15 min)
1. Create an empty Google Sheet, for example "Spot price responses".
2. In Google Cloud Console (free), create a project, enable the **Google Sheets API** and **Google Drive API**, then create a **service account** and download its JSON key.
3. Share the Sheet with the service account's email address (found in the JSON key) as **Editor**.

You can skip this step for a first test: answers then go to a local `responses.csv`, but on the free hosting that file disappears when the app restarts.

## 3. Put the code on GitHub (5 min)
Create a new repository and upload `app.py` and `requirements.txt`.

## 4. Deploy on Streamlit Community Cloud (10 min)
1. Go to share.streamlit.io, sign in with GitHub and click **Create app**.
2. Pick your repository and `app.py`.
3. Under **Advanced settings → Secrets**, paste the following, filled in with your values:

```toml
MISTRAL_API_KEY = "your-mistral-key"
SHEET_NAME = "Spot price responses"
CURRENCY = "NOK"   # or "EUR" for euro bill ranges

[gcp_service_account]
# paste every field from the service account JSON key here, e.g.
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

4. Deploy. You get a public link like `https://your-app.streamlit.app`.

## 5. Test, then make the QR code
- Run about 10 test conversations on your phone, covering both branches, and check the rows appear in the Sheet. Delete the test rows afterwards.
- Free Streamlit apps go to sleep after a period without visits. Open the link yourself shortly before the presentation to wake it up.
- Generate a QR code from the link and put it on the last slide.

## Changing the questions
Everything is at the top of `app.py`: the answer options, the currency, the AI's instructions (`SYSTEM_PROMPT`) and the maximum number of open answers (`MAX_USER_TURNS`).

If the AI service is unavailable, the app still runs: it asks a fixed opening question and thanks the respondent, so no one gets stuck.
