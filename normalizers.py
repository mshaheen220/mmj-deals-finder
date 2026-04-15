import re
from models import NormalizedProduct

def get_first_valid_number(*args):
    """Aggressively un-nests dictionaries and lists to find the first valid float > 0"""
    for val in args:
        if not val: continue
        if isinstance(val, list) and len(val) > 0:
            val = val[0]
        if isinstance(val, dict):
            val = val.get("med") or val.get("rec") or val.get("value") or val.get("amount") or val.get("price") or val.get("sellPrice")
        if isinstance(val, dict): # double nested check
            val = val.get("med") or val.get("value") or val.get("amount")
        if isinstance(val, (int, float)):
            if val > 0: return float(val)
        if isinstance(val, str):
            match = re.search(r'([\d.]+)', val)
            if match and float(match.group(1)) > 0:
                return float(match.group(1))
    return 0.0

COMMON_TERPENES = [
    "Myrcene", "Caryophyllene", "Limonene", "Linalool", "Pinene", 
    "Humulene", "Terpinolene", "Ocimene", "Bisabolol", "Camphene", 
    "Terpineol", "Phellandrene", "Carene", "Nerolidol", "Geraniol"
]

def extract_all_terpenes(raw_item: dict, structured_data) -> dict:
    terps = {}
    flat_items = []
    if isinstance(structured_data, list):
        for item in structured_data:
            if isinstance(item, list):
                flat_items.extend(item)
            elif item:
                flat_items.append(item)
    elif structured_data:
        flat_items.append(structured_data)
        
    for terp in flat_items:
        if isinstance(terp, dict):
            name_obj = terp.get("terpene") or terp
            name = name_obj.get("name") if isinstance(name_obj, dict) else terp.get("name") or terp.get("terpene")
            if name and isinstance(name, str):
                val = get_first_valid_number(terp.get("value"), terp.get("amount"), terp.get("percentage"))
                terps[name.strip()] = val
            else:
                for k, v in terp.items():
                    if isinstance(v, (int, float, str)) and k.lower() not in ["unit", "range", "__typename", "id", "value"]:
                        terps[str(k).strip()] = get_first_valid_number(v)
        elif isinstance(terp, str):
            terps[terp.strip()] = 0.0

    desc_parts = [
        raw_item.get("description"), raw_item.get("descriptionHtml"),
        raw_item.get("Description"), raw_item.get("staffReview"),
        raw_item.get("POSMetaData", {}).get("description")
    ]
    desc = " ".join([str(d) for d in desc_parts if d])
    name_str = str(raw_item.get("name") or raw_item.get("productName") or "")
    full_text = (desc + " " + name_str).lower()
    
    for t_name in COMMON_TERPENES:
        matched_key = next((k for k in terps.keys() if t_name.lower() in k.lower()), None)
        if not matched_key or terps[matched_key] == 0.0:
            if t_name.lower() in full_text:
                val = 0.0
                m1 = re.search(rf'{t_name.lower()}[^\d]*?([\d.]+)\s*%', full_text)
                if m1:
                    val = float(m1.group(1))
                else:
                    m2 = re.search(rf'([\d.]+)\s*%[^\d]*?{t_name.lower()}', full_text)
                    if m2:
                        val = float(m2.group(1))
                if val > 0:
                    terps[t_name] = val
                elif not matched_key:
                    terps[t_name] = 0.0
                    
    return dict(sorted(terps.items(), key=lambda item: item[1], reverse=True)[:4])

