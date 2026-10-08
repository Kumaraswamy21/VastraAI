"""Deterministic, category-aware synthetic Indian fashion catalog generator."""

from dataclasses import dataclass
import random
import re

from fashion_search.catalog.schemas import ProductCreate

DEFAULT_SEED = 20261007
DEFAULT_PRODUCT_COUNT = 750

COLORS = (
    "black", "white", "navy blue", "maroon", "emerald green", "mustard",
    "beige", "powder blue", "coral", "olive", "lavender", "rust",
)
ADJECTIVES = (
    "Classic", "Elegant", "Festive", "Contemporary", "Handcrafted",
    "Refined", "Heritage", "Everyday", "Statement", "Minimal",
)


@dataclass(frozen=True)
class CategoryProfile:
    """Coherent generation rules for one product category."""

    category: str
    genders: tuple[str, ...]
    materials: tuple[str, ...]
    occasions: tuple[str, ...]
    styles: tuple[str, ...]
    sizes: tuple[str, ...]
    price_range: tuple[int, int]
    nouns: tuple[str, ...]


PROFILES = (
    CategoryProfile("saree", ("women",), ("silk", "cotton", "chiffon", "georgette"), ("wedding", "festive", "party", "formal"), ("banarasi", "kanjeevaram", "printed", "embroidered"), ("Free Size",), (1400, 12000), ("Saree",)),
    CategoryProfile("kurta", ("women",), ("cotton", "rayon", "silk blend", "linen"), ("casual", "festive", "office", "wedding"), ("straight", "anarkali", "a-line", "embroidered"), ("XS", "S", "M", "L", "XL", "XXL"), (650, 4500), ("Kurta", "Kurti")),
    CategoryProfile("salwar suit", ("women",), ("cotton", "chanderi", "silk blend", "georgette"), ("festive", "wedding", "office", "party"), ("anarkali", "palazzo", "churidar", "embroidered"), ("XS", "S", "M", "L", "XL", "XXL"), (1200, 7000), ("Suit Set", "Salwar Suit")),
    CategoryProfile("lehenga", ("women",), ("silk", "velvet", "georgette", "organza"), ("wedding", "festive", "party"), ("embroidered", "zari", "mirror work", "contemporary"), ("XS", "S", "M", "L", "XL"), (3000, 18000), ("Lehenga Set",)),
    CategoryProfile("dress", ("women",), ("cotton", "viscose", "satin", "linen"), ("casual", "party", "office", "vacation"), ("a-line", "wrap", "maxi", "fit and flare"), ("XS", "S", "M", "L", "XL"), (900, 5500), ("Dress",)),
    CategoryProfile("shirt", ("men",), ("cotton", "linen", "denim", "viscose"), ("casual", "office", "party", "vacation"), ("checked", "solid", "printed", "slim fit"), ("S", "M", "L", "XL", "XXL"), (700, 3500), ("Shirt",)),
    CategoryProfile("kurta", ("men",), ("cotton", "linen", "silk blend", "jacquard"), ("festive", "wedding", "casual"), ("classic", "embroidered", "nehru collar", "pathani"), ("S", "M", "L", "XL", "XXL"), (900, 5500), ("Kurta",)),
    CategoryProfile("sherwani", ("men",), ("silk blend", "brocade", "velvet", "jacquard"), ("wedding", "festive"), ("embroidered", "jodhpuri", "achkan", "classic"), ("S", "M", "L", "XL", "XXL"), (4500, 22000), ("Sherwani", "Achkan")),
    CategoryProfile("trousers", ("men", "women"), ("cotton blend", "linen blend", "viscose"), ("office", "casual", "party"), ("tailored", "wide leg", "straight fit", "relaxed"), ("28", "30", "32", "34", "36", "38"), (900, 4000), ("Trousers",)),
    CategoryProfile("jeans", ("men", "women"), ("denim",), ("casual", "party", "travel"), ("straight fit", "slim fit", "relaxed", "bootcut"), ("28", "30", "32", "34", "36", "38"), (1000, 4500), ("Jeans",)),
    CategoryProfile("t-shirt", ("men", "women", "unisex"), ("cotton", "cotton blend", "modal"), ("casual", "workout", "travel"), ("graphic", "solid", "oversized", "polo"), ("XS", "S", "M", "L", "XL", "XXL"), (450, 2200), ("T-Shirt", "Polo T-Shirt")),
    CategoryProfile("jacket", ("men", "women", "unisex"), ("denim", "cotton twill", "polyester", "faux leather"), ("casual", "travel", "party"), ("bomber", "biker", "utility", "denim"), ("S", "M", "L", "XL", "XXL"), (1500, 6500), ("Jacket",)),
    CategoryProfile("dupatta", ("women",), ("chanderi", "silk", "cotton", "organza"), ("festive", "wedding", "casual"), ("bandhani", "phulkari", "printed", "zari"), ("Free Size",), (500, 3500), ("Dupatta",)),
    CategoryProfile("footwear", ("men",), ("leather", "suede", "textile"), ("wedding", "office", "casual", "festive"), ("mojari", "loafer", "sneaker", "kolhapuri"), ("6", "7", "8", "9", "10", "11"), (900, 6000), ("Mojari", "Loafers", "Sneakers")),
    CategoryProfile("footwear", ("women",), ("leather", "suede", "textile"), ("wedding", "office", "casual", "festive", "party"), ("juttis", "heels", "flats", "kolhapuri"), ("3", "4", "5", "6", "7", "8"), (800, 5500), ("Juttis", "Heels", "Flats")),
)


