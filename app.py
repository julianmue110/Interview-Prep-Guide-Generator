import streamlit as st
import urllib.parse
import requests
import pandas as pd
from bs4 import BeautifulSoup
import cohere

st.markdown("""
    <style>
    /* Main app background */
    [data-testid="stAppViewContainer"] {
        background-color: #fdf6e3;
    }

    /* Sidebar (if used) */
    [data-testid="stSidebar"] {
        background-color: #f5f0da;
    }

    /* Main content area */
    [data-testid="stAppViewContainer"] > .main {
        background-color: #fdf6e3;
    }
    </style>
""", unsafe_allow_html=True)

# ──────────────────────── Setup ────────────────────────
COHERE_API_KEY = "fBHX6T5DR8UZSewEO3T26io3MRDYQes4NI4rOEoH"
co = cohere.ClientV2(COHERE_API_KEY)

# FinancialModelingPrep API key and base URL
FMP_API_KEY = "DLHlD9A4nSmMccInKupXe6KswgCyFxdN"
FMP_BASE = "https://financialmodelingprep.com/api/v3"

# ───────────── Lookup ticker via company name ─────────────
def lookup_ticker(company_name: str) -> str | None:
    url = f"{FMP_BASE}/search"
    params = {"query": company_name, "limit": 1, "apikey": FMP_API_KEY}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    return results[0].get("symbol") if results else None

# ───────────── Company profile & metrics ─────────────
def get_company_profile(symbol: str) -> dict:
    url = f"{FMP_BASE}/profile/{symbol.upper()}"
    resp = requests.get(url, params={"apikey": FMP_API_KEY}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"No profile data for ticker '{symbol}'")
    return data[0]

# ───────────── Improved Wikipedia infobox scraper ─────────────
def scrape_infobox_df(company: str):
    base = "https://en.wikipedia.org/wiki/"
    slug = urllib.parse.quote(company.replace(" ", "_"))
    url = f"{base}{slug}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.select_one("table.infobox.vcard, table.infobox.ib-company.vcard")
    if not table:
        raise ValueError(f"No infobox found for '{company}'")

    rows = []
    for tr in table.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not (th and td):
            continue
        for sup in td.find_all("sup"):
            sup.decompose()
        key = th.get_text(" ", strip=True)
        val = td.get_text(" ", strip=True)
        rows.append((key, val))

    df = pd.DataFrame(rows, columns=["Field", "Value"])
    logo = None
    img = table.select_one("tr td.infobox-image img")
    if img:
        src = img.get('src')
        logo = 'https:' + src if src.startswith('//') else src
    return df, logo

# ───────────── Interview prep generator ─────────────
def generate_interview_prep(company: str, role: str) -> str:
    prompt = f'Please write me an interview prep guide for company "{company}" tailored to a "{role}" role.'
    resp = co.chat(
        model="command-r-plus",
        messages=[{"role":"user","content":prompt}],
        temperature=0.7
    )
    return resp.message.content[0].text.strip()

# ───────────── Follow-up Q&A ─────────────
def answer_followup_question(prep: str, question: str) -> str:
    prompt = f"""You are an interview prep assistant. The following is the original prep guide:

{prep}

Now answer the follow-up question: '{question}'"""
    resp = co.chat(
        model="command-r-plus",
        messages=[{"role":"user","content":prompt}],
        temperature=0.7
    )
    return resp.message.content[0].text.strip()

# ──────────────── Streamlit Interface ────────────────
st.title("📝 Interview Prep Guide Generator")
st.markdown("""
This tool:
- 🗂️ Scrapes Wikipedia for company infobox + logo
- 📊 Fetches full company profile via FMP and displays all available financial metrics
- 🔎 Auto-looks-up the company’s stock ticker if available to manually check financials on any financial website if financial metrics are not available
- 🤖 Generates an AI-powered interview prep guide tailored to the role and offers follow-up Q&A as well as a Mock Interview Quiz
- 📥 Download the prep guide as a text file
- NOTE: Please be patient as the request may take a few seconds to generate the prep guide and make sure to have your browser in light mode for better readability.
""")

