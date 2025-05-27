
import streamlit as st
import feedparser
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz
import pandas as pd
from io import BytesIO
from geopy.geocoders import Nominatim
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="EpiWatch", layout="wide")
st.title("🦠 EpiWatch")

email_sender = "ghadisubahi@gmail.com"
app_password = "munu pxkv vxhb bssk"
email_receiver = "ghadisubahi@gmail.com"

geolocator = Nominatim(user_agent="epiwatch")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("📅 From date", datetime.now().date())
with col2:
    end_date = st.date_input("📅 To date", datetime.now().date())

default_keywords = [
    "cholera", "anthrax", "meningitis", "avian flu", "covid-19", "mers",
    "dengue", "ebola", "plague", "yellow fever", "measles", "influenza",
    "hajj", "umrah", "pilgrimage", "mecca", "madinah", "mass gathering",
    "infectious disease in pilgrims", "public health hajj"
]
keywords = st.multiselect("🦠 Select diseases/keywords:", default_keywords, default=default_keywords)
search = st.button("🔍 Search")
enable_email_alert = st.checkbox("📬 Send email if alerts found")

rss_sources = {
    "WHO": "https://www.who.int/feeds/entity/csr/don/en/rss.xml",
    "CDC": "https://tools.cdc.gov/api/v2/resources/media/403372.rss",
    "BBC": "http://feeds.bbci.co.uk/news/health/rss.xml",
    "Reuters": "http://feeds.reuters.com/reuters/healthNews",
    "Google Health": "https://news.google.com/rss/search?q=health+disease+outbreak",
    "GPHIN": "https://www.phac-aspc.gc.ca/rss/gphin.xml"
}

def fetch_feed(url):
    return feedparser.parse(url)

def fetch_sabq_articles(keywords):
    sabq_url = "https://sabq.org/health"
    results = []
    try:
        response = requests.get(sabq_url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("a", href=True)

        for a in articles:
            title = a.get_text(strip=True)
            link = a["href"]
            full_text = title.lower()

            for kw in keywords:
                if kw.lower() in full_text:
                    results.append({
                        "source": "Sabq News",
                        "title": title,
                        "keyword": kw,
                        "date": str(datetime.today().date()),
                        "country": "Saudi Arabia",
                        "link": f"https://sabq.org{link}" if link.startswith("/") else link
                    })
    except Exception as e:
        print("Sabq error:", e)
    return results

def keyword_found(text, keywords):
    text = text.lower()
    return [kw for kw in keywords if kw.lower() in text]

def is_within_range(date_str, start_date, end_date):
    try:
        pub_date = datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S")
        pub_date = pub_date.replace(tzinfo=pytz.UTC).date()
        return start_date <= pub_date <= end_date
    except:
        return False

def detect_country(entry):
    try:
        full_text = f"{entry.title} {entry.get('summary', '')}"
        location = geolocator.geocode(full_text, timeout=10)
        if location and location.address:
            return location.address.split(",")[-1].strip()
    except:
        pass
    return "Unknown"

def send_email_alert(alerts):
    if not alerts:
        return
    subject = "🚨 EpiWatch: Disease Alerts"
    body = "\n\n".join([f"{a['keyword']} - {a['title']} ({a['source']})\n{a['link']}" for a in alerts])
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = email_sender
    msg["To"] = email_receiver
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_sender, app_password)
        server.send_message(msg)

if search:
    alerts = []

    # Get alerts from RSS sources
    for source, url in rss_sources.items():
        feed = fetch_feed(url)
        for entry in feed.entries:
            text = f"{entry.title} {entry.get('summary', '')}"
            pub_date = entry.get("published", "")
            matched_keywords = keyword_found(text, keywords)
            if matched_keywords and is_within_range(pub_date, start_date, end_date):
                country = detect_country(entry)
                for kw in matched_keywords:
                    alerts.append({
                        "source": source,
                        "title": entry.title,
                        "keyword": kw,
                        "date": pub_date,
                        "country": country,
                        "link": entry.link
                    })

    # Append Sabq results
    sabq_alerts = fetch_sabq_articles(keywords)
    alerts.extend(sabq_alerts)

    if alerts:
        df = pd.DataFrame(alerts)
        st.success(f"✅ Found {len(df)} alerts.")

        st.header("📊 Dashboard Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Alerts", len(df))
        with col2:
            top_disease = df["keyword"].value_counts().idxmax()
            st.metric("Top Disease", f"{top_disease}")
        with col3:
            top_source = df["source"].value_counts().idxmax()
            st.metric("Top Source", f"{top_source}")

        st.subheader("📋 Alert Details")
        for _, row in df.iterrows():
            st.markdown(f"🔗 **[{row['title']}]({row['link']})**")
            st.markdown(f"📅 {row['date']} | 🦠 {row['keyword']} | 🌐 {row['source']} | 🗺️ {row['country']}")
            st.markdown("---")

        st.subheader("📤 Export Alerts")
        excel_output = BytesIO()
        df.to_excel(excel_output, index=False, engine="openpyxl")
        st.download_button("📁 Download Excel", data=excel_output.getvalue(), file_name="epiwatch_alerts.xlsx")

        if enable_email_alert:
            send_email_alert(alerts)
    else:
        st.warning("📭 No alerts found.")
