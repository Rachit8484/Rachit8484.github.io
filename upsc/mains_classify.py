"""Keyword-based subject/topic classifier for UPSC Mains questions.

The UPSC Mains syllabus doesn't come with canonical topic tags per question,
so this module applies an editorial taxonomy — reusing Prelims subjects where
they overlap, and adding Mains-only ones (Indian Society, Ethics, Essay).

Classification is a weighted keyword match. Each (subject, topic) pair has a
keyword list; a question scores 1 point per keyword hit. The highest-scoring
pair wins. Ties are broken by keyword specificity (length).

If no keyword matches, we fall back to the paper's default bucket
(e.g. GS-II → Indian Polity and Governance / Governance).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# ───────────────────────── taxonomy ─────────────────────────

# Each tuple: (paper_restriction, subject, topic, [keywords]).
# paper_restriction may be a set of papers, or None = any paper.
# Keywords are matched case-insensitively as whole-word substrings where
# reasonable; multi-word keywords are matched as-is.


TAXONOMY: list[tuple[set[str] | None, str, str, list[str]]] = [
    # ─────────── GS-I : History, Society, Geography, Art & Culture ───────────
    # Ancient India
    ({"GS-I"}, "Ancient India", "Prehistoric Period and Indus Valley Civilisation",
     ["indus valley", "harappan", "mohenjo", "prehistoric", "stone age", "chalcolithic"]),
    ({"GS-I"}, "Ancient India", "Vedic and Later Vedic Age",
     ["rig vedic", "rigveda", "vedic age", "later vedic", "vedic period", "aryans"]),
    ({"GS-I"}, "Ancient India", "Mauryan and Post-Mauryan Age",
     ["mauryan", "maurya", "ashoka", "kushana", "gupta"]),
    ({"GS-I"}, "Ancient India", "Gupta and Post-Gupta Age",
     ["gupta empire", "post-gupta", "harshavardhana", "kannauj"]),
    ({"GS-I"}, "Ancient India", "Sangam Age",
     ["sangam", "pallava", "pallavas", "kanchi", "chola", "cholas", "chera", "pandya", "satavahana"]),
    # Medieval India
    ({"GS-I"}, "Medieval India", "Delhi Sultanate (1206 AD to 1526 AD)",
     ["delhi sultanate", "khilji", "tughlaq", "slave dynasty", "lodi"]),
    ({"GS-I"}, "Medieval India", "Mughal Empire (1526 AD to 1761 AD)",
     ["mughal", "akbar", "aurangzeb", "shah jahan", "jahangir", "babur", "humayun"]),
    ({"GS-I"}, "Medieval India", "Provincial Kingdoms in Medieval India",
     ["vijayanagar", "bahmani", "chandella", "chandela", "rajput", "marathas", "shivaji"]),
    ({"GS-I"}, "Medieval India", "Religious Movement during Medieval Period",
     ["bhakti", "sufi", "kabir", "guru nanak", "chaitanya", "alvars"]),
    # Art & Culture
    ({"GS-I"}, "Art & Culture", "Architecture and Sculpture",
     ["architecture", "sculpt", "temple", "stupa", "harappan", "rock-cut", "dravidian", "nagara", "mandir",
      "lion and bull", "mythology", "monument"]),
    ({"GS-I"}, "Art & Culture", "Performing Arts: Dance, Theatre, and Music",
     ["dance", "music", "classical dance", "bharatanatyam", "kathakali", "theatre", "natyashastra"]),
    ({"GS-I"}, "Art & Culture", "Visual Arts: Painting, Ceramics, and Drawing",
     ["painting", "miniature", "mural", "fresco", "ceramics"]),
    ({"GS-I"}, "Art & Culture", "Literature: Religious and Scientific",
     ["sanskrit literature", "bhakti literature", "tamil literature", "persian literature", "puranas", "upanishad"]),
    ({"GS-I"}, "Art & Culture", "Indian Philosophy and Bhakti & Sufi Movements",
     ["philosophy", "darshana", "mimamsa", "vedanta", "yoga", "buddhism", "jainism"]),
    ({"GS-I"}, "Art & Culture", "Indian Traditions, Festivals, and Calendars",
     ["festival", "tradition", "calendar", "ritual"]),
    ({"GS-I"}, "Art & Culture", "Ancient Society & Vedic Traditions",
     ["vedic society", "vedic religion", "vedic age society", "features of vedic"]),
    ({"GS-I"}, "Art & Culture", "Sultanate-era Technology & Culture",
     ["sultanate period", "technological changes", "sultanate"]),
    # Modern India (Freedom Struggle)
    ({"GS-I"}, "Modern India", "Early Uprising Against the British and Revolt of 1857",
     ["1857", "revolt of 1857", "sepoy", "mangal pandey", "rani lakshmibai"]),
    ({"GS-I"}, "Modern India", "Rise of Indian National Movement: Moderate and Extremists Phase",
     ["moderate", "moderates", "extremist", "indian national congress", "tilak", "gokhale", "early congress",
      "freedom movement"]),
    ({"GS-I"}, "Modern India", "The Beginning of Gandhian Era",
     ["gandhian", "non-cooperation", "civil disobedience", "champaran", "satyagraha", "salt march", "dandi"]),
    ({"GS-I"}, "Modern India", "The National Movement in the 1940s",
     ["quit india", "1942", "cripps", "cabinet mission", "interim government", "ina", "subhas chandra"]),
    ({"GS-I"}, "Modern India", "Phases of Revolutionary Nationalism",
     ["revolutionary", "bhagat singh", "ghadar", "chandrashekhar azad"]),
    ({"GS-I"}, "Modern India", "Indian Renaissance and Reform Movements",
     ["renaissance", "ram mohan", "brahmo", "arya samaj", "social reform"]),
    ({"GS-I"}, "Modern India", "Independence to Partition",
     ["partition", "two-nation", "mountbatten", "transfer of power"]),
    ({"GS-I"}, "Modern India", "Development of Press, Education, and Civil Services",
     ["press", "newspaper", "education system", "macaulay", "civil services", "wood's despatch"]),
    ({"GS-I"}, "Modern India", "Colonial Economy & Society",
     ["colonial india", "colonial rule", "colonial era", "colonial administration", "british rule",
      "famines in colonial", "railways in", "introduction of railways", "economic drain",
      "deindustrialisation", "deindustrialization"]),
    # Post-independence (new topic for Mains)
    ({"GS-I"}, "Modern India", "Post-independence Consolidation",
     ["post-independence", "post independence", "integration of states", "linguistic reorganization",
      "linguistic reorganisation", "reorganization of states", "reorganisation of states",
      "princely states", "integration of indian princely", "consolidation process", "consolidation of india",
      "india's consolidation", "indian states"]),
    # World History
    ({"GS-I"}, "World History", "Industrial Revolution and Colonialism",
     ["industrial revolution", "imperialism", "scramble for africa"]),
    ({"GS-I"}, "World History", "World Wars and Post-War Order",
     ["world war", "first world war", "second world war", "cold war", "league of nations", "versailles"]),
    ({"GS-I"}, "World History", "Revolutions (French, Russian, American, Chinese)",
     ["french revolution", "russian revolution", "american revolution", "chinese revolution", "bolshevik"]),
    ({"GS-I"}, "World History", "Decolonisation and Nationalism",
     ["decolonisation", "decolonization", "end of apartheid", "non-aligned"]),
    # Indian Society
    ({"GS-I"}, "Indian Society", "Women, Gender & Empowerment",
     ["women", "gender", "female", "patriarchy", "empowerment", "feminist", "matrimon", "girl child",
      "gender justice", "gender equity", "challenges for women"]),
    ({"GS-I"}, "Indian Society", "Population, Urbanisation & Migration",
     ["population", "urbanisation", "urbanization", "migration", "migrant", "migrants", "demographic",
      "slums", "large cities", "smaller towns", "rural-urban"]),
    ({"GS-I"}, "Indian Society", "Poverty, Inequality, and Social Justice",
     ["poverty", "inequality", "marginal", "dalit", "tribal", "sc/st", "untouchab", "reservation",
      "affirmative action", "underprivileged", "regional disparity", "socio-economic marginalit",
      "disparities", "human development"]),
    ({"GS-I"}, "Indian Society", "Communalism, Regionalism, Secularism",
     ["communal", "communalism", "regionalism", "secular", "secularism", "religious identity"]),
    ({"GS-I"}, "Indian Society", "Family, Marriage & Social Institutions",
     ["family", "marriage", "divorce", "joint family", "kinship", "caste system", "caste identity",
      "intercaste", "sect", "socialization", "socialisation"]),
    ({"GS-I"}, "Indian Society", "Globalization and its Impact",
     ["globalization", "globalisation", "cultural impact", "consumerism"]),
    ({"GS-I"}, "Indian Society", "Technology, Media & Social Change",
     ["mobile phone", "mobile phones", "social media", "IT industries", "cryptocurrency",
      "child cuddling", "fast food", "health concerns", "modern society"]),
    # World Geography
    ({"GS-I"}, "World Geography", "Geomorphology",
     ["plate tectonic", "volcano", "earthquake", "mountain", "folding", "faulting",
      "primary rocks", "types of rocks"]),
    ({"GS-I"}, "World Geography", "Climatology",
     ["climate", "monsoon", "el nino", "la nina", "cyclone", "precipitation", "jet stream",
      "troposphere", "atmospheric layer", "weather processes", "cloudburst"]),
    ({"GS-I"}, "World Geography", "Oceanography",
     ["ocean current", "tides", "fjord", "fjords", "ocean salinity", "marine", "ocean",
      "gulf of mexico", "tsunami", "tsunamis", "strait", "straits", "isthmus", "coastline"]),
    ({"GS-I"}, "World Geography", "Human and Economic Geography",
     ["industrial location", "human geography", "world population", "world resources",
      "off-shore oil", "oil reserves", "rubber producing", "non-farm primary",
      "distribution of", "international trade", "economic geography"]),
    ({"GS-I"}, "World Geography", "The Earth and the Universe",
     ["aurora", "universe", "solar system", "galaxy", "magnetosphere", "magnetism"]),
    ({"GS-I"}, "World Geography", "World Climatic Regions",
     ["tropical", "equatorial climate", "desert region", "tundra", "mediterranean climate",
      "twister", "tornado"]),
    # Indian Geography
    ({"GS-I"}, "Indian Geography", "Physiography of India",
     ["himalaya", "western ghat", "eastern ghat", "deccan", "plateau", "coast of india",
      "physiographic", "physiography", "indian coastline", "coastal india"]),
    ({"GS-I"}, "Indian Geography", "Indian Climate",
     ["indian monsoon", "south-west monsoon", "purvaiya", "indian climate"]),
    ({"GS-I"}, "Indian Geography", "Drainage System of India",
     ["ganga", "gangetic", "godavari", "krishna", "narmada", "yamuna", "river system",
      "groundwater potential", "groundwater in india"]),
    ({"GS-I"}, "Indian Geography", "Agriculture in India",
     ["cropping pattern", "agricultural region", "indian agriculture", "food importer",
      "food exporter", "net food"]),
    ({"GS-I"}, "Indian Geography", "Mineral and Industries",
     ["mineral resources", "iron ore", "coal", "steel industry", "cotton industry", "heavy industry",
      "mining industry", "gondwanaland", "gondwana", "IT industry in india"]),
    ({"GS-I"}, "Indian Geography", "Natural Vegetation in India",
     ["forest", "vegetation", "mangrove", "sal", "teak"]),
    ({"GS-I"}, "Indian Geography", "Soils",
     ["soil", "alluvial", "laterite", "black soil", "red soil"]),
    ({"GS-I"}, "Indian Geography", "Coastal & Island Geography",
     ["coastal erosion", "coastal management", "coastal areas", "coastal hazard", "island"]),
    ({"GS-I"}, "Indian Geography", "Energy & Resource Geography",
     ["solar energy generation", "ecological and economic benefits", "renewable energy sources",
      "electric energy"]),

    # ─────────── GS-II : Polity, Governance, IR ───────────
    ({"GS-II"}, "Indian Polity and Governance", "Historical Background & Making of Indian Constitution",
     ["constituent assembly", "government of india act", "drafting committee", "objectives resolution"]),
    ({"GS-II"}, "Indian Polity and Governance", "Features of the Indian Constitution",
     ["basic structure", "preamble", "fundamental right", "directive principle", "amendment", "schedule",
      "article 21", "article 356", "right to privacy", "personal liberty", "right of movement",
      "constitutional perspective", "constitution of india is a living"]),
    ({"GS-II"}, "Indian Polity and Governance", "Legislature",
     ["parliament", "lok sabha", "rajya sabha", "legislature", "vice-president", "speaker", "anti-defection",
      "legislative assembly", "legislative council", "presiding officer", "state legislature",
      "parliamentary standing committee", "parliamentary control", "department-related"]),
    ({"GS-II"}, "Indian Polity and Governance", "Executive",
     ["president", "prime minister", "council of ministers", "cabinet", "bureaucra", "civil servant",
      "all india service", "presidents of india"]),
    ({"GS-II"}, "Indian Polity and Governance", "Judiciary",
     ["supreme court", "high court", "judicial", "judiciary", "pil", "public interest litigation"]),
    ({"GS-II"}, "Indian Polity and Governance", "Judicial & Quasi-Judicial Bodies",
     ["tribunal", "lok adalat", "arbitration", "lokpal", "lokayukta", "central vigilance",
      "competition commission", "CCI"]),
    ({"GS-II"}, "Indian Polity and Governance", "Constitutional and Non-constitutional Bodies",
     ["election commission", "comptroller and auditor general", "cag", "finance commission",
      "ncbc", "ncw", "nhrc", "nclat", "niti aayog",
      "human rights commission", "national commission for backward", "national commission for protection",
      "NCPCR", "child rights"]),
    ({"GS-II"}, "Indian Polity and Governance", "Local Self Government",
     ["panchayat", "panchayati raj", "municipal", "local bodies", "urban local", "73rd amendment", "74th amendment"]),
    ({"GS-II"}, "Indian Polity and Governance", "Centre-State Relations",
     ["centre-state", "federalism", "federal", "inter-state", "governor", "state list", "concurrent list",
      "jammu and kashmir reorganization", "union territory", "jammu and kashmir legislative"]),
    ({"GS-II"}, "Indian Polity and Governance", "Elections & Political Parties",
     ["election", "representation of the people act", "electoral", "political part",
      "model code of conduct", "voter"]),
    ({"GS-II"}, "Indian Polity and Governance", "Governance",
     ["governance", "e-governance", "citizens charter", "citizens' charter", "citizen-centric",
      "transparency", "accountability", "good governance", "service delivery",
      "direct benefit transfer", "DBT", "gati-shakti", "gati shakti"]),
    ({"GS-II"}, "Indian Polity and Governance", "RTI, RTE & Rights-based Legislation",
     ["right to information", "rti", "right to education", "rte", "right to food",
      "right of children to free and compulsory", "free and compulsory education"]),
    ({"GS-II"}, "Indian Polity and Governance", "Welfare Schemes for Vulnerable Sections",
     ["welfare scheme", "welfare state", "social justice", "scheduled caste", "scheduled tribe",
      "obc", "disabled", "persons with disabilit", "senior citizen", "transgender",
      "poverty", "malnutrition", "microfinance", "microfinancing", "self-help group", "shg",
      "vulnerable section", "marginalised", "marginalized"]),
    ({"GS-II"}, "Indian Polity and Governance", "Health, Education & Human Resources",
     ["public health", "healthcare", "education policy", "nep", "education system", "malnutrit",
      "human resource", "primary health", "vocational education", "skill training",
      "earn while you learn", "life expectancy", "telemedicine"]),
    ({"GS-II"}, "Indian Polity and Governance", "NGOs, Pressure Groups & Civil Society",
     ["ngo", "non-government", "civil society", "pressure group", "public charitable trust",
      "donor agencies", "community participation"]),
    ({"GS-II"}, "Indian Polity and Governance", "Women & Gender in Governance",
     ["women's social capital", "advancing empowerment", "women empowerment", "gender equity"]),
    ({"GS-II"}, "International Relations", "India & Its Neighbors",
     ["pakistan", "china", "bangladesh", "sri lanka", "nepal", "bhutan", "myanmar", "maldives",
      "afghanistan", "neighbour", "neighborhood"]),
    ({"GS-II"}, "International Relations", "India's Foreign Policy",
     ["foreign policy", "diaspora", "indian diaspora", "soft power", "sovereign nationalism",
      "waning of globalization", "waning of globalisation", "post-cold war"]),
    ({"GS-II"}, "International Relations", "International Groups and Political Organizations",
     ["united nations", "security council", "unsc", "g-20", "g20", "brics", "saarc", "bimstec", "asean",
      "sco", "wto", "imf", "world bank", "quad", "NATO", "IMO", "international maritime"]),
    ({"GS-II"}, "International Relations", "Bilateral & Regional Cooperation",
     ["bilateral", "strategic partnership", "russia", "united states", "usa", "european union",
      "japan", "israel", "iran", "central asia", "indo-pacific",
      "india-africa", "india and africa", "africa"]),
    ({"GS-II"}, "International Relations", "International Institutions & Law",
     ["international law", "treaty", "convention", "international court"]),

    # ─────────── GS-III : Economy, Agri, S&T, Env, Security ───────────
    ({"GS-III"}, "Indian Economy", "Growth, Development & Employment",
     ["economic growth", "gdp", "development", "employment", "unemployment", "inclusive growth",
      "jobless growth", "v-shaped", "recovery", "care economy", "monetized economy",
      "labour codes", "labor codes", "labour market", "labour reform", "labor reform"]),
    ({"GS-III"}, "Indian Economy", "Budgeting, Taxation & Public Finance",
     ["budget", "fiscal deficit", "taxation", "tax", "gst", "direct tax", "indirect tax",
      "subsidies", "subsidy", "fiscal health", "fiscal performance"]),
    ({"GS-III"}, "Indian Economy", "Banking, Finance & Monetary Policy",
     ["banking", "monetary policy", "rbi", "inflation", "repo rate", "non-performing", "npa", "currency"]),
    ({"GS-III"}, "Indian Economy", "Infrastructure & Investment",
     ["infrastructure", "investment", "fdi", "ppp", "public-private partnership", "capex",
      "regional air connectivity", "air connectivity", "udan", "PLI", "production linked"]),
    ({"GS-III"}, "Indian Economy", "External Sector & Trade",
     ["external sector", "balance of payments", "current account deficit", "exports",
      "free trade", "bilateralism", "protectionism", "multilateralism"]),
    ({"GS-III"}, "Indian Economy", "Industry & Services",
     ["manufacturing sector", "msme", "service sector", "industrial policy", "make in india"]),
    ({"GS-III"}, "Indian Economy", "Digitalization & New Economy",
     ["digitalization", "digitisation", "digital economy", "fintech", "e-commerce",
      "platform economy", "gig worker"]),
    ({"GS-III"}, "Indian Economy", "Agriculture — Cropping, Irrigation, Land",
     ["agriculture", "farmer", "cropping", "land reform", "irrigation", "msp", "minimum support price",
      "high value crop", "integrated farming", "e-technology", "e technology",
      "supply chain of agricultural", "marketing of agricultural", "upstream and downstream"]),
    ({"GS-III"}, "Indian Economy", "Food Security, PDS & Food Processing",
     ["food security", "public distribution system", "pds", "food processing", "buffer stock",
      "food inflation"]),
    ({"GS-III"}, "Indian Economy", "Animal Husbandry, Fisheries & Allied",
     ["animal husbandry", "dairy", "fisheries", "poultry", "livestock"]),
    ({"GS-III"}, "Science & Tech and Basic Science", "Space Science",
     ["space", "isro", "satellite", "launch vehicle", "chandrayaan", "gaganyaan", "mars orbit",
      "asteroids", "asteroid"]),
    ({"GS-III"}, "Science & Tech and Basic Science", "Nuclear & Energy Technology",
     ["nuclear", "atomic energy", "renewable energy", "solar energy", "wind energy",
      "hydrogen fuel", "clean energy", "fusion energy", "fusion programme",
      "blue LED", "LEDs"]),
    ({"GS-III"}, "Science & Tech and Basic Science", "Biotechnology & Health",
     ["biotechnology", "genetic", "dna", "gene therapy", "vaccine", "crispr", "mrna",
      "microorganism", "cellulose", "nanotechnology", "nano-technology"]),
    ({"GS-III"}, "Science & Tech and Basic Science", "IT, AI & Digital Technology",
     ["artificial intelligence", "ai ", "machine learning", "quantum computing", "5g", "6g",
      "blockchain", "internet of things", "semiconductor"]),
    ({"GS-III"}, "Science & Tech and Basic Science", "Defence Technology",
     ["defence", "defense", "agni missile", "brahmos", "tejas", "indigenous",
      "unmanned aerial", "uav", "drones"]),
    ({"GS-III"}, "Environment & Ecology and Disaster Management", "Climate Change: Causes and Implications",
     ["climate change", "global warming", "carbon emission", "greenhouse",
      "paris agreement", "cop26", "cop27", "cop28", "net zero"]),
    ({"GS-III"}, "Environment & Ecology and Disaster Management", "Biodiversity & Conservation",
     ["biodiversity", "wildlife", "endangered species", "tiger reserve", "elephant",
      "national park", "sanctuary", "ramsar"]),
    ({"GS-III"}, "Environment & Ecology and Disaster Management", "Environmental Pollution",
     ["pollution", "air quality", "water pollution", "plastic", "waste", "solid waste",
      "photochemical smog", "smog", "gothenburg protocol", "clean air programme", "NCAP"]),
    ({"GS-III"}, "Environment & Ecology and Disaster Management", "Disaster Management",
     ["disaster", "cyclone", "flood", "earthquake", "landslide", "ndma", "disaster management",
      "dam failure", "dam failures", "cloudburst", "coastal erosion"]),
    ({"GS-III"}, "Environment & Ecology and Disaster Management", "Environment — Sustainable Development & Policy",
     ["sustainable development", "sdg", "eia", "environmental impact", "forest conservation",
      "jal shakti", "water conservation", "freshwater", "seawater intrusion", "groundwater depletion",
      "mining as environmental hazard"]),
    ({"GS-III"}, "Internal Security", "Extremism, Terrorism & LWE",
     ["terror", "terrorism", "extremism", "naxal", "naxalism", "maoist", "left wing extremism",
      "insurgency", "no money for terror"]),
    ({"GS-III"}, "Internal Security", "Border Management & External Threats",
     ["border management", "india-china border", "line of actual control", "line of control",
      "lac", "loc", "cross-border", "external state and non"]),
    ({"GS-III"}, "Internal Security", "Cybersecurity & Data",
     ["cyber", "cybersecurity", "data protection", "cyber attack", "cybercrime"]),
    ({"GS-III"}, "Internal Security", "Money Laundering & Organised Crime",
     ["money laundering", "organised crime", "human trafficking", "narcotic", "drug traffick",
      "terror funding"]),
    ({"GS-III"}, "Internal Security", "Security Forces & Agencies",
     ["paramilitary", "armed forces", "central armed police", "intelligence bureau", "raw ",
      "national security", "central intelligence", "investigative agencies"]),
    ({"GS-III"}, "Internal Security", "Maritime & Regional Security",
     ["maritime security", "sea trade", "coastal security", "north-eastern states", "north-east"]),
    ({"GS-III"}, "Indian Economy", "Pandemic & Crisis Response",
     ["covid-19", "covid", "pandemic"]),

    # ─────────── GS-IV : Ethics ───────────
    ({"GS-IV"}, "Ethics and Integrity", "Theoretical Foundations of Ethics",
     ["ethics", "morality", "moral philosophy", "values", "virtue", "consequentialism", "deontolog",
      "moral intuition", "moral reasoning", "conscience", "just and unjust",
      "teachings of mahavir", "teachings of guru nanak", "teachings of", "mahavir", "guru nanak"]),
    ({"GS-IV"}, "Ethics and Integrity", "Attitude & Emotional Intelligence",
     ["attitude", "emotional intelligence", "empathy", "compassion", "perseverance",
      "emotional skills", "emotional quotient", "EQ"]),
    ({"GS-IV"}, "Ethics and Integrity", "Aptitude & Foundational Values",
     ["aptitude", "integrity", "objectivity", "dedication", "impartial", "non-partisan",
      "sense of responsibility", "personal fulfilment", "devoted to one's duty",
      "social capital"]),
    ({"GS-IV"}, "Ethics and Integrity", "Ethics in Public Administration",
     ["public service", "civil servant", "administrat", "bureaucrac", "citizen-centric",
      "transparency", "probity", "good governance", "e-governance", "BNS",
      "bharatiya nyaya sanhita", "rational decision-making", "work culture", "work environment",
      "coercion", "undue influence"]),
    ({"GS-IV"}, "Ethics and Integrity", "Corporate Governance & Professional Ethics",
     ["corporate governance", "professional ethics", "whistleblow", "conflict of interest",
      "corporate social responsibility", "pharmaceutical", "pharmaceuticals company", "CEO",
      "chief executive officer"]),
    ({"GS-IV"}, "Ethics and Integrity", "Probity, Corruption & Accountability",
     ["corruption", "accountability", "probity", "code of conduct", "lokpal", "quality of service", "rti"]),
    ({"GS-IV"}, "Ethics and Integrity", "Ethics in Society, Media & Technology",
     ["social media", "digital age", "online methodology", "telemedicine",
      "ethical dilemma", "ethical dilemmas", "digital era"]),
    ({"GS-IV"}, "Ethics and Integrity", "Environment & Security Ethics",
     ["environmental clearance", "ecologically sensitive", "global warming and climate",
      "national security", "war is", "weapon industries", "russia and ukraine",
      "geo-political", "clausewitz"]),
    ({"GS-IV"}, "Ethics and Integrity", "Philosophical Quotations & Thinkers",
     ["quotations", "quotation", "thinkers", "vivekananda", "sardar patel", "thiruvalluvar",
      "awaken the people", "simplest acts", "hatred", "learn everything",
      "what really matters for success", "discovery of my generation",
      "greatest discovery", "wisdom lies in knowing", "knowing the difference",
      "father, mother and teacher", "three key societal"]),
    ({"GS-IV"}, "Ethics and Integrity", "Case Studies",
     ["case study", "you are", "officer heading", "you receive", "you find", "your colleague",
      "dilemma", "what would you do", "options available", "course of action",
      "you are the", "as the chief", "company known", "infectious disease",
      "spreading disease", "you find yourself"]),

    # ─────────── Essay ───────────
    ({"Essay"}, "Essay", "Philosophy, Values & Human Nature",
     ["happiness", "wisdom", "wantlessness", "desire", "virtue", "soul", "consciousness",
      "thought", "mind", "smile", "ambiguities", "poets", "unacknowledged legislators",
      "muddy water", "years teach", "ideas", "thinking", "visionary", "creativity",
      "magical", "step twice", "cost of being wrong", "bitter experiences",
      "supreme art of war", "subdue the enemy"]),
    ({"Essay"}, "Essay", "Society, Culture & Gender",
     ["women", "society", "culture", "family", "tradition", "community", "inequality",
      "girls are weighed", "restrictions", "boys with demands"]),
    ({"Essay"}, "Essay", "Education, Knowledge & Science",
     ["education", "knowledge", "science", "mathematics", "research", "doubter", "curiosity",
      "scientific man", "romantic man", "history is a series"]),
    ({"Essay"}, "Essay", "Economy, Development & Governance",
     ["economy", "development", "governance", "power", "leadership", "authority",
      "adversity", "test the character", "character, give him power"]),
    ({"Essay"}, "Essay", "Environment & Sustainability",
     ["forests", "environment", "nature", "sustainab", "climate"]),
    ({"Essay"}, "Essay", "Media, Technology & Society",
     ["social media", "media", "technology", "artificial intelligence", "digital", "internet"]),
]


# Compile: pre-lower all keywords once.
_RULES: list[tuple[set[str] | None, str, str, list[tuple[re.Pattern, int]]]] = []
for papers, subject, topic, kws in TAXONOMY:
    compiled: list[tuple[re.Pattern, int]] = []
    for kw in kws:
        # Word-boundary match for single-word ASCII kws; substring for multi-word/hyphenated.
        if " " in kw or "-" in kw or "/" in kw:
            pat = re.compile(re.escape(kw), re.IGNORECASE)
        else:
            pat = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        compiled.append((pat, len(kw)))
    _RULES.append((papers, subject, topic, compiled))


# Fallback default per paper.
_FALLBACK: dict[str, tuple[str, str]] = {
    "GS-I":   ("Indian Society",              "Miscellaneous"),
    "GS-II":  ("Indian Polity and Governance", "Governance"),
    "GS-III": ("Indian Economy",              "Growth, Development & Employment"),
    "GS-IV":  ("Ethics and Integrity",        "Case Studies"),
    "Essay":  ("Essay",                        "Philosophy, Values & Human Nature"),
}


@dataclass
class Classification:
    subject: str
    topic: str
    score: int


def classify(question: str, paper: str) -> Classification:
    """Return the best-matching (subject, topic) for a question.

    Tie-breakers: (1) higher total keyword length, (2) rule order.
    """
    best_score = 0
    best_specificity = 0
    best_subject: str | None = None
    best_topic: str | None = None
    for papers, subj, topic, kws in _RULES:
        if papers is not None and paper not in papers:
            continue
        score = 0
        specificity = 0
        for pat, length in kws:
            hits = len(pat.findall(question))
            if hits:
                score += hits
                specificity += length * hits
        if score > best_score or (score == best_score and specificity > best_specificity):
            best_score = score
            best_specificity = specificity
            best_subject = subj
            best_topic = topic
    if best_score == 0:
        subj, topic = _FALLBACK.get(paper, ("Uncategorised", "Miscellaneous"))
        return Classification(subject=subj, topic=topic, score=0)
    return Classification(subject=best_subject, topic=best_topic, score=best_score)


def classify_batch(questions: Iterable[tuple[str, str]]) -> list[Classification]:
    """Bulk helper: yields a Classification for each (question, paper)."""
    return [classify(q, p) for q, p in questions]
