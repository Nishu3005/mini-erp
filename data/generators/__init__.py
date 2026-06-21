"""Programmatic seed-data generators — believable scale without hand-writing thousands of rows.

Hand-authored JSON (`data/*.json`) seeds the *anchor* records — the 8 named users a judge will recognise
(admin/owner/sales.ravi/...) and the curated products/BoMs the demo walks through. These generators
PRODUCE the larger dataset around them — extra team members, ~500 products, ~5,000 customers, etc.

The seed loader (`app/services/seed.py`) calls these AFTER loading the JSON anchors.
"""
import random
from datetime import datetime, timedelta

# Use a fixed seed so seeds are reproducible across runs (judges seeing the same demo every time).
_RNG = random.Random(20260621)

# ---------- name pools ----------
_FIRST = [
    "Aarav","Aditi","Akash","Amit","Anjali","Arjun","Asha","Bhavna","Chetan","Deepa","Dhruv","Divya",
    "Esha","Faisal","Farah","Gaurav","Geeta","Harish","Hema","Imran","Indira","Jatin","Jaya","Karan",
    "Kavita","Krishna","Lakshmi","Manav","Meera","Naveen","Neha","Om","Pankaj","Pooja","Priya",
    "Rahul","Rajesh","Rakesh","Reena","Rohan","Rupali","Sachin","Sandeep","Sanjay","Sapna","Sarita",
    "Shilpa","Shivani","Siddharth","Smita","Suresh","Sushma","Tanvi","Tarun","Uday","Usha","Vandana",
    "Varun","Vidya","Vijay","Vikram","Vinay","Vivek","Yash","Yamini","Zara",
]
_LAST = [
    "Sharma","Verma","Patel","Singh","Kumar","Reddy","Iyer","Nair","Rao","Mehta","Joshi","Gupta",
    "Shah","Mishra","Pandey","Bose","Chatterjee","Mukherjee","Banerjee","Das","Ghosh","Roy","Kapoor",
    "Khanna","Malhotra","Chopra","Saxena","Tiwari","Yadav","Bhatt","Desai","Trivedi","Bhattacharya",
    "Krishnan","Subramanian","Kulkarni","Deshmukh","Pillai","Menon","Pawar","Choudhury","Sengupta",
]
_CITIES = [
    ("Ahmedabad","380001"),("Vadodara","390001"),("Surat","395003"),("Mumbai","400001"),
    ("Pune","411001"),("Bangalore","560001"),("Chennai","600001"),("Hyderabad","500001"),
    ("Delhi","110001"),("Gurgaon","122001"),("Noida","201301"),("Kolkata","700001"),
    ("Jaipur","302001"),("Indore","452001"),("Bhopal","462001"),("Lucknow","226001"),
    ("Patna","800001"),("Coimbatore","641001"),("Kochi","682001"),("Visakhapatnam","530001"),
]
_NEIGHBOURHOODS = [
    "Bodakdev","Maninagar","Vastrapur","Naroda","Satellite","Navrangpura","Gota","Andheri",
    "Bandra","Powai","Koregaon Park","Hinjewadi","Whitefield","Indiranagar","Jayanagar",
    "T. Nagar","Anna Nagar","Banjara Hills","Jubilee Hills","Saket","Connaught Place","Salt Lake",
]


def _name():
    return f"{_RNG.choice(_FIRST)} {_RNG.choice(_LAST)}"


def _address():
    city, pin = _RNG.choice(_CITIES)
    return f"{_RNG.choice(_NEIGHBOURHOODS)}, {city}, {pin}"


def _mobile():
    return "+91" + "".join(str(_RNG.randint(0, 9)) for _ in range(10))


# ---------- users (40 team members beyond the JSON anchors) ----------
# Compact demo: 15 extra users on top of the 8 hand-authored anchors = 23 total.
TEAM_PROFILE = {
    # role -> (count, position_titles, login_prefix, password)
    "sales":         (4, ["Sales Executive","Account Manager"], "sales", "Sales@123"),
    "purchase":      (3, ["Purchase Officer","Buyer"], "purchase", "Purchase@123"),
    "manufacturing": (3, ["Production Supervisor","Floor Lead"], "mfg", "Mfg@1234"),
    "inventory":     (2, ["Inventory Manager","Stock Controller"], "inv", "Inv@1234"),
    "owner":         (1, ["Director"], "owner", "Owner@123"),
    # a couple of pending users so the admin Pending tab has content out of the box
    "_pending":      (2, ["—"], "pending", "Strong@1pass"),
}