def normalize_dutchie_product(raw_item: dict, store_name: str) -> dict:
    product_name = raw_item.get("name") or raw_item.get("Name") or raw_item.get("productName") or "Unknown"
    
    brand_data = raw_item.get("brand")
    brand = brand_data.get("name", "Unknown") if isinstance(brand_data, dict) else str(brand_data or "Unknown")
    
    options = raw_item.get("options") or raw_item.get("Options") or raw_item.get("variants") or []
    opt = options[0] if isinstance(options, list) and len(options) > 0 else {}
    
    weight = "Unknown"
    if isinstance(opt, dict):
        weight = opt.get("option") or opt.get("name") or "Unknown"
    elif isinstance(opt, str):
        weight = opt
        opt = {}
        
    if weight == "Unknown" and raw_item.get("weight"):
        weight = str(raw_item.get("weight"))
    if str(weight).isdigit():
        weight = "1g" 

    thc_content = get_first_valid_number(
        opt.get("potency", {}).get("thc"),
        opt.get("thc"),
        raw_item.get("THCContent", {}).get("range"),
        raw_item.get("thcContent", {}).get("range"),
        raw_item.get("thcContent"),
        raw_item.get("thc"),
        raw_item.get("THC"),
        raw_item.get("potencyAmount", {}).get("thc"),
        raw_item.get("potency", {}).get("thc")
    )

    msrp = get_first_valid_number(
        raw_item.get("medicalPrices"),
        raw_item.get("recPrices"),
        opt.get("priceMed"), opt.get("price"), opt.get("prices"),
        raw_item.get("priceMed"), raw_item.get("priceRec"), raw_item.get("prices"), raw_item.get("price"), raw_item.get("Prices")
    )
    
    sale_price = get_first_valid_number(
        raw_item.get("medicalSpecialPrices"),
        raw_item.get("recSpecialPrices"),
        opt.get("specialPriceMed"), opt.get("specialPrice"),
        raw_item.get("specialPriceMed"), raw_item.get("specialPriceRec"), raw_item.get("specialPrice"), raw_item.get("discountedPrice")
    )
    
    if sale_price == 0.0:
        sale_price = msrp

    promos = []
    specials = opt.get("specials") or raw_item.get("specials") or raw_item.get("Specials") or []
    if isinstance(specials, list):
        for special in specials:
            if isinstance(special, dict) and special.get("title"):
                promos.append(special["title"])
            elif isinstance(special, str):
                promos.append(special)
                
    special_data = raw_item.get("specialData") or {}
    for promo_type in ["bogoSpecials", "saleSpecials"]:
        for special in special_data.get(promo_type, []):
            name = special.get("specialName")
            if name and name not in promos:
                promos.append(name)

    terp_sources = [
        raw_item.get("terpenes"),
        raw_item.get("terpenesV2"),
        raw_item.get("terpeneProfile"),
        opt.get("terpenes"),
        raw_item.get("potency", {}).get("terpenes")
    ]
    terpenes = extract_all_terpenes(raw_item, terp_sources)
    
    tt_obj = raw_item.get("totalTerpenes") or {}
    total_terps = get_first_valid_number(tt_obj.get("range"), tt_obj.get("value"), tt_obj)
    
    effects_raw = raw_item.get("effects") or {}
    effects = {}
    if isinstance(effects_raw, dict):
        for k, v in effects_raw.items():
            val = get_first_valid_number(v)
            if val > 0:
                effects[str(k).replace("-", " ").title()] = val
                    
    return NormalizedProduct(
        product_name=str(product_name),
        brand=brand,
        strain_type=str(raw_item.get("strainType", "Unknown") or "Unknown"),
        category=str(raw_item.get("type", "Unknown") or raw_item.get("category", "Unknown")),
        weight=str(weight),
        thc_percentage=thc_content,
        msrp_price=msrp,
        sale_price=sale_price,
        promos=promos,
        terpenes=terpenes,
        total_terpenes=total_terps,
        effects=effects,
        source_store=store_name
    ).model_dump()

