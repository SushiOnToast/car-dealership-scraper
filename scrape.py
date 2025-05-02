import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
import google.generativeai as genai
import json
import re
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Throttling
semaphore = asyncio.Semaphore(1)
REQUEST_DELAY = 4  # seconds between requests
BATCH_SIZE = 3     # listings per prompt

def clean_markdown(markdown):
    # Remove image markdown
    cleaned_markdown = re.sub(r'!\[.*?\]\(.*?\)', '', markdown)

    # Define the divider based on the pattern
    divider = "Call  Check availability Check availability"

    # Split the markdown by the divider
    listings = cleaned_markdown.split(divider)

    # Clean up any extra new lines or spaces from each listing
    listings = [re.sub(r'\n+', '\n', listing).strip() for listing in listings]

    # Filter out any empty listings (if there are any after the split)
    listings = [listing for listing in listings if listing.strip()]

    return listings

# Gemini extractor (batch)
async def extract_listings_batch(cards_markdown):
    formatted_cards = "\n\n---\n\n".join(cards_markdown)
    prompt = f"""
You're given multiple car listings from a Cars.com search result page in markdown format.

Each listing is separated by "---".

Extract each listing as a JSON object with the following fields:
- condition (Used/New)
- make_and_model
- year
- price
- mileage
- dealer_name
- location

Return all listings as a JSON array.

Markdown:
{formatted_cards}
"""

    async with semaphore:
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, model.generate_content, prompt)
            await asyncio.sleep(REQUEST_DELAY)

            content = response.text.strip()
            if content.startswith("```json"):
                content = content.strip("```json").strip("```").strip()
            return json.loads(content)
        except Exception as e:
            print("❌ Failed to parse batch:")
            print(formatted_cards)
            print("Error:", e)
            return []

# Crawler logic
async def scrape_all_pages(url, max_pages):
    if "page=" in url:
        base_url = re.sub(r'page=\d+', 'page={}', url)
    else:
        # If no page= param exists, append it with proper format
        separator = '&' if '?' in url else '?'
        base_url = f"{url}{separator}page={{}}"

    all_listings = []

    config = CrawlerRunConfig(
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
        stream=False,
        target_elements=["div.vehicle-card-main"],
    )

    async with AsyncWebCrawler() as crawler:
        for page in range(1, max_pages + 1):
            url = base_url.format(page)
            print(f"\n🔎 Crawling page {page}: {url}")
            result = await crawler.arun(url, config=config)
            markdown = result.markdown

            # Clean the markdown by removing image markdown and split it into listings
            listings = clean_markdown(markdown)

            # Process the listings
            parsed_listings = await extract_listings_batch(listings)
            all_listings.extend(parsed_listings)

    # Save the listings to a CSV file
    if all_listings:
        df = pd.DataFrame(all_listings)
        df.to_csv("data.csv", index=False)
    else:
        print("\n⚠️ No listings extracted.")

    return df