def slugify(value: str) -> str:
    """Convert a title-like value to an ASCII URL slug."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def rounded_price(rng: random.Random, price_range: tuple[int, int]) -> int:
    """Choose a retail-looking price ending in 49 or 99 within a profile range."""
    low, high = price_range
    base = rng.randrange((low // 50) + 1, high // 50) * 50
    return min(high, max(low, base - rng.choice((1, 1, 51))))


def choose_sizes(rng: random.Random, available: tuple[str, ...]) -> list[str]:
    """Return a realistic contiguous selection of available sizes."""
    if len(available) == 1:
        return list(available)
    start = rng.randrange(0, min(2, len(available) - 2))
    end = rng.randrange(max(start + 2, len(available) - 2), len(available) + 1)
    return list(available[start:end])


def build_product(rng: random.Random, profile: CategoryProfile, index: int) -> ProductCreate:
    """Build and validate one coherent product from a category profile."""
    color = rng.choice(COLORS)
    material = rng.choice(profile.materials)
    occasion = rng.choice(profile.occasions)
    style = rng.choice(profile.styles)
    gender = rng.choice(profile.genders)
    noun = rng.choice(profile.nouns)
    title = f"{rng.choice(ADJECTIVES)} {color.title()} {style.title()} {noun}"
    slug = f"{slugify(title)}-{index:04d}"
    description = (
        f"A {style} {noun.lower()} in {color}, made from {material}. "
        f"Designed for {occasion} wear with comfortable, practical finishing."
    )
    return ProductCreate.model_validate(
        {
            "title": title,
            "category": profile.category,
            "color": color,
            "material": material,
            "occasion": occasion,
            "style": style,
            "gender": gender,
            "sizes": choose_sizes(rng, profile.sizes),
            "price_inr": rounded_price(rng, profile.price_range),
            "description": description,
            "image_reference": f"catalog/{slug}.webp",
            "slug": slug,
        }
    )


def generate_catalog(
    count: int = DEFAULT_PRODUCT_COUNT,
    seed: int = DEFAULT_SEED,
) -> list[ProductCreate]:
    """Generate a repeatable validated catalog with balanced category profiles."""
    if not 500 <= count <= 1000:
        raise ValueError("catalog count must be between 500 and 1000")
    rng = random.Random(seed)
    return [build_product(rng, PROFILES[index % len(PROFILES)], index + 1) for index in range(count)]
