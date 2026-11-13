"""Decide whether a job description says the company sponsors work visas.

This is keyword matching, not AI, so it can be wrong. That's why we also keep the exact
sentences that decided the label ("evidence") so you can check them yourself.

How it works: split the description into sentences, look only at sentences that talk about
sponsorship (or citizenship/clearance requirements), and check whether they're negated.
"""
import re

SPONSORS = "Sponsors"
NO_SPONSOR = "Does not sponsor"
UNSPECIFIED = "Not specified"

NEGATION = re.compile(
    r"\b(not|no|unable|cannot|can't|won't|don't|doesn't|ineligible|without|neither|nor)\b", re.I)
SPONSOR = re.compile(r"\bsponsor(ship|ed|s)?\b", re.I)
# Requirements that in practice rule out visa holders (clearances need citizenship).
CITIZENS_ONLY = re.compile(
    r"(must be a (u\.?s\.?|united states) citizen|(u\.?s\.?|united states) citizenship (is )?required"
    r"|security clearance)", re.I)
OPTIONAL = re.compile(r"\b(not required|a plus|beneficial|preferred|nice to have|bonus)\b", re.I)
# Not a label on its own, but worth showing to international students.
CPT_OPT = re.compile(r"\b(CPT|OPT|STEM extension)\b")


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def classify(text):
    """Returns (label, evidence)."""
    no, yes, notes = [], [], []
    for s in _sentences(text or ""):
        if SPONSOR.search(s):
            (no if NEGATION.search(s) else yes).append(s)
        elif CITIZENS_ONLY.search(s) and not OPTIONAL.search(s):
            no.append(s)
        if CPT_OPT.search(s) and s not in no + yes:
            notes.append(s)

    if no:
        label, evidence = NO_SPONSOR, no[:1]
    elif yes:
        label, evidence = SPONSORS, yes[:1]
    else:
        label, evidence = UNSPECIFIED, []
    return label, " … ".join(s[:250] for s in evidence + notes[:1])
