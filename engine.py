import re
from typing import Optional

# A list of known brands to help with parsing brand-specific deals.
# This can be dynamically generated from the inventory later.
KNOWN_BRANDS = [
    "Strane", "Strane Stash", "Strane Reserve", "Garcia Hand Picked", 
    "Cresco", "Rythm", "GTI", "INSA", "Curaleaf", "Standard Farms", "Holistic",
    "Liberty", "Verano", "Savvy", "Essence", "On The Rocks", "Ozone"
]

def parse_promo_text(promo_text: str) -> Optional[dict]:
    """Parses a single promo string and returns a structured rule."""
    
    # Pattern 1: Flat bundle (e.g., "4 for $99" or "2 Ozone carts for $55"). \b and negative lookahead (?!\s*%) ensures we don't match "2 for 42%"
    bundle_match = re.search(r'\b(\d+)\s+(?:[a-zA-Z0-9.\-]+\s+){0,6}for\s+\$?([\d.]+)\b(?!\s*%)', promo_text, re.IGNORECASE)
    if bundle_match:
        brands_found = []
        for brand in KNOWN_BRANDS:
            if re.search(r'\b' + re.escape(brand) + r'\b', promo_text, re.IGNORECASE):
                brands_found.append(brand)
                
        return {
            "type": "bundle",
            "required_quantity": int(bundle_match.group(1)),
            "bundle_price": float(bundle_match.group(2)),
            "scope": "brand" if brands_found else "product",
            "brands": brands_found
        }

    # Pattern 2: Bulk percentage (e.g., "50% off 6+" OR "2 for 42% off")
    bulk_match_1 = re.search(r'([\d.]+)\s*%\s*(?:off\s+)?(\d+)\s*\+', promo_text, re.IGNORECASE)
    bulk_match_2 = re.search(r'\b(\d+)\s+(?:[a-zA-Z0-9.\-]+\s+){0,6}for\s+([\d.]+)\s*%(?:\s*off)?', promo_text, re.IGNORECASE)
    
    if bulk_match_1 or bulk_match_2:
        # After matching the core deal, check for brand names in the rest of the string
        brands_found = []
        for brand in KNOWN_BRANDS:
            # Use word boundaries to avoid matching substrings like 'and' in 'Standard'
            if re.search(r'\b' + re.escape(brand) + r'\b', promo_text, re.IGNORECASE):
                brands_found.append(brand)
                
        discount = float(bulk_match_1.group(1)) / 100.0 if bulk_match_1 else float(bulk_match_2.group(2)) / 100.0
        qty = int(bulk_match_1.group(2)) if bulk_match_1 else int(bulk_match_2.group(1))
        
        return {
            "type": "bulk_percent",
            "discount_percent": discount,
            "required_quantity": qty,
            "scope": "brand" if brands_found else "product",
            "brands": brands_found
        }
        
    # Pattern 3: Standard percentage (e.g., "30% STOREWIDE SALE!", "40% off Strane")
    # Matches any percentage number, as long as it didn't already match the bulk deal above
    standard_percent_match = re.search(r'([\d.]+)\s*%', promo_text)
    if standard_percent_match:
        brands_found = []
        for brand in KNOWN_BRANDS:
            if re.search(r'\b' + re.escape(brand) + r'\b', promo_text, re.IGNORECASE):
                brands_found.append(brand)
        
        return {
            "type": "standard_percent",
            "discount_percent": float(standard_percent_match.group(1)) / 100.0,
            "required_quantity": 1,
            "scope": "brand" if brands_found else "storewide",
            "brands": brands_found
        }
        
    # Pattern 4: Flat dollar discount (e.g., "$5 Off 1g Ozone Distillate Cartridges!")
    flat_off_match = re.search(r'\$([\d.]+)\s*off', promo_text, re.IGNORECASE)
    if flat_off_match:
        brands_found = []
        for brand in KNOWN_BRANDS:
            if re.search(r'\b' + re.escape(brand) + r'\b', promo_text, re.IGNORECASE):
                brands_found.append(brand)
        
        return {
            "type": "flat_discount",
            "discount_amount": float(flat_off_match.group(1)),
            "required_quantity": 1,
            "scope": "brand" if brands_found else "storewide",
            "brands": brands_found
        }
        
    return None

def parse_all_promos(promo_texts: list[str]) -> list[dict]:
    """Iterates through a list of promo strings and returns all parsed rules."""
    parsed_rules = []
    for text in promo_texts:
        rule = parse_promo_text(text)
        if rule:
            parsed_rules.append(rule)
    return parsed_rules

def score_product(product: dict) -> float:
    """Scores an individual product based on user preferences (Max: ~60 pts)"""
    score = 0.0
    
    # Terpenes Preference (+20 pts)
    terps = product.get("terpenes", {})
    if "Myrcene" in terps or "Caryophyllene" in terps:
        score += 20
    elif terps:
        score += 5  # Bonus just for having transparency/data
        
    # Effects Preference (+20 pts)
    effects = product.get("effects", {})
    if "Relaxed" in effects or "Pain Relief" in effects:
        score += 20
        
    # THC Percentage (Scales up to +20 pts)
    thc = product.get("thc_percentage", 0.0)
    score += (thc / 100.0) * 20
    
    return score

