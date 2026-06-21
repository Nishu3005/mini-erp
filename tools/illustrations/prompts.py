"""Per-page prompt seeds for the illustration generator.

Shared style brief (every page inherits it). The PER-PAGE list of scene seeds gives the model a
different starting concept each run so we don't regenerate the same composition. The generator
varies the seed phrase + a small random twist for uniqueness.
"""

STYLE = (
    "hand-drawn line art illustration, friendly editorial style, "
    "thin dark green ink outlines on warm off-white background, "
    "loose pencil-like sketch texture, generous negative space, "
    "soft yellow brush-stroke accent shape behind the subject "
    "(like a highlighter mark), landscape orientation 16:9, "
    "no text, no logo, no signature, no watermark. "
    "Vibe: warm, human, hand-made — never corporate, never 3D."
)

# Per-page scene seeds (cycle through; the script appends an index + style brief)
SCENES = {
    "dashboard": [
        "a small team of five furniture workers walking together with notebooks and laptops",
        "a clipboard, a tape measure and a coffee mug on a workshop table at sunrise",
        "a desk with stacked invoices, a pencil and a potted plant in soft morning light",
    ],
    "sales": [
        "a salesperson handing a furniture catalogue to a smiling customer in a showroom",
        "two people shaking hands beside a wooden dining table",
        "a customer reviewing a delivery slip while a chair is unboxed",
    ],
    "purchase": [
        "a warehouse worker checking a stack of timber planks against a clipboard",
        "a forklift driver placing wrapped pallets on a shelf",
        "a vendor and buyer reviewing a paper purchase order at a loading dock",
    ],
    "manufacturing": [
        "a carpenter sanding a wooden chair leg in a sunlit workshop",
        "two workers assembling a wooden table together with hand tools",
        "an apron-wearing craftsperson sketching a furniture design at a workbench",
    ],
    "bom": [
        "an exploded-view technical drawing of a wooden chair with parts labelled by hand",
        "a notebook page with sketches of table joinery and bracket dimensions",
        "neat rows of wooden components laid out before assembly",
    ],
    "product": [
        "a curated row of furniture pieces — chair, lamp, side table — drawn in line art",
        "an artisan polishing a finished wooden cabinet in warm light",
        "a small display of finished furniture with handwritten price tags",
    ],
    "audit": [
        "a magnifying glass over a long ledger sheet of handwritten entries",
        "a stack of bound notebooks with bookmarks sticking out the top",
        "an inspector with a clipboard examining a row of files on a shelf",
    ],
    "admin": [
        "a friendly office manager organising name cards on a noticeboard",
        "a row of diverse people in profile, like a small team portrait",
        "a circle of people of different professions standing together",
    ],
    "profile": [
        "a person sketching a self-portrait at a sunny desk",
        "a hand writing a name and details on a paper ID card",
        "a workshop badge with a small photograph and signature",
    ],
    "auth": [   # login / signup / pending
        "an open door at the entrance of a small workshop, soft morning light",
        "a paper key tag with a string, lying on a wooden table",
        "two people meeting at a desk, one offering a welcome card",
    ],
    "landing": [
        "a wide scene of a furniture workshop with people working together, illustrated",
        "an arrangement of furniture pieces and tools across a landscape composition",
    ],
    "errors": [
        "a confused craftsperson scratching their head holding a broken chair leg",
        "a paper sign on a closed workshop door that reads nothing (no text)",
    ],
}


def build_prompt(page: str, index: int) -> str:
    """Return the full prompt for page #index. Seeds wrap when index exceeds the seed list."""
    seeds = SCENES.get(page) or SCENES["dashboard"]
    scene = seeds[index % len(seeds)]
    twist = ["", " seen from a slight angle", " composed slightly off-centre",
             " with extra negative space around the subject"][index % 4]
    return f"{scene}{twist}. {STYLE}"