def generate_users():
    """Generate extra team-member users to add to the hand-authored 8 anchors."""
    users = []
    n = 1
    for role, (count, titles, prefix, pwd) in TEAM_PROFILE.items():
        for _ in range(count):
            name = _name()
            slug = name.lower().replace(" ", ".")
            login_id = f"{prefix}.{slug.split('.')[0]}{n}"[:12]
            entry = {
                "login_id": login_id,
                "email": f"{slug.split('.')[0]}{n}@shivfurniture.in",
                "password": pwd,
                "name": name,
                "address": _address(),
                "mobile": _mobile(),
                "position": _RNG.choice(titles),
            }
            if role == "_pending":
                entry["status"] = "pending"
                entry["requested_role"] = _RNG.choice(["sales", "purchase", "manufacturing", "inventory"])
                # no role; admin assigns on approval
            else:
                entry["role"] = role
                entry["status"] = "active"
                entry["rights"] = role        # uses the same preset name (sales/purchase/...)
            users.append(entry)
            n += 1
    return users


# ---------- customers (target: ~5,000) ----------
_COMPANY_TYPES = [
    "Furniture", "Interiors", "Home Decor", "Living", "Designs", "Studio",
    "Furnishings", "Lifestyle", "House", "Mart", "Trading Co.", "Retail",
    "Hospitality", "Hotel Group", "Resorts", "Office Solutions", "Workspace",
    "Distributors", "Enterprises", "Industries", "Ltd.", "Pvt. Ltd.", "& Sons",
]
_COMPANY_PREFIX = [
    "Royal","Imperial","Grand","Crown","Heritage","Elite","Prime","Apex","Pinnacle","Zenith",
    "Modern","Urban","Metro","City","Town","Village","Krishna","Shree","Shri","Lakshmi",
    "Sai","Ganesh","Hanuman","Surya","Chandra","Star","Galaxy","Cosmos","Horizon","Skyline",
    "Maple","Oak","Cedar","Pine","Teak","Rosewood","Mahogany","Walnut","Cherry","Birch",
    "Alpha","Beta","Sigma","Omega","Nova","Vega","Orion","Polaris","Phoenix","Atlas",
]


def generate_customers(count=5000):
    """Believable customer names: <Prefix> [Last] <Type>. Reproducible via seeded RNG."""
    out = []
    used = set()
    for _ in range(count):
        for _try in range(5):  # avoid duplicate names
            prefix = _RNG.choice(_COMPANY_PREFIX)
            if _RNG.random() < 0.5:
                suffix = _RNG.choice(_LAST)
                name = f"{prefix} {suffix} {_RNG.choice(_COMPANY_TYPES)}"
            else:
                name = f"{prefix} {_RNG.choice(_COMPANY_TYPES)}"
            if name not in used:
                used.add(name); break
        out.append({"name": name, "address": _address()})
    return out


# ---------- vendors (target: ~40) ----------
_VENDOR_KIND = [
    "Timber Traders","Plywood Co.","Hardware Industries","Metal Works","Fasteners & Fittings",
    "Foam Industries","Fabric House","Upholstery Mart","Lighting Co.","Glass Works","Paint &amp; Polish",
    "Adhesives Co.","Steel Industries","Aluminium Co.","Castings Ltd.","Engineering Works",
]


def generate_vendors(count=40):
    out = []
    used = set()
    for _ in range(count):
        for _try in range(5):
            name = f"{_RNG.choice(_COMPANY_PREFIX)} {_RNG.choice(_VENDOR_KIND)}"
            if name not in used:
                used.add(name); break
        out.append({"name": name, "address": _address()})
    return out


# ---------- products (target: ~500) ----------
_PRODUCT_TYPES = [
    ("Wooden Chair", 1200, 700, 50, False),
    ("Office Chair", 2400, 1300, 25, False),
    ("Executive Chair", 4500, 2600, 12, False),
    ("Dining Chair", 1800, 950, 40, False),
    ("Lounge Sofa", 12000, 7000, 5, True),
    ("Two-Seater Sofa", 8500, 4800, 6, True),
    ("Three-Seater Sofa", 14000, 8200, 4, True),
    ("Dining Table", 5400, 3100, 15, True),
    ("Coffee Table", 3200, 1800, 20, False),
    ("Side Table", 1400, 800, 30, False),
    ("Wooden Bed", 22000, 12500, 4, True),
    ("Bunk Bed", 18000, 10500, 3, True),
    ("Single Bed", 9500, 5200, 8, False),
    ("Wardrobe", 16000, 9000, 6, True),
    ("Bookshelf", 4800, 2700, 12, False),
    ("Study Table", 3600, 2000, 18, False),
    ("Kitchen Cabinet", 11000, 6200, 7, True),
    ("Door Frame", 1200, 700, 80, False),
    ("Window Frame", 950, 550, 100, False),
    ("Wooden Top (5ft)", 700, 380, 120, False),
    ("Wooden Top (6ft)", 850, 450, 100, False),
    ("Wooden Legs", 120, 80, 600, False),
    ("Cushion (foam)", 250, 130, 400, False),
    ("Upholstery Fabric (m)", 180, 90, 800, False),
    ("Hinges (pack)", 90, 50, 1500, False),
    ("Screws (pack)", 5, 3, 5000, False),
    ("Brackets (pack)", 35, 18, 1200, False),
    ("LED Strip (m)", 220, 130, 500, False),
    ("Glass Panel", 850, 450, 60, False),
    ("Mirror", 1400, 760, 30, False),
]
_FINISHES = ["Walnut", "Teak", "Oak", "Mahogany", "Pine", "Cherry", "Rosewood", "Beech", "Birch", "Cedar"]
_SIZES = ["Small", "Medium", "Large", "Compact", "Standard", "Premium", "Classic", "Deluxe"]


