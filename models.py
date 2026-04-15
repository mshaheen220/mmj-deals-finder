from pydantic import BaseModel, Field

class RecommendedItem(BaseModel):
    product_name: str = Field(description="Name of the cannabis product")
    unit_price: float = Field(description="Effective price per single unit AFTER applying any quantity discounts")
    quantity: int = Field(description="Number of units to purchase of this specific product")
    applied_discount: str = Field(description="Description of any quantity discount or special applied (e.g., '2 for $50', 'None')")
    weight: str = Field(description="Weight of the product (e.g., 1g)")
    terpenes: dict[str, float] = Field(description="Dictionary of dominant terpenes and their percentages (e.g., {'Myrcene': 1.2, 'Limonene': 0.5})")
    effects: dict[str, float] = Field(default_factory=dict, description="Dictionary of reported effects (e.g., {'Relaxed': 9, 'Pain Relief': 7})")
    justification: str = Field(description="Why this specific product was chosen based on user preferences")

class ShoppingTrip(BaseModel):
    recommended_dispensary: str = Field(description="The SINGLE dispensary chosen for this trip")
    math_scratchpad: str = Field(description="Brief math equation proving the total cost (e.g., '4 * 25 = 100'). Keep it extremely short.")
    total_estimated_cost: float = Field(description="Total cost of the recommended items")
    overall_justification: str = Field(description="Why this dispensary and basket of goods was chosen over the alternatives")
    items_to_buy: list[RecommendedItem]

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
    total_terpenes: float
    effects: dict[str, float]
    source_store: str