def normalize_trulieve_product(raw_item: dict, store_name: str) -> dict:
    variants = raw_item.get("variants") or []
    opt = variants[0] if isinstance(variants, list) and len(variants) > 0 else {}

    thc = get_first_valid_number(opt.get("thc_percentage"), opt.get("thc_content"), raw_item.get("thc_percentage"), raw_item.get("thc_content"), raw_item.get("thc"))
    msrp = get_first_valid_number(opt.get("unit_price"), opt.get("price"), raw_item.get("price"), raw_item.get("regular_price"), raw_item.get("default_price"))
    sale_price = get_first_valid_number(opt.get("sale_unit_price"), opt.get("special_price"), raw_item.get("discounted_price"), raw_item.get("sale_price"))
    if sale_price == 0.0: sale_price = msrp
        
    promos = []
    raw_promos = raw_item.get("promotions") or raw_item.get("specials") or []
    if isinstance(raw_promos, list):
        for promo in raw_promos:
            if isinstance(promo, dict):
                p_text = promo.get("name") or promo.get("description")
                if p_text: promos.append(p_text)
            elif isinstance(promo, str):
                promos.append(promo)
                
    brand_data = raw_item.get("brand")
    brand = brand_data.get("name", "Unknown") if isinstance(brand_data, dict) else str(brand_data or "Unknown")

    category_data = raw_item.get("subcategory")
    category = category_data.get("name", "Unknown") if isinstance(category_data, dict) else str(category_data or "Unknown")

    unit_size = opt.get("unitSize") or raw_item.get("unitSize") or {}
    weight = "Unknown"
    if isinstance(unit_size, dict) and "value" in unit_size:
        val = unit_size.get("value")
        abbr = str(unit_size.get("unitAbbr", "")).lower()
        if val is not None:
            if val == int(val): val = int(val) 
            weight = f"{val}{abbr}"
    if weight == "Unknown":
        weight = str(opt.get("size") or opt.get("option") or raw_item.get("size", "Unknown") or "Unknown")

    terp_sources = raw_item.get("terpenes") or raw_item.get("terpene_profile") or []
    terpenes = extract_all_terpenes(raw_item, terp_sources)

    return NormalizedProduct(
        product_name=raw_item.get("name", "Unknown") or "Unknown",
        brand=brand,
        strain_type=raw_item.get("strain_type", "Unknown") or "Unknown",
        category=category,
        weight=weight,
        thc_percentage=thc,
        msrp_price=msrp,
        sale_price=sale_price,
        promos=promos,
        terpenes=terpenes,
        total_terpenes=0.0,
        effects={},
        source_store=store_name
    ).model_dump()

def normalize_zenleaf_product(raw_item: dict, store_name: str) -> dict:
    variants = raw_item.get("variants") or []
    opt = variants[0] if isinstance(variants, list) and len(variants) > 0 else {}

    thc = get_first_valid_number(
        opt.get("thc"), 
        raw_item.get("thc"),
        opt.get("labTests", {}).get("thc", {}).get("value"),
        raw_item.get("labTests", {}).get("thc", {}).get("value"),
        raw_item.get("labTests", {}).get("displayThc")
    )
    msrp = get_first_valid_number(opt.get("price"), opt.get("regularPrice"), raw_item.get("price"), raw_item.get("regularPrice"))
    sale_price = get_first_valid_number(opt.get("promoPrice"), opt.get("specialPrice"), raw_item.get("promoPrice"), raw_item.get("specialPrice"))
    if sale_price == 0.0: sale_price = msrp
    
    promos = []
    for variant in raw_item.get("variants", []):
        for promo in variant.get("promos", []):
            desc = promo.get("full_description") or promo.get("name") or promo.get("shortName")
            if desc and desc not in promos:
                promos.append(desc)
                
    brand_data = raw_item.get("brand")
    brand = brand_data.get("name", "Unknown") if isinstance(brand_data, dict) else str(brand_data or "Unknown")

    category_data = raw_item.get("category")
    category = category_data.get("name", "Unknown") if isinstance(category_data, dict) else str(category_data or "Unknown")

    unit_size = opt.get("unitSize") or raw_item.get("unitSize") or {}
    weight = "Unknown"
    if isinstance(unit_size, dict) and "value" in unit_size:
        val = unit_size.get("value")
        abbr = str(unit_size.get("unitAbbr", "")).lower()
        if val is not None:
            if val == int(val): val = int(val) 
            weight = f"{val}{abbr}"
    if weight == "Unknown":
        weight = str(opt.get("size") or opt.get("option") or raw_item.get("size", "Unknown") or "Unknown")

    terp_sources = raw_item.get("terpenes") or []
    terpenes = extract_all_terpenes(raw_item, terp_sources)

    return NormalizedProduct(
        product_name=raw_item.get("name", "Unknown") or "Unknown",
        brand=brand,
        strain_type=raw_item.get("strainType", "Unknown") or "Unknown",
        category=category,
        weight=weight,
        thc_percentage=thc,
        msrp_price=msrp,
        sale_price=sale_price,
        promos=promos,
        terpenes=terpenes,
        total_terpenes=0.0,
        effects={},
        source_store=store_name
    ).model_dump()