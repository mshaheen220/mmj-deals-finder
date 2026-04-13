# 🌿 MMJ Deals Finder & AI Personal Shopper

An intelligent Python agent that aggregates medical marijuana dispensary menus and uses Google Gemini to act as your personal cannabis shopper. Instead of using slow headless browsers, this script directly reverse-engineers and fetches data from dispensary APIs (Dutchie, Trulieve, Sweed POS) to gather real-time inventory, pricing, and promotional data.

It is built as a **Flask web server** containerized with **Docker** and deployed on **Google Cloud Run**. It then feeds the aggregated inventory into Google Gemini, which acts as a "sommelier" to build the perfect shopping cart based on your specific budget, terpene preferences, and desired strains. This architecture allows you to trigger the AI personal shopper from anywhere using an **iOS Siri Shortcut**!

## ✨ Features

- **Lightning Fast API Scraping**: Bypasses Cloudflare and Datadome WAFs using `curl_cffi` to spoof Chrome TLS fingerprints.
- **Multi-Platform Support**: Natively extracts data from Dutchie GraphQL, Trulieve REST API, and Zen Leaf (Sweed POS) GraphQL.
- **AI-Powered Recommendations**: Uses Google Gemini to analyze hundreds of products and output a structured Pydantic schema of the best deals.
- **Smart Discount Calculation**: The AI reads raw promotional text (e.g., "4 for $99") and automatically factors quantity discounts into your total cost.
- **Siri & iOS Shortcut Integration**: Returns short, conversational audio summaries for Siri, along with a clickable link to view your full cart.
- **Cloud Storage**: Automatically generates a timestamped, highly readable Markdown file wrapped in beautiful HTML, backed by Google Cloud Storage.

## 🏢 Supported Dispensaries
Currently configured to pull 1g Indica Vape Cartridges from:
- Liberty Cannabis (Cranberry)
- Trulieve (Cranberry)
- Trulieve (Zelienople)
- Ascend (Cranberry)
- Zen Leaf (Cranberry)

## ⚙️ Deployment (Google Cloud Run)

This project is designed to be deployed as a serverless container on Google Cloud Run.

1. **Install the Google Cloud CLI (`gcloud`)** and authenticate your account.
2. **Deploy to Cloud Run** directly from your terminal:
   ```bash
   gcloud run deploy mmj-deals-finder --source . \
     --region us-central1 --allow-unauthenticated \
     --set-env-vars GEMINI_API_KEY="your_actual_api_key_here"
   ```

3. **Optional (Cloud Storage):** If you want to permanently save your shopping lists, create a Google Cloud Storage bucket and add `--set-env-vars GCS_BUCKET_NAME="your_bucket_name"` to your deployment command.

4. **Continuous Deployment:** You can also link your GitHub repository directly in the Google Cloud Run console to auto-deploy every time you push to the `main` branch.

## 🛒 Usage

Adjust your personal preferences by editing the `my_preferences` variable inside the `main.py` file before deploying.

Once deployed, your Cloud Run service exposes two endpoints:

### `/run-deals` (Webhook)
Create an iOS Shortcut with the following actions:
1. **Get contents of** `https://your-cloud-run-url.a.run.app/run-deals`
2. **Get Dictionary from Input** (Contents of URL)
3. **Speak Text** -> `speech` value from Dictionary
4. **Show Alert** -> `display` value from Dictionary
5. **Open URLs** -> `url` value from Dictionary

### `/list` (Webpage)
Navigate to `https://your-cloud-run-url.a.run.app/list` in your browser to view your most recent shopping list, beautifully formatted using Pico.css and Marked.js.

## 🛠️ Tech Stack
- **`curl_cffi`**: For stealthy HTTP requests that bypass strict bot protection.
- **`google-genai`**: For interacting with the Gemini 1.5/2.5 Flash models.
- **`Flask` & `Gunicorn`**: For the lightweight web server and production WSGI handling.
- **`Docker`**: Containerization for seamless Google Cloud deployment.
- **`pydantic`**: For enforcing strict JSON schemas on the LLM output.
- **`google-cloud-storage`**: For stateless file persistence.

## ⚠️ Disclaimer
This script is for educational purposes and personal use. Dispensary APIs change frequently, so payloads and endpoint URLs may need to be updated periodically if the script returns 0 products.