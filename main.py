import streamlit as st
import asyncio
import google.generativeai as genai
from scrape import scrape_all_pages
import sys
from dotenv import load_dotenv
import os

load_dotenv()

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# config gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Streamlit UI
st.set_page_config(page_title="Cars.com Scraper & LLM Assistant", layout="wide")
st.title("🚗 Cars.com Scraper + LLM Q&A")

# Scraping form
with st.form("scraper_form"):
    url = st.text_input("Enter Cars.com Search URL",
                        "https://www.cars.com/shopping/results/?list_price_max=&makes[]=&maximum_distance=all&models[]=&page=1&stock_type=all&zip=#vehicle-card-e4916b0d-7dc9-4e2e-ac6a-3de1b1014bb1")
    max_pages = st.number_input("Number of pages to scrape", min_value=1, max_value=100, value=3)
    submitted = st.form_submit_button("Scrape & Analyze")

# Scrape and store in session
if submitted:
    with st.spinner("Scraping and parsing listings..."):
        df = asyncio.run(scrape_all_pages(url, max_pages))
        st.session_state["cars_df"] = df
        
        # Now we just pass the CSV data in a user message
        st.session_state["chat"] = model.start_chat(history=[
            {
                "role": "user",
                "parts": [
                    "You are a helpful assistant analyzing used car listings from Cars.com. "
                    "The user will ask questions about the following CSV data:\n\n"
                    + df.to_csv(index=False)
                ]
            }
        ])
        st.success("✅ Scraping complete! You can now chat with the LLM.")
        st.dataframe(df)

# Chat section
st.markdown("### 💬 Chat with Gemini About the Listings")
if "chat" in st.session_state:
    user_input = st.chat_input("Ask about the listings (e.g. 'Find SUVs under $30k')")

    if user_input:
        with st.spinner("Thinking..."):
            response = st.session_state["chat"].send_message(user_input)
            st.chat_message("user").write(user_input)
            st.chat_message("assistant").write(response.text.strip())

# Warn if trying to chat without scraping
else:
    st.info("👆 First scrape Cars.com listings above before chatting.")
