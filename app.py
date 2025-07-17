import os
import time

import gradio as gr
from firecrawl import FirecrawlApp
from groq import Groq

# Initialize API clients
firecrawl_client = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])


def search_flights(origin: str, destination: str, limit: int = 5):
    query = f"Find flights from {origin} to {destination}"
    results = firecrawl_client.search(
        query,
        limit=limit,
        tbs="qdr:w",  # results from the past week
        timeout=30000,
    )
    flights = []
    for item in results.data:
        flights.append(
            {
                "title": item["title"],
                "url": item["url"],
                "description": item["description"],
            }
        )
    return flights


def summarize_flights(flights):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": f"""
Summarize these flight search results in clear, visually appealing markdown. For each flight, use the following format:

---
## [Airline Name]

- **Route:** [Origin] → [Destination]
- **Price:** [Price or 'Not quoted']
- **Key Points:** [Key features or restrictions]
- **Book:** [Link with airline name](URL)

---

{flights}
""",
        },
    ]
    resp = groq_client.chat.completions.create(
        model="moonshotai/kimi-k2-instruct",
        messages=messages,
        max_tokens=512,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def scrape_flight_details(url: str):
    try:
        scrape_result = firecrawl_client.scrape_url(
            url=url,
            formats=["markdown"],
            max_age=3600000,
        )
        content = getattr(scrape_result, "markdown", None)
        if not content:
            return "No markdown content returned from scrape."
        content = content[:1500]  # limit for display
        # Summarize scraped content
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"Summarize the key details from this flight booking page for a traveler.\n{content}",
            },
        ]
        resp = groq_client.chat.completions.create(
            model="moonshotai/kimi-k2-instruct",
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        return f"Error scraping details: {type(e).__name__}: {e}\nTraceback:\n{tb}"


def travel_deal_finder(origin, destination, deep_search):
    flights = search_flights(origin, destination)
    summary = summarize_flights(str(flights))
    scraped_details = "No results to scrape."
    if deep_search:
        for flight in flights:
            url = flight["url"]
            details = scrape_flight_details(url)
            if not details.startswith("Error scraping details"):
                scraped_details = details
                break
    else:
        scraped_details = (
            "Deep Search is disabled. Only summarized search results are shown above."
        )
    return summary, scraped_details


def travel_deal_finder_with_time(origin, destination, deep_search):
    start = time.time()
    summary, scraped_details = travel_deal_finder(origin, destination, deep_search)
    elapsed = time.time() - start
    return (
        summary,
        scraped_details,
        gr.update(interactive=True),  # Re-enable button
        f"⏱️ Processing time: {elapsed:.2f} seconds",
    )


def main():
    with gr.Blocks() as demo:
        gr.Markdown(
            "# Travel Deal Finder ✈️\nEnter your origin and destination to find and summarize the best flight deals!"
        )
        with gr.Row():
            origin = gr.Textbox(label="Origin City", value="New York")
            destination = gr.Textbox(label="Destination City", value="Tokyo")
        deep_search = gr.Checkbox(
            label="Deep Search (scrape top results for details)", value=False
        )
        search_btn = gr.Button("Find Deals")
        summary_output = gr.Markdown(label="Flight Deals Summary")
        scrape_output = gr.Markdown(label="Top Result Details (Scraped)")
        time_output = gr.Markdown(label="Processing Time")

        def on_search(o, d, ds):
            # Disable button immediately
            return (
                gr.update(),  # summary_output placeholder
                gr.update(),  # scrape_output placeholder
                gr.update(interactive=False),  # Disable button
                "Processing...",  # Show processing message
            )

        search_btn.click(
            on_search,
            inputs=[origin, destination, deep_search],
            outputs=[summary_output, scrape_output, search_btn, time_output],
            queue=False,
        )

        search_btn.click(
            travel_deal_finder_with_time,
            inputs=[origin, destination, deep_search],
            outputs=[summary_output, scrape_output, search_btn, time_output],
            queue=True,
        )

    demo.launch()


if __name__ == "__main__":
    main()
