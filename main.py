import json
import os
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from curl_cffi import requests
from pydantic import BaseModel, Field
from flask import Flask, Response, request, jsonify
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

# Load environment variables
load_dotenv()

# Initialize Flask Web Server
app = Flask(__name__)

# ==========================================
# 1. Define the Pydantic Schema
# ==========================================
class RecommendedItem(BaseModel):
    product_name: str = Field(description="Name of the cannabis product")
    unit_price: float = Field(description="Effective price per single unit AFTER applying any quantity discounts")
    quantity: int = Field(description="Number of units to purchase of this specific product")
    applied_discount: str = Field(description="Description of any quantity discount or special applied (e.g., '2 for $50', 'None')")
    weight: str = Field(description="Weight of the product (e.g., 1g)")
    terpenes: str = Field(description="Notable terpenes if listed, otherwise 'Unknown'")
    justification: str = Field(description="Why this specific product was chosen based on user preferences")

class ShoppingTrip(BaseModel):
    recommended_dispensary: str = Field(description="The SINGLE dispensary chosen for this trip")
    total_estimated_cost: float = Field(description="Total cost of the recommended items")
    overall_justification: str = Field(description="Why this dispensary and basket of goods was chosen over the alternatives")
    items_to_buy: list[RecommendedItem]

# ==========================================
# 2. Direct API Fetch (No Playwright!)
# ==========================================
def fetch_dutchie_data(dispensary_id: str) -> str:
    print(f"Fetching data directly from Dutchie API for dispensary {dispensary_id}...")
    base_url = "https://dutchie.com/api-1/graphql"
    
    payload = {
        "operationName": "FilteredProducts",
        "variables": {
            "includeEnterpriseSpecials": False,
            "productsFilter": {
                "dispensaryId": dispensary_id,
                "option": "1g",
                "pricingType": "med",
                "strainTypes": ["Indica"],
                "subcategories": "cartridges",
                "Status": "Active",
                "isOnSpecial": True,
                "types": [],
                "useCache": False,
                "isDefaultSort": False,
                "sortBy": "potency",
                "sortDirection": -1,
                "bypassOnlineThresholds": False,
                "isKioskMenu": False,
                "removeProductsBelowOptionThresholds": True,
                "platformType": "ONLINE_MENU",
                "preOrderType": None
            },
            "page": 0,
            "perPage": 1000
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "98b4aaef79a84ae804b64d550f98dd64d7ba0aa6d836eb6b5d4b2ae815c95e32"
            }
        }
    }
    
    headers = {
        "Origin": "https://dutchie.com",
        "Referer": "https://dutchie.com/",
        "x-apollo-operation-name": "FilteredProducts",
        "apollo-require-preflight": "true"
    }
    
    params = {
        "operationName": "FilteredProducts",
        "variables": json.dumps(payload["variables"], separators=(',', ':')),
        "extensions": json.dumps(payload["extensions"], separators=(',', ':'))
    }
    full_url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        print(f"    [>] Making GET request to: {base_url}")
        response = requests.get(
            full_url, 
            headers=headers,
            impersonate="chrome120"
        )
        response.raise_for_status()
        print("    [+] Successfully fetched API response!")
        return response.text
    except Exception as e:
        print(f"    [!] Failed to fetch API data: {e}")
        return "[]"

# ==========================================
# 2b. Direct API Fetch (Trulieve)
# ==========================================
def fetch_trulieve_data(store_id: str) -> list:
    print(f"Fetching data directly from Trulieve API for store {store_id}...")
    all_products = []
    page = 1
    
    headers = {
        "Origin": "https://www.trulieve.com",
        "Referer": "https://www.trulieve.com/"
    }
    
    while True:
        # Use the exact working API filters to pre-filter data before sending to Gemini
        url = f"https://api.trulieve.com/api/v2/menu/{store_id}/vapes/DEFAULT?search=&weights=1g&brand=&strain_type=indica&subcategory=CARTRIDGES&cbd_max=&cbd_min=&thc_max=&thc_min=70&tags_menu=&collections=&special=&sort_by=default&page={page}"
        
        try:
            print(f"    [>] Fetching page {page}...")
            response = requests.get(url, headers=headers, impersonate="chrome120")
            response.raise_for_status()
            data = response.json()
            
            # Extract the products array from the JSON response
            products = []
            if isinstance(data, dict):
                if "products" in data and data["products"]:
                    products = data["products"]
                elif "data" in data:
                    if isinstance(data["data"], list):
                        products = data["data"]
                    elif isinstance(data["data"], dict) and "products" in data["data"]:
                        products = data["data"]["products"]
            
            if not products:
                if page == 1:
                    print(f"    [DEBUG] Raw Trulieve response: {json.dumps(data)[:500]}")
                break # Exit the loop when a page returns 0 products
                
            all_products.extend(products)
            page += 1
            
        except Exception as e:
            print(f"    [!] Failed to fetch Trulieve data on page {page}: {e}")
            break
            
    print(f"    [+] Successfully fetched {len(all_products)} total products from Trulieve!")
    return all_products