def score_cart(cart: dict) -> float:
    """Scores a full cart based on average product quality and price (Max: ~100 pts)"""
    score = 0.0
    
    # 1. Average Product Quality Score
    item_scores = []
    for item in cart["items_to_buy"]:
        s = 0
        terps = item.get("terpenes", {})
        effects = item.get("effects", {})
        if "Myrcene" in terps or "Caryophyllene" in terps: s += 20
        if "Relaxed" in effects or "Pain Relief" in effects: s += 20
        item_scores.append(s)
        
    score += (sum(item_scores) / len(item_scores)) if item_scores else 0
    
    # 2. Price Score: $27 = 0 pts. Drops below $15 max out at +40 pts.
    unit_price = cart.get("effective_unit_price", 27.0)
    price_diff = max(0.0, 27.0 - unit_price)
    score += min(40.0, price_diff * 3.33)
    
    return score

def generate_best_cart(inventory: list[dict]) -> Optional[dict]:
    """Groups by store, simulates rule combinations, and returns the best overall cart."""
    stores = {}
    
    # 1. Group by store and apply hard THC limit
    for p in inventory:
        if p.get("thc_percentage", 0) < 70:
            continue
        store = p.get("source_store")
        if store not in stores:
            stores[store] = []
        stores[store].append(p)
        
    best_overall_cart = None
    highest_score = -1
    
    for store, products in stores.items():
        # Score and sort products so we always grab the best ones first
        for p in products:
            p["_base_score"] = score_product(p)
        products.sort(key=lambda x: x["_base_score"], reverse=True)
        
        # Extract all unique rules available at this store
        unique_rules = []
        seen = set()
        for p in products:
            for r in p.get("parsed_rules", []):
                r_str = str(r)
                if r_str not in seen:
                    seen.add(r_str)
                    unique_rules.append(r)
                    
        valid_carts = []
        
        # Scenario A: Standard Sale Pricing (Buy 4 of the best standard-priced items)
        cheap_products = [p for p in products if p.get("sale_price", 999) <= 26.99]
        if cheap_products:
            cart_items = []
            total_cost = 0.0
            for p in cheap_products[:2]:  # Top 2 products, buy 2 of each
                cart_items.append({
                    "product_name": p["product_name"], "unit_price": p["sale_price"], "quantity": 2,
                    "applied_discount": "Standard Sale", "weight": p["weight"],
                    "terpenes": p.get("terpenes", {}), "effects": p.get("effects", {}),
                    "justification": f"Standard sale price of ${p['sale_price']:.2f} meets strict limits."
                })
                total_cost += (p["sale_price"] * 2)
            if len(cart_items) > 0:
                total_qty = sum(item["quantity"] for item in cart_items)
                valid_carts.append({
                    "recommended_dispensary": store, "total_estimated_cost": total_cost, "effective_unit_price": total_cost / total_qty,
                    "math_scratchpad": f"{total_qty} items at standard sale = ${total_cost:.2f}",
                    "overall_justification": "Utilizing standard individual sale prices to maximize preferred terpenes.",
                    "items_to_buy": cart_items
                })
                
        # Scenario B: Apply Bulk and Brand Deals
        for rule in unique_rules:
            qty_needed = max(4, rule.get("required_quantity", 1)) # We want at least 4
            if qty_needed > 10: continue # User hard limit
            
            eligible_products = [p for p in products if rule["scope"] == "storewide" or p["brand"] in rule.get("brands", [])]
            if not eligible_products: continue
            
            cart_items_raw = []
            remaining_qty = qty_needed
            total_msrp = 0.0
            
            # Grab top items 2 at a time until we hit the threshold
            for p in eligible_products:
                if remaining_qty <= 0: break
                take_qty = min(2, remaining_qty)
                cart_items_raw.append({"p": p, "qty": take_qty})
                total_msrp += (p["msrp_price"] * take_qty)
                remaining_qty -= take_qty
                
            if remaining_qty == 0:
                total_cost = 0.0
                math_str = ""
                discount_desc = ""
                
                if rule["type"] == "bundle":
                    bundles_count = qty_needed / rule["required_quantity"]
                    total_cost = rule["bundle_price"] * bundles_count
                    math_str = f"{int(bundles_count)} bundle(s) * ${rule['bundle_price']} = ${total_cost:.2f}"
                    discount_desc = f"{rule['required_quantity']} for ${rule['bundle_price']} Bundle"
                elif rule["type"] == "bulk_percent":
                    discount_amt = total_msrp * rule["discount_percent"]
                    total_cost = total_msrp - discount_amt
                    math_str = f"MSRP ${total_msrp:.2f} - {int(rule['discount_percent']*100)}% = ${total_cost:.2f}"
                    discount_desc = f"{int(rule['discount_percent']*100)}% Off Bulk Deal"
                else:
                    continue # Standard percent handled by Scenario A
                    
                unit_price = total_cost / qty_needed
                if unit_price <= 26.99:
                    formatted_items = []
                    for item in cart_items_raw:
                        p = item["p"]
                        formatted_items.append({
                            "product_name": p["product_name"], "unit_price": unit_price, "quantity": item["qty"],
                            "applied_discount": discount_desc, "weight": p["weight"],
                            "terpenes": p.get("terpenes", {}), "effects": p.get("effects", {}),
                            "justification": f"Selected to fulfill {discount_desc} deal."
                        })
                        
                    valid_carts.append({
                        "recommended_dispensary": store, "total_estimated_cost": total_cost, "effective_unit_price": unit_price,
                        "math_scratchpad": math_str,
                        "overall_justification": f"This store offers a powerful {discount_desc}, dropping the price to ${unit_price:.2f} each.",
                        "items_to_buy": formatted_items
                    })
                    
        # Score valid carts and crown the winner
        for cart in valid_carts:
            c_score = score_cart(cart)
            if c_score > highest_score:
                highest_score = c_score
                best_overall_cart = cart
                
    return best_overall_cart