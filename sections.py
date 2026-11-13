"""Sort each posting into a section: events, quant, swe, hardware, finance, or other.

Rules are checked in order and the first match wins, so "Quantitative Developer" is quant (not
SWE) and "Technology Summer Analyst" is SWE (not finance). Simplify's own category is used
when the title alone doesn't decide it.
"""
import re

LABELS = {
    "swe": "SWE", "quant": "Quant", "finance": "Finance", "hardware": "Hardware",
    "events": "Event / program", "other": "Other",
}

# Company-sponsored programs and events: insight weeks, sophomore programs, summits, etc.
EVENTS = re.compile(
    r"insight (program|week|day|series)|early insights?|discovery (day|program)|summit|spring week"
    r"|sophomore|freshman|first[- ]year|explore (program|microsoft)|externship"
    r"|info(rmation)? session|open house|hackathon|virtual experience|bootcamp"
    r"|diversity (program|forum)|women in (tech|finance|business|stem)|launch(ing)? (program|leaders)"
    r"|career fair|pre[- ]internship|sponsors for educational opportunity|possibilities", re.I)

RULES = [
    ("quant", r"quant|trading|trader|\bstrats?\b|market making"),
    ("swe", r"software|back[- ]?end|full[- ]?stack|front[- ]?end|\bswe\b|developer|data (scien|engineer|analy)"
            r"|machine learning|\bml\b|\bai\b|platform|infrastructure|cloud|devops|\bsre\b|site reliability"
            r"|cyber|security engineer|computer science|technology|engineering intern"),
    ("hardware", r"hardware|electrical|mechanical|asic|fpga|vlsi|silicon|embedded|firmware|\brf\b|circuit"
                 r"|semiconductor|robotics|\bcad\b"),
    ("finance", r"financ|investment bank|banking|\bib\b|analyst|accounting|fp&a|treasury|wealth"
                r"|asset management|private equity|capital markets|markets|risk|audit|actuar|research"),
]
RULES = [(name, re.compile(p, re.I)) for name, p in RULES]

SIMPLIFY_CATEGORIES = {
    "Software": "swe", "Software Engineering": "swe", "AI/ML/Data": "swe",
    "Data Science, AI & Machine Learning": "swe", "Quant": "quant", "Hardware": "hardware",
}


def section_of(job):
    title = job["title"]
    if is_event(title):
        return "events"
    if job.get("category") in SIMPLIFY_CATEGORIES:
        # Simplify's category is reliable, but a quant title still beats a generic "Software" label
        quant = RULES[0][1].search(title)
        return "quant" if quant else SIMPLIFY_CATEGORIES[job["category"]]
    for name, pattern in RULES:
        if pattern.search(title):
            return name
    return "other"


SENIOR = re.compile(r"\b(senior|sr\.?|manager|director|principal|staff|lead|head of|vice president|vp)\b", re.I)


def is_event(title):
    """A student program/event, not a staff job that mentions one ("Discovery Program Manager")."""
    return bool(EVENTS.search(title)) and not SENIOR.search(title)
