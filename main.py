import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from flask import Flask, Response, request, jsonify
from google.cloud import storage

from api import fetch_dutchie_data, fetch_trulieve_data, fetch_zenleaf_data
from normalizers import normalize_dutchie_product, normalize_trulieve_product, normalize_zenleaf_product
from engine import parse_all_promos, generate_best_cart

# Load environment variables
load_dotenv()

# Initialize Flask Web Server
app = Flask(__name__)

# ==========================================
# Main Execution / Controller
# ==========================================
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
    
    # 6. Parse promo text into structured rules for the engine
    for product in master_inventory:
        product['parsed_rules'] = parse_all_promos(product.get('promos', []))

    # 7. Run Python Rule Engine
    if master_inventory:
        best_cart = generate_best_cart(master_inventory)
        
        if not best_cart:
            return "No combinations found under $27 per cart today.", "No qualifying deals found under $27 today."
            
        # Format the winning cart exactly like the old Gemini Markdown format
        md_output = f"# Python Engine Recommendation\n\n"
        md_output += f"**Recommended Dispensary:** {best_cart.get('recommended_dispensary', 'N/A')}\n"
        md_output += f"**Total Estimated Cost:** ${best_cart.get('total_estimated_cost', 0):.2f} (${best_cart.get('effective_unit_price', 0):.2f}/ea)\n"
        md_output += f"**Math Check:** {best_cart.get('math_scratchpad', 'N/A')}\n\n"
        md_output += f"### Overall Justification\n{best_cart.get('overall_justification', 'N/A')}\n\n"
        md_output += f"### Items to Buy\n"
        
        for item in best_cart.get('items_to_buy', []):
            terps_str = ", ".join([f"{k} {v}%" for k, v in item.get('terpenes', {}).items()]) or "Unknown"
            md_output += f"- **{item.get('quantity', 1)}x {item.get('product_name', 'Unknown')}** ({item.get('weight', 'N/A')})\n"
            md_output += f"  - **Unit Price:** ${item.get('unit_price', 0):.2f}\n"
            md_output += f"  - **Discount:** {item.get('applied_discount', 'None')}\n"
            md_output += f"  - **Terpenes:** {terps_str}\n"
            md_output += f"  - **Justification:** {item.get('justification', 'N/A')}\n"
            
        print("\n" + "="*60 + "\n")
        print(md_output)
        print("="*60 + "\n")
        
        # Save locally for /list
        with open("/tmp/latest_report.md", "w", encoding="utf-8") as f:
            f.write(md_output)
            
        # Save to Google Cloud Storage if configured
        bucket_name = os.environ.get("GCS_BUCKET_NAME")
        if bucket_name:
            try:
                storage_client = storage.Client()
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob("latest_report.md")
                blob.upload_from_string(md_output, content_type="text/markdown")
            except Exception as e:
                print(f"[!] Failed to save to GCS bucket: {e}")

        # Also dump a copy to the local project folder for easy reading during development
        try:
            with open("latest_report.md", "w", encoding="utf-8") as f:
                f.write(md_output)
        except Exception:
            pass # Safely ignore on Cloud Run since its file system is read-only
            
        speech_text = f"I recommend going to {best_cart['recommended_dispensary']}. The total estimated cost for your cart is ${best_cart['total_estimated_cost']:.2f}."
        return speech_text, md_output
            
    return f"No deals found. Master inventory contained {len(master_inventory)} items.", "No deals found."

@app.route("/", methods=["GET"])
def health_check():
    return "MMJ Deals Finder is awake and running!", 200

@app.route("/run-deals", methods=["GET", "POST"])
def run_deals_webhook():
    print("Webhook triggered by Siri/Cloud!")
    speech_text, full_report = generate_deals_report()
    
    # Dynamically grab the server URL so it works locally AND in the cloud
    list_url = f"{request.host_url.rstrip('/')}/list"
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
    # 3. Open your browser to http://127.0.0.1:5001/
    print("Starting local Flask server for testing at http://127.0.0.1:5001")
    app.run(debug=True, port=5001)
