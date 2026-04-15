from pydantic import BaseModel, Field

class NormalizedProduct(BaseModel):
    product_name: str
    brand: str
    strain_type: str
    category: str
    weight: str
    thc_percentage: float
    msrp_price: float
    sale_price: float
    promos: list[str]
    terpenes: dict[str, float]
    effects: dict[str, float]
    source_store: str