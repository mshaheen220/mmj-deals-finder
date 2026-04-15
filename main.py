import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from flask import Flask, Response, request, jsonify
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
from google.cloud import storage

from models import ShoppingTrip
from api import fetch_dutchie_data, fetch_trulieve_data, fetch_zenleaf_data
from normalizers import normalize_dutchie_product, normalize_trulieve_product, normalize_zenleaf_product

# Load environment variables
load_dotenv()

# Initialize Flask Web Server
app = Flask(__name__)

# ==========================================
# Main Execution / Controller
# ==========================================
def sanitize_product_data(item):
    """Recursively removes empty values and heavy junk fields (like images/URLs) to save AI tokens."""
    if isinstance(item, list):
        return [sanitize_product_data(i) for i in item if i]
    elif isinstance(item, dict):
        cleaned = {}
        # Blacklist of noisy keys that don't help the AI pick products
        junk_keys = {'image', 'images', 'imageurl', 'image_url', 'picture', 'assets', 'media', 'url', 'slug', 'createdat', 'updatedat', 'reviews', 'icon'}
        for k, v in item.items():
            if k.lower() in junk_keys:
                continue
            if v in (None, "", [], {}):
                continue
            if isinstance(v, str) and v.startswith('http') and len(v) > 15:
                continue
            cleaned_v = sanitize_product_data(v)
            if cleaned_v not in (None, "", [], {}):
                cleaned[k] = cleaned_v
        return cleaned
    return item

def generate_deals_report():
    # 1. Define Stores to Check
    dutchie_id = "60523818a6b5d500e0fb2e31"  # Liberty Cranberry
    trulieve_cranberry_id = "87"           # Trulieve Cranberry
    trulieve_zelienople_id = "103"         # Trulieve Zelienople
    ascend_id = "66fef50576b5d1b3703a1890"   # Ascend
    zenleaf_id = "145"                     # Zen Leaf Cranberry
    
    master_inventory = []
    
    # 2. Fetch Dutchie Data & normalize
    dutchie_raw = fetch_dutchie_data(dutchie_id)
    try:
        dutchie_json = json.loads(dutchie_raw)
        if "errors" in dutchie_json:
            print(f"[!] Dutchie API Errors (Liberty): {json.dumps(dutchie_json['errors'])}")
        if "data" in dutchie_json and isinstance(dutchie_json["data"], dict) and "filteredProducts" in dutchie_json["data"]:
            dutchie_products = dutchie_json["data"]["filteredProducts"].get("products", [])
            for p in dutchie_products:
                master_inventory.append(normalize_dutchie_product(p, "Liberty Cannabis - Cranberry Township"))
    except Exception as e:
        print(f"[!] Failed to parse Dutchie inventory: {e}")

    # 3. Fetch Trulieve Data (Cranberry) & normalize
    trulieve_cranberry_products = fetch_trulieve_data(trulieve_cranberry_id)
    for p in trulieve_cranberry_products:
        master_inventory.append(normalize_trulieve_product(p, "Trulieve - Cranberry"))

    # 3b. Fetch Trulieve Data (Zelienople) & normalize
    trulieve_zelienople_products = fetch_trulieve_data(trulieve_zelienople_id)
    for p in trulieve_zelienople_products:
        master_inventory.append(normalize_trulieve_product(p, "Trulieve - Zelienople"))
    
    # 4. Fetch Ascend Data using the Dutchie API & normalize
    ascend_raw = fetch_dutchie_data(ascend_id)
    try:
        ascend_json = json.loads(ascend_raw)
        if "errors" in ascend_json:
            print(f"[!] Dutchie API Errors (Ascend): {json.dumps(ascend_json['errors'])}")
        if "data" in ascend_json and isinstance(ascend_json["data"], dict) and "filteredProducts" in ascend_json["data"]:
            ascend_products = ascend_json["data"]["filteredProducts"].get("products", [])
            for p in ascend_products:
                master_inventory.append(normalize_dutchie_product(p, "Ascend"))
    except Exception as e:
        print(f"[!] Failed to parse Ascend inventory: {e}")
        
    # 5. Fetch Zen Leaf Data & normalize
    zenleaf_products = fetch_zenleaf_data(zenleaf_id)
    for p in zenleaf_products:
        norm_p = normalize_zenleaf_product(p, "Zen Leaf - Cranberry")
        # Sweed POS API returns all sizes, so we must filter for 1g carts in Python
        if norm_p["weight"] in ["1g", "1.0g", "1000mg"]:
            master_inventory.append(norm_p)

    print(f"\n[+] Aggregated {len(master_inventory)} total products across all stores.")
    
    # 6. Define your Personal Preferences!
    my_preferences = (
        "Target: 1g Indica vape cartridges, >70% THC.\n"
        "Preferences: Prioritize Myrcene and Caryophyllene terpenes. If specific terpenes are missing, prioritize high 'Pain Relief' and 'Relaxed' effects. If both are missing, prioritize highest THC%.\n"
        "Pricing Logic: The lowest JSON price is final. DO NOT apply percentage discounts (like '40% off')—they are already baked into the JSON price. Only recalculate for flat-rate volume deals (e.g., '4 for $99').\n"
        "Quantity Logic: If the deal is average (close to $27), buy 4 carts. If the deal is great (well below $27), buy up to 10 carts. You can recommend anywhere between 4 and 10 carts depending on how good the price is.\n"
        "Hard Limits: Max 10 carts. The FINAL effective price (after any valid volume bundles are applied) MUST be $26.99 or less per unit. If the effective unit price remains $27.00 or higher, REJECT IT. Do not alter or fake prices to make them fit. No total budget cap.\n"
        "Goal: Select the single store with the best overall value."
    )
    
    # 7. Sanitize inventory to strip images, nulls, and empty values, saving thousands of tokens
    sanitized_inventory = sanitize_product_data(master_inventory)
    
    # 8. Get AI Recommendation
    if sanitized_inventory:
        # ---  DEBUGGING: DUMP NORMALIZED DATA AND SKIP GEMINI ---
        print("\n[DEBUG] Skipping Gemini call. Saving normalized data for inspection.")
        
        with open("normalized_inventory.json", "w", encoding="utf-8") as f:
            json.dump(sanitized_inventory, f, indent=2)
        print("💾 Normalized inventory saved locally to 'normalized_inventory.json'")

        debug_message = f"DEBUG MODE: Skipped Gemini. Found {len(sanitized_inventory)} normalized products. Check local 'normalized_inventory.json'."
        return debug_message, debug_message
            
    return f"No deals found. Master inventory contained {len(master_inventory)} items.", "No deals found."

