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
    r"insights? (program|week|day|days|series|event)|early insights?|discovery (day|days|program|programme|event|week|series)"
    r"|(student|diversity|women|campus|career|leadership|insight|early careers?) summit|summit (program|series)|spring (week|insight|program)|winter (insight|program)|sophomore|freshman|first[- ]year|first[- ]gen"
    r"|rising (sophomore|junior)|explore (program|microsoft)|externship|info(rmation)? session|open (house|day)"
    r"|hackathon|datathon|virtual (experience|event|program)|boot ?camp|diversity (program|forum|summit)"
    r"|women in (tech|finance|business|stem|trading|quant)|launch(ing)? (program|leaders)|career fair"
    r"|pre[- ]internship|sponsors for educational opportunity|seo (career|scholar)|management leadership for tomorrow"
    r"|girls who invest|possibilities|(case|stock pitch|trading|quant|coding) (competition|challenge|game)"
    r"|webinar|fireside chat|tech talk|coffee chat|networking (event|night|session)|immersion (program|day|week)"
    r"|emerging (leaders|talent) program|early careers? (program|event|series)|scholarship|student fellowship"
    r"|fellowship program|academy program|trading (simulation|intensive)|intensive program|networking event",
    re.I)

RULES = [
    ("quant", r"quant|trading(?! cards?)|trader|\bstrats?\b|market making"),
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


SENIOR = re.compile(r"\b(senior|sr\.?|manager|director|principal|staff|lead|head of|vice president|vp"
                    r"|specialist|coordinator|strategist|recruiter|writer|planner)\b", re.I)


def is_event(title):
    """A student program/event, not a staff job that mentions one ("Discovery Program Manager")."""
    return bool(EVENTS.search(title)) and not SENIOR.search(title)
