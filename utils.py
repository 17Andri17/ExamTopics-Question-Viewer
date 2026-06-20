import re

# Helpers for working with questions across topics.
#
# ExamTopics encodes the topic inside each discussion link, e.g.
#   .../view/384735-exam-cis-df-topic-5-question-1-discussion/
# The same question_number can therefore appear under several different
# topics, so navigation and search must key on (topic, question_number)
# rather than question_number alone.

_TOPIC_RE = re.compile(r"topic-(\d+)-question-\d+")


def get_topic(question):
    """Return the topic number for a question as a string.

    Falls back to "1" for exams whose links don't encode a topic
    (e.g. AWS SAA-C03), which behave as a single-topic exam.
    """
    link = question.get("link", "") or ""
    match = _TOPIC_RE.search(link)
    return match.group(1) if match else "1"


def _as_int(value, default=10 ** 9):
    """Best-effort int conversion that keeps non-numeric values last."""
    return int(value) if str(value).isdigit() else default


def annotate_topics(questions):
    """Attach a parsed ``topic`` field to every question (in place)."""
    for question in questions:
        question["topic"] = get_topic(question)
    return questions


def sort_key(question):
    """Sort questions by topic, then by question number."""
    topic = question.get("topic") or get_topic(question)
    return (_as_int(topic), _as_int(question.get("question_number", "")))


def order_questions(questions):
    """Return questions ordered by (topic, question_number)."""
    return sorted(questions, key=sort_key)


def get_topics(questions):
    """Return the sorted list of distinct topics present in the questions."""
    topics = {q.get("topic") or get_topic(q) for q in questions}
    return sorted(topics, key=_as_int)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def plain_text(html):
    """Strip HTML tags and collapse whitespace for display/searching."""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


def search_questions(questions, query):
    """Return questions whose question text or answers contain ``query``.

    Matching is case-insensitive and ignores HTML markup. Results keep the
    order of ``questions`` (already sorted by topic then number).
    """
    needle = (query or "").strip().lower()
    if not needle:
        return []
    matches = []
    for q in questions:
        haystack = plain_text(q.get("question", ""))
        haystack += " " + " ".join(q.get("answers", []) or [])
        if needle in haystack.lower():
            matches.append(q)
    return matches
