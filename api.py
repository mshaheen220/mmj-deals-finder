import json
import urllib.parse
from curl_cffi import requests

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
                "types": [],
                "isDefaultSort": True,
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

def fetch_trulieve_data(store_id: str) -> list:
    print(f"Fetching data directly from Trulieve API for store {store_id}...")
    all_products = []
    page = 1
    
    headers = {
        "Origin": "https://www.trulieve.com",
        "Referer": "https://www.trulieve.com/"
    }
    
    while True:
        url = f"https://api.trulieve.com/api/v2/menu/{store_id}/vapes/DEFAULT?search=&weights=1g&brand=&strain_type=indica&subcategory=CARTRIDGES&cbd_max=&cbd_min=&thc_max=&thc_min=70&tags_menu=&collections=&special=&sort_by=default&page={page}"
        
        try:
            print(f"    [>] Fetching page {page}...")
            response = requests.get(url, headers=headers, impersonate="chrome120")
            response.raise_for_status()
            data = response.json()
            
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
                break
                
            all_products.extend(products)
            page += 1
            
        except Exception as e:
            print(f"    [!] Failed to fetch Trulieve data on page {page}: {e}")
            break
            
    print(f"    [+] Successfully fetched {len(all_products)} total products from Trulieve!")
    return all_products

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