# ==========================================
# 2c. Direct API Fetch (Zen Leaf / Sweed)
# ==========================================
def fetch_zenleaf_data(store_id: str) -> list:
    if store_id == "INSERT_STORE_ID_HERE":
        print("    [!] Skipping Zen Leaf: store_id not configured yet.")
        return []
        
    print(f"Fetching data directly from Zen Leaf (Sweed) API for store {store_id}...")
    url = "https://web-ui-production.sweedpos.com/_api/proxy/Products/GetProductList"
    
    payload = {
        "filters": {"strainPrevalence":[4],"category":[712],"subcategory":[5524]},
        "page": 1,
        "pageSize": 1000,
        "sortingMethodId": 7,
        "searchTerm": "",
        "platformOs": "web",
        "sourcePage": 0
    }
    
    headers = {
        "Origin": "https://zenleafdispensaries.com",
        "Referer": "https://zenleafdispensaries.com/",
        "Content-Type": "application/json",
        "storeId": store_id
    }
    
    try:
        print(f"    [>] Making POST request to: {url}")
        response = requests.post(url, json=payload, headers=headers, impersonate="chrome120")
        response.raise_for_status()
        data = response.json()
        
        products = []
        if isinstance(data, dict):
            if "list" in data:
                products = data["list"]
            elif "items" in data:
                products = data["items"]
            elif "products" in data:
                products = data["products"]
                
            # Inject full promotional details from the root 'promos' node into each product
            root_promos = {p.get("id"): p for p in data.get("promos", [])}
            if root_promos:
                for p in products:
                    for variant in p.get("variants", []):
                        for promo in variant.get("promos", []):
                            promo_id = promo.get("id")
                            if promo_id in root_promos:
                                promo["full_name"] = root_promos[promo_id].get("name")
                                promo["full_description"] = root_promos[promo_id].get("description")
                
        print(f"    [+] Successfully fetched {len(products)} total products from Zen Leaf!")
        return products
    except Exception as e:
        print(f"    [!] Failed to fetch Zen Leaf data: {e}")
        return []

# ==========================================
# 3. Extraction Layer (Gemini 1.5 Flash)
# ==========================================
def get_shopping_recommendation(aggregated_inventory: str, user_preferences: str) -> str:
    print("Sending combined inventory to Gemini for personal shopper analysis...")
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # The System Prompt directs the model's behavior
    system_instruction = (
        "You are an expert cannabis personal shopper and sommelier. "
        "You will be provided with a JSON list of available products from MULTIPLE dispensaries. "
        "Your goal is to build the perfect shopping cart based on the user's preferences. \n\n"
        "CRITICAL RULES:\n"
        "1. You MUST pick only ONE dispensary for the entire shopping trip. The user refuses to drive to multiple stores.\n"
        "2. Optimize for the user's stated preferences (price, terpenes, strains, etc.).\n"
        "3. Provide a clear justification for why you chose the store and the specific products.\n"
        "4. If no products match the user's strict criteria, return an empty list of items, but explain why.\n"
        "5. Do NOT list the same product multiple times. Use the 'quantity' field to indicate how many of each to buy.\n"
        "6. IMPORTANT: Carefully review pricing and specials data. For many stores, the sale price (e.g., 'specialPrice' or 'promoPrice') ALREADY has the percentage discount applied. Do NOT apply a percentage discount a second time (no double-discounting). If a flat-rate quantity bundle (e.g., '4 for $99') applies, recalculate the 'unit_price' and 'total_estimated_cost' based on that bundle. Note the deal in the 'applied_discount' field."
    )
    
    # We combine the system instruction with the user's specific prompt for this run
    full_prompt = (
        f"USER PREFERENCES:\n{user_preferences}\n\n"
        f"AVAILABLE INVENTORY:\n{aggregated_inventory}"
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ShoppingTrip,
                temperature=0.2, # Slightly higher temperature allows for better reasoning/justification generation
            )
        )
        return response.text
    except ClientError as e:
        # Clean the message so it doesn't break our JSON parsing
        error_msg = str(e.message).replace('"', "'").replace('\n', ' ')
        print(f"\n[!] Gemini API Client Error: {error_msg}")
        return f'{{"error": "Client Error: {error_msg}"}}'
    except ServerError as e:
        error_msg = str(e.message).replace('"', "'").replace('\n', ' ')
        print(f"\n[!] Gemini API Server Error: {error_msg}")
        return f'{{"error": "Server Error: {error_msg}"}}'