def generate_products(count=500):
    """A long catalogue: base type × finish × size, varying prices around the base."""
    out = []
    used = set()
    for _ in range(count):
        base, sp, cp, on_hand, prefers_mto = _RNG.choice(_PRODUCT_TYPES)
        for _try in range(5):
            finish = _RNG.choice(_FINISHES)
            size = _RNG.choice(_SIZES)
            name = f"{size} {finish} {base}"
            if name not in used:
                used.add(name); break
        # ±20% price variation
        var = 1 + _RNG.uniform(-0.2, 0.2)
        entry = {
            "name": name,
            "sales_price": round(sp * var, 2),
            "cost_price": round(cp * var * 0.9, 2),  # margin
            "on_hand_qty": _RNG.randint(0, max(1, on_hand * 2)),
            "procure_on_demand": False,
        }
        # Some bigger items default to MTO so procurement actually fires later
        if prefers_mto and _RNG.random() < 0.3:
            entry["procure_on_demand"] = True
            entry["procure_method"] = "manufacturing"  # vendor/bom resolved at seed time
        out.append(entry)
    return out


# ---------- orders ----------
SO_STATUSES = ["draft", "confirmed", "partially_delivered", "fully_delivered", "cancelled"]
PO_STATUSES = ["draft", "confirmed", "partially_received", "fully_received", "cancelled"]
MO_STATUSES = ["draft", "confirmed", "in_progress", "done", "cancelled"]


def generate_sales_orders(count, customer_names, product_names, salesperson_logins):
    """One SO per row; lines 1-4 products at random qty 1-15; status weighted to realistic mix."""
    out = []
    status_weights = [0.10, 0.30, 0.10, 0.40, 0.10]   # most are delivered
    for _ in range(count):
        status = _RNG.choices(SO_STATUSES, weights=status_weights, k=1)[0]
        line_count = _RNG.randint(1, 4)
        lines = []
        seen = set()
        for _ in range(line_count):
            for _try in range(5):
                p = _RNG.choice(product_names)
                if p not in seen: seen.add(p); break
            ordered = _RNG.randint(1, 15)
            if status == "fully_delivered":
                delivered = ordered
            elif status == "partially_delivered":
                delivered = _RNG.randint(1, max(1, ordered - 1))
            else:
                delivered = 0
            lines.append({"product": p, "ordered_qty": ordered, "delivered_qty": delivered})
        out.append({
            "customer": _RNG.choice(customer_names),
            "salesperson": _RNG.choice(salesperson_logins),
            "status": status,
            "created_offset_days": _RNG.randint(-60, 0),
            "lines": lines,
        })
    return out


def generate_purchase_orders(count, vendor_names, product_names, responsible_logins):
    out = []
    status_weights = [0.10, 0.25, 0.10, 0.45, 0.10]
    for _ in range(count):
        status = _RNG.choices(PO_STATUSES, weights=status_weights, k=1)[0]
        line_count = _RNG.randint(1, 3)
        lines = []
        seen = set()
        for _ in range(line_count):
            for _try in range(5):
                p = _RNG.choice(product_names)
                if p not in seen: seen.add(p); break
            ordered = _RNG.randint(20, 500)
            if status == "fully_received":
                received = ordered
            elif status == "partially_received":
                received = _RNG.randint(10, max(11, ordered - 10))
            else:
                received = 0
            lines.append({"product": p, "ordered_qty": ordered, "received_qty": received})
        out.append({
            "vendor": _RNG.choice(vendor_names),
            "responsible": _RNG.choice(responsible_logins),
            "status": status,
            "created_offset_days": _RNG.randint(-90, -1),
            "lines": lines,
        })
    return out


def generate_manufacturing_orders(count, bom_names, assignee_logins):
    """MOs are anchored to existing BoMs (so the inventory math works)."""
    if not bom_names:
        return []
    out = []
    status_weights = [0.10, 0.25, 0.20, 0.40, 0.05]
    for _ in range(count):
        status = _RNG.choices(MO_STATUSES, weights=status_weights, k=1)[0]
        bom_name = _RNG.choice(bom_names)
        out.append({
            "finished_product": bom_name,     # bom_name == finished product name in our seed
            "bom": bom_name,
            "quantity": _RNG.randint(2, 20),
            "assignee": _RNG.choice(assignee_logins),
            "status": status,
            "created_offset_days": _RNG.randint(-45, -1),
            "schedule_offset_days": _RNG.randint(-15, 30),
        })
    return out
