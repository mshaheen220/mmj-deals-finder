# 🌿 MMJ Deals Finder & AI Personal Shopper

An intelligent Python agent that aggregates medical marijuana dispensary menus and uses Google Gemini to act as your personal cannabis shopper. Instead of using slow headless browsers, this script directly reverse-engineers and fetches data from dispensary APIs (Dutchie, Trulieve, Sweed POS) to gather real-time inventory, pricing, and promotional data.

It then feeds the aggregated inventory into Google Gemini, which acts as a "sommelier" to build the perfect shopping cart based on your specific budget, terpene preferences, and desired strains.

## ✨ Features

- **Lightning Fast API Scraping**: Bypasses Cloudflare and Datadome WAFs using `curl_cffi` to spoof Chrome TLS fingerprints.
- **Multi-Platform Support**: Natively extracts data from Dutchie GraphQL, Trulieve REST API, and Zen Leaf (Sweed POS) GraphQL.
- **AI-Powered Recommendations**: Uses Google Gemini to analyze hundreds of products and output a structured Pydantic schema of the best deals.
- **Smart Discount Calculation**: The AI reads raw promotional text (e.g., "4 for $99") and automatically factors quantity discounts into your total cost.
- **Markdown Reports**: Automatically generates a timestamped, highly readable Markdown file with your custom shopping list and the AI's justification for picking it.

## 🏢 Supported Dispensaries
Currently configured to pull 1g Indica Vape Cartridges from:
- Liberty Cannabis (Cranberry)
- Trulieve (Cranberry)
- Trulieve (Zelienople)
- Ascend (Cranberry)
- Zen Leaf (Cranberry)

## ⚙️ Prerequisites

- Python 3.9+
- A Google Gemini API Key (Available for free at Google AI Studio)

## 🚀 Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd ~/Documents/dev/mmj-deals-finder
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install the required dependencies:**
   ```bash
   pip install curl_cffi google-genai pydantic python-dotenv
   ```

4. **Set up your environment variables:**
   Create a `.env` file in the root directory and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```

## 🛒 Usage

Before running the script, you can adjust your personal preferences by editing the `my_preferences` variable inside the `main()` function in `main.py`. Tell the AI your budget, preferred terpenes, strains, or product types!

Run the script:
```bash
python main.py
```

### What happens next?
1. The script rapidly fetches the live inventory from all configured dispensaries.
2. It saves a raw dump of the aggregated data to `debug_inventory.json`.
3. It sends the inventory and your preferences to Gemini.
4. Gemini returns a fully optimized shopping cart.
5. The script prints the results to your terminal and saves a beautifully formatted file (e.g., `shopping_recommendation_20231024_153022.md`) in your project folder.

## 🤖 Automation Ideas (What's Next?)
Because this is a standard Python script, you can easily wire it up to your daily life:
- **Daily Morning Routine**: Use a cron job or macOS Automator to run this at 7:00 AM every day and email you the resulting Markdown file.
- **Voice Activation**: Tie the script to a macOS Shortcut so you can say *"Hey Siri, find dispensary deals"* to execute it.
- **Push Notifications**: Add a few lines of code to send the final `md_output` directly to a private Discord channel, Slack, or as an SMS via Twilio.
- **Web Dashboard**: Wrap the script in a lightweight framework like Streamlit to create a personal website where you can adjust preferences via sliders and push a button to run it.

## 🛠️ Tech Stack
- **`curl_cffi`**: For stealthy HTTP requests that bypass strict bot protection.
- **`google-genai`**: For interacting with the Gemini 1.5/2.5 Flash models.
- **`pydantic`**: For enforcing strict JSON schemas on the LLM output.
- **`urllib.parse` & `json`**: For intercepting and modifying complex GraphQL payloads.

## ⚠️ Disclaimer
This script is for educational purposes and personal use. Dispensary APIs change frequently, so payloads and endpoint URLs may need to be updated periodically if the script returns 0 products.