# ==========================================
# 4. Main Execution
# ==========================================
def generate_deals_report():
    # 1. Define Stores to Check
    dutchie_id = "60523818a6b5d500e0fb2e31"  # Liberty Cranberry
    trulieve_cranberry_id = "87"           # Trulieve Cranberry
    trulieve_zelienople_id = "103"         # Trulieve Zelienople
    ascend_id = "66fef50576b5d1b3703a1890"   # Ascend
    zenleaf_id = "145"                     # Zen Leaf Cranberry
    
    master_inventory = []
    
    # 2. Fetch Dutchie Data & tag with store name
    dutchie_raw = fetch_dutchie_data(dutchie_id)
    try:
        dutchie_json = json.loads(dutchie_raw)
        if "data" in dutchie_json and "filteredProducts" in dutchie_json["data"]:
            dutchie_products = dutchie_json["data"]["filteredProducts"].get("products", [])
            for p in dutchie_products:
                p["_source_store"] = "Liberty Cannabis - Cranberry Township"
            master_inventory.extend(dutchie_products)
    except Exception:
        print("[!] Failed to parse Dutchie inventory")

    # 3. Fetch Trulieve Data (Cranberry) & tag with store name
    trulieve_cranberry_products = fetch_trulieve_data(trulieve_cranberry_id)
    for p in trulieve_cranberry_products:
        p["_source_store"] = "Trulieve - Cranberry"
    master_inventory.extend(trulieve_cranberry_products)

    # 3b. Fetch Trulieve Data (Zelienople) & tag with store name
    trulieve_zelienople_products = fetch_trulieve_data(trulieve_zelienople_id)
    for p in trulieve_zelienople_products:
        p["_source_store"] = "Trulieve - Zelienople"
    master_inventory.extend(trulieve_zelienople_products)
    
    # 4. Fetch Ascend Data using the Dutchie API & tag with store name
    ascend_raw = fetch_dutchie_data(ascend_id)
    try:
        ascend_json = json.loads(ascend_raw)
        if "data" in ascend_json and "filteredProducts" in ascend_json["data"]:
            ascend_products = ascend_json["data"]["filteredProducts"].get("products", [])
            for p in ascend_products:
                p["_source_store"] = "Ascend"
            master_inventory.extend(ascend_products)
    except Exception:
        print("[!] Failed to parse Ascend inventory")
        
    # 5. Fetch Zen Leaf Data & tag with store name
    zenleaf_products = fetch_zenleaf_data(zenleaf_id)
    for p in zenleaf_products:
        p["_source_store"] = "Zen Leaf - Cranberry"
    master_inventory.extend(zenleaf_products)

    print(f"\n[+] Aggregated {len(master_inventory)} total products across all stores.")
    
    # 6. Define your Personal Preferences!
    my_preferences = (
        "I am looking for 1g Indica vape cartridges. "
        "i like to buy a couple of each strain and no more than 8 total in an order. "
        "a typical 1g indica cart should cost under $30. "
        "the thc level should be high (above 70%). "
        "I prefer strains high in Myrcene or Caryophyllene if that data is available, otherwise just look for classic heavy Indicas. "
        "Which single store offers the best basket for my money today?"
    )
    
    # 7. Get AI Recommendation
    if master_inventory:
        # ---  GEMINI CALL ---
        recommendation_json = get_shopping_recommendation(json.dumps(master_inventory), my_preferences)
        try:
            rec_data = json.loads(recommendation_json)
            if "error" in rec_data:
                print(f"\n[!] Error from AI: {rec_data['error']}")
                return f"AI Error: {rec_data['error']}", f"Error: {rec_data['error']}"
            else:
                md_output = f"# AI Personal Shopper Recommendation\n\n"
                md_output += f"**Recommended Dispensary:** {rec_data.get('recommended_dispensary', 'N/A')}\n"
                md_output += f"**Total Estimated Cost:** ${rec_data.get('total_estimated_cost', 0):.2f}\n\n"
                md_output += f"### Overall Justification\n{rec_data.get('overall_justification', 'N/A')}\n\n"
                md_output += f"### Items to Buy\n"
                for item in rec_data.get('items_to_buy', []):
                    md_output += f"- **{item.get('quantity', 1)}x {item.get('product_name', 'Unknown')}** ({item.get('weight', 'N/A')})\n"
                    md_output += f"  - **Unit Price:** ${item.get('unit_price', 0):.2f}\n"
                    md_output += f"  - **Discount:** {item.get('applied_discount', 'None')}\n"
                    md_output += f"  - **Terpenes:** {item.get('terpenes', 'Unknown')}\n"
                    md_output += f"  - **Justification:** {item.get('justification', 'N/A')}\n"
                print("\n" + "="*60 + "\n")
                print(md_output)
                print("="*60 + "\n")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"/tmp/shopping_recommendation_{timestamp}.md"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(md_output)
                
                # Save to the /tmp directory (which Google Cloud Run uses for in-memory file storage)
                with open("/tmp/latest_report.md", "w", encoding="utf-8") as f:
                    f.write(md_output)
                    
                # Create the short, conversational summary for Siri
                dispensary = rec_data.get('recommended_dispensary', 'Unknown')
                cost = rec_data.get('total_estimated_cost', 0)
                speech_text = f"I recommend going to {dispensary}. The total estimated cost for your cart is ${cost:.2f}."
                
                return speech_text, md_output
        except json.JSONDecodeError:
            print("\n--- AI Personal Shopper Recommendation (Raw JSON) ---")
            print(recommendation_json)
            return "I encountered an error parsing the AI data.", recommendation_json
            
    return f"No deals found. Master inventory contained {len(master_inventory)} items.", "No deals found."