@app.route("/", methods=["GET"])
def health_check():
    return "MMJ Deals Finder is awake and running!", 200

@app.route("/run-deals", methods=["GET", "POST"])
def run_deals_webhook():
    print("Webhook triggered by Siri/Cloud!")
    speech_text, full_report = generate_deals_report()
    
    # Hardcoded Cloud Run URL for the list page
    list_url = "https://mmj-deals-finder-9234350374.us-central1.run.app/list"
    display_text = f"{speech_text}\n\n# [🔗 Tap here to view your full shopping list]({list_url})"
    
    # Return JSON so the iOS Shortcut can separate spoken text from displayed text
    return jsonify({"speech": speech_text, "display": display_text, "url": list_url})

@app.route("/list", methods=["GET"])
def view_latest_list():
    # Serve the full markdown file wrapped in beautiful, mobile-friendly HTML
    try:
        bucket_name = os.environ.get("GCS_BUCKET_NAME")
        if bucket_name:
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob("latest_report.md")
            if not blob.exists():
                raise FileNotFoundError
                
            report = blob.download_as_text()
            blob.reload() # Fetch the latest metadata (like upload time)
            processed_time = blob.updated.astimezone(ZoneInfo("America/New_York")).strftime('%b %d, %Y at %I:%M %p')
        else:
            file_path = "/tmp/latest_report.md"
            with open(file_path, "r", encoding="utf-8") as f:
                report = f.read()
                
            # Get the file modification time for the timestamp
            mtime = os.path.getmtime(file_path)
            processed_time = datetime.fromtimestamp(mtime, tz=ZoneInfo("America/New_York")).strftime('%b %d, %Y at %I:%M %p')
            
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>MMJ Personal Shopper</title>
            <!-- Pico.css for beautiful, dark-mode ready styling -->
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
            <!-- Marked.js to convert Markdown to HTML -->
            <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        </head>
        <body>
            <main class="container" id="content">
                <div aria-busy="true">Loading recommendations...</div>
            </main>
            <footer class="container">
                <hr>
                <small style="color: var(--pico-muted-color);"><i>Report processed at: {processed_time}</i></small>
            </footer>
            <script>
                const markdownText = {json.dumps(report)};
                document.getElementById('content').innerHTML = marked.parse(markdownText);
            </script>
        </body>
        </html>
        """
        return Response(html_content, mimetype="text/html")
    except Exception:
        return Response("<main class='container'><h1>No report found.</h1><p>Ask Siri to find deals first!</p></main>", mimetype="text/html")

if __name__ == "__main__":
    # If running locally in the terminal, just print the report directly
    # To run the web server locally for testing:
    # 1. Make sure your venv is active: source venv/bin/activate
    # 2. Run this file: python main.py
    # 3. Open your browser to http://127.0.0.1:5000/
    print("Starting local Flask server for testing at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
