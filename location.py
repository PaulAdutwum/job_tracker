"""Decide whether a job is in the United States.

Platforms write locations very differently ("New York, NY", "US, CA, Santa Clara",
"San Francisco, Seattle, New York City", "Remote (US)"), so we look for any US signal:
the platform's country field, the words "United States"/"US", a state code or name,
or a major US city. Multi-location jobs count as US if any location is in the US.
"""
import re

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
US_CITIES = [
    "san francisco", "new york city", "nyc", "seattle", "boston", "chicago", "austin",
    "los angeles", "palo alto", "mountain view", "menlo park", "sunnyvale", "santa clara",
    "san jose", "san diego", "denver", "atlanta", "miami", "dallas", "houston", "pittsburgh",
    "philadelphia", "bellevue", "redmond", "salt lake city", "raleigh", "phoenix",
    "minneapolis", "detroit", "nashville", "boulder", "irvine", "cupertino", "redwood city",
    "san mateo", "brooklyn",
]
US_COUNTRY_VALUES = {"us", "usa", "united states", "united states of america"}

US_WORDS = re.compile(r"(?<![A-Za-z])(united states|usa|u\.s\.a?\.?|us)(?![A-Za-z])", re.I)
STATE_CODES = re.compile(r"(?:,|\s-)\s*(" + "|".join(STATES) + r")(?![A-Za-z])")  # case-sensitive
STATE_NAMES = re.compile(r"\b(" + "|".join(STATES.values()) + r")\b", re.I)
CITIES = re.compile(r"\b(" + "|".join(US_CITIES) + r")\b", re.I)


def is_us(location, country=None):
    if country and country.strip().lower() in US_COUNTRY_VALUES:
        return True
    text = location or ""
    return any(p.search(text) for p in (US_WORDS, STATE_CODES, STATE_NAMES, CITIES))