@app.route("/", methods=["GET"])
def health_check():
    return "MMJ Deals Finder is awake and running!", 200

@app.route("/run-deals", methods=["GET", "POST"])
def run_deals_webhook():
    print("Webhook triggered by Siri/Cloud!")
    speech_text, full_report = generate_deals_report()
    
    # Dynamically grab the server URL so the link works in the cloud
    list_url = f"{request.host_url.rstrip('/')}/list"
    display_text = f"{speech_text}\n\n🔗 Tap here to view your full shopping list:\n{list_url}"
    
    # Return JSON so the iOS Shortcut can separate spoken text from displayed text
    return jsonify({"speech": speech_text, "display": display_text})

@app.route("/list", methods=["GET"])
def view_latest_list():
    # Serve the full markdown file wrapped in beautiful, mobile-friendly HTML
    try:
        with open("/tmp/latest_report.md", "r", encoding="utf-8") as f:
            report = f.read()
            
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
            <script>
                const markdownText = {json.dumps(report)};
                document.getElementById('content').innerHTML = marked.parse(markdownText);
            </script>
        </body>
        </html>
        """
        return Response(html_content, mimetype="text/html")
    except FileNotFoundError:
        return Response("<main class='container'><h1>No report found.</h1><p>Ask Siri to find deals first!</p></main>", mimetype="text/html")

if __name__ == "__main__":
    # If running locally in the terminal, just print the report directly
    speech, report = generate_deals_report()
    print(f"\n[SIRI WOULD SAY]: {speech}")