company = st.text_input("🏢 Company name (Wikipedia)", "Volkswagen")
role = st.selectbox(
    "💼 Role you're applying for",
    ["Software Engineer", "Product Manager", "Data Analyst", "Marketing Specialist", "Other"]
)
custom_role = None
if role == "Other":
    custom_role = st.text_input("Please specify your role", "")
    display_role = custom_role.strip() or "Other"
else:
    display_role = role

if "prep_guide" not in st.session_state:
    st.session_state.prep_guide = ""

if st.button("Generate Interview Prep"):
    if not company.strip():
        st.warning("Please enter a company name.")
        st.stop()
    if role == "Other" and not custom_role.strip():
        st.warning("Please specify your role.")
        st.stop()

    # 1) Infobox
    st.subheader("📘 1. Wikipedia Infobox")
    try:
        info_df, logo_url = scrape_infobox_df(company)
        if logo_url:
            st.image(logo_url, width=200, caption=f"{company} logo")
        st.dataframe(info_df, use_container_width=True)
    except Exception:
        st.warning(
            "Sorry, it seems that we cannot fetch this company’s information right now. "
            "Make sure the name of the company you are searching for is entered correctly "
            "and that the company also exists."
        )
        st.stop()

    # 2) Company Profile
    st.subheader("💼 2. Company Profile & Financial Metrics")
    ticker = lookup_ticker(company)
    if not ticker:
        st.warning(
            "Sorry, we can’t pull the company’s profile or financial details right now. "
            "It also seems like this company is not traded publicly and thus we cannot provide a stock ticker."
        )
        profile = {}
    else:
        st.success(f"Ticker symbol: {ticker}")
        try:
            profile = get_company_profile(ticker)
        except Exception:
            st.warning(
                "Sorry, we can’t pull the company’s profile or financial details right now. "
                "We’re working to expand our coverage—please check back soon! "
                "In the meantime, feel free to use the ticker symbol shown above to look up this company’s information on any financial website."
            )
            profile = {}

    if profile:
        desc = profile.pop("description", None)
        clean = {k: v for k, v in profile.items() if v not in (None, "", " ")}
        if desc:
            st.markdown(f"**📄 Description:** {desc}")
        if clean:
            prof_df = pd.DataFrame(clean.items(), columns=["Field","Value"])
            st.table(prof_df)

    # 3) Interview Prep Guide
    st.subheader("📄 3. Interview Prep Guide")
    try:
        guide = generate_interview_prep(company, display_role)
        st.session_state.prep_guide = guide
        st.markdown(guide)
        st.download_button(
            "📥 Download Prep Guide",
            guide,
            file_name=f"{company}_prep.txt",
            mime="text/plain"
        )
    except Exception as e:
        st.error("Failed to generate the prep guide.")
        st.exception(e)

# 4) Follow-up & Practice
if st.session_state.prep_guide:
    st.subheader("❓ 4. Ask a Follow-up Question")
    question = st.text_input("Your question", "")
    if st.button("Ask"):
        if not question.strip():
            st.warning("Please enter a follow-up question.")
        else:
            try:
                answer = answer_followup_question(st.session_state.prep_guide, question)
                st.markdown(f"**💬 Answer:** {answer}")
            except Exception as e:
                st.error("Failed to generate answer.")
                st.exception(e)

    # 5) Mock Interview Quiz
    st.markdown("---")
    st.markdown("### 🧠 5. Want to test yourself?")
    if st.button("Generate Sample Question"):
        try:
            quiz_prompt = f"""Create a challenging interview question for a {display_role} role based on this guide:

{st.session_state.prep_guide}"""
            quiz_resp = co.chat(
                model="command-r-plus",
                messages=[{"role":"user","content":quiz_prompt}],
                temperature=0.7
            )
            st.markdown(f"**Practice Question:** {quiz_resp.message.content[0].text.strip()}")
        except Exception as e:
            st.error("Failed to generate practice question.")
            st.exception(e)
