"""
Wikidata property-ID → English label mapping.

The relbert/t_rex export carries most relations as bare PIDs (P17, P54, ...).
Bare PIDs are semantically opaque to LLM agents — a validator judging
"(Kermit Washington) --[P54]--> (Los Angeles Lakers)" cannot reason about
what P54 asserts. This map covers the 80 most frequent PIDs in the dataset
(~93% of PID-bearing records); unmapped PIDs pass through unchanged.

Labels follow official Wikidata English property labels.
"""

PID_LABELS: dict[str, str] = {
    "P17":   "country",
    "P54":   "member of sports team",
    "P27":   "country of citizenship",
    "P641":  "sport",
    "P131":  "located in the administrative territorial entity",
    "P106":  "occupation",
    "P31":   "instance of",
    "P569":  "date of birth",
    "P19":   "place of birth",
    "P161":  "cast member",
    "P47":   "shares border with",
    "P136":  "genre",
    "P570":  "date of death",
    "P20":   "place of death",
    "P1412": "language spoken or written",
    "P495":  "country of origin",
    "P1344": "participant in",
    "P150":  "contains administrative territorial entity",
    "P69":   "educated at",
    "P361":  "part of",
    "P57":   "director",
    "P166":  "award received",
    "P108":  "employer",
    "P279":  "subclass of",
    "P264":  "record label",
    "P463":  "member of",
    "P102":  "member of political party",
    "P171":  "parent taxon",
    "P39":   "position held",
    "P1303": "instrument",
    "P159":  "headquarters location",
    "P413":  "position played on team",
    "P118":  "league",
    "P364":  "original language of work",
    "P175":  "performer",
    "P400":  "platform",
    "P607":  "conflict",
    "P40":   "child",
    "P22":   "father",
    "P58":   "screenwriter",
    "P527":  "has part",
    "P26":   "spouse",
    "P36":   "capital",
    "P155":  "follows",
    "P127":  "owned by",
    "P101":  "field of work",
    "P105":  "taxon rank",
    "P3373": "sibling",
    "P156":  "followed by",
    "P190":  "twinned administrative body",
    "P162":  "producer",
    "P530":  "diplomatic relation",
    "P137":  "operator",
    "P103":  "native language",
    "P449":  "original broadcaster",
    "P241":  "military branch",
    "P1376": "capital of",
    "P403":  "mouth of the watercourse",
    "P1411": "nominated for",
    "P937":  "work location",
    "P138":  "named after",
    "P706":  "located on terrain feature",
    "P178":  "developer",
    "P123":  "publisher",
    "P206":  "located next to body of water",
    "P86":   "composer",
    "P140":  "religion",
    "P276":  "location",
    "P37":   "official language",
    "P50":   "author",
    "P1923": "participating team",
    "P112":  "founded by",
    "P1001": "applies to jurisdiction",
    "P30":   "continent",
    "P749":  "parent organization",
    "P53":   "family",
    "P647":  "drafted by",
    "P1346": "winner",
    "P740":  "location of formation",
    "P272":  "production company",
}


def label_for(predicate: str) -> str:
    """Map a bare PID to its English label; anything else passes through."""
    return PID_LABELS.get(predicate, predicate)
