"""Task 0.6 / 0.7 - word difficulty + offline dictionary feasibility.

Answers:

  * Can WordNet supply definitions and synonyms offline? (FR-22, FR-24)
  * Is rank-based difficulty classification workable? (FR-21, FR-25)
  * Can we produce IPA pronunciation from CMUdict offline? (FR-23)
  * How long does analysing one subtitle line take? (budget < 100 ms)

WordNet has **no IPA**. The spike builds ARPAbet from ``nltk.corpus.cmudict``
and maps it to IPA, which is the approach tech-stack.md §5 already recommends.

Frequency source order:
  1. ``data/word_frequency.db`` if you have built it (task 1.17),
  2. NLTK's Brown corpus as a stand-in for SUBTLEXus (real rank signal),
  3. a length/synset-count heuristic, clearly labelled as a fallback.

Usage:

    python spikes/spike_wordnet.py
    python spikes/spike_wordnet.py --text "The edifice was resplendent under the moonlight."
    python spikes/spike_wordnet.py --difficulty advanced
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import time
from collections import Counter

from _util import REPO_ROOT, banner, die, step, verdict

RANK_CUTOFF = {"beginner": 3_000, "intermediate": 8_000, "advanced": 15_000}
DEFAULT_TEXT = (
    "The edifice was resplendent under the moonlight, and the vicar was quite nonplussed."
)

FALLBACK_STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}

# ARPAbet -> IPA (American English, simplified). Stress digits are handled separately.
ARPABET_TO_IPA = {
    "AA": "ɑ",
    "AE": "æ",
    "AH": "ʌ",
    "AO": "ɔ",
    "AW": "aʊ",
    "AY": "aɪ",
    "B": "b",
    "CH": "tʃ",
    "D": "d",
    "DH": "ð",
    "EH": "ɛ",
    "ER": "ɝ",
    "EY": "eɪ",
    "F": "f",
    "G": "ɡ",
    "HH": "h",
    "IH": "ɪ",
    "IY": "i",
    "JH": "dʒ",
    "K": "k",
    "L": "l",
    "M": "m",
    "N": "n",
    "NG": "ŋ",
    "OW": "oʊ",
    "OY": "ɔɪ",
    "P": "p",
    "R": "ɹ",
    "S": "s",
    "SH": "ʃ",
    "T": "t",
    "TH": "θ",
    "UH": "ʊ",
    "UW": "u",
    "V": "v",
    "W": "w",
    "Y": "j",
    "Z": "z",
    "ZH": "ʒ",
}

TOKEN_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")


def arpabet_to_ipa(phones: list[str]) -> str:
    """Convert a CMUdict phone list to a rough IPA string."""
    pieces: list[str] = []
    for phone in phones:
        stress = ""
        if phone[-1].isdigit():
            if phone[-1] == "1":
                stress = "ˈ"
            elif phone[-1] == "2":
                stress = "ˌ"
            phone = phone[:-1]
        pieces.append(stress + ARPABET_TO_IPA.get(phone, phone.lower()))
    return "".join(pieces)


class FrequencySource:
    """Rank lookup backed by SQLite, Brown corpus, or a heuristic."""

    def __init__(self) -> None:
        self.kind = "heuristic"
        self._ranks: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        db_path = REPO_ROOT / "data" / "word_frequency.db"
        if db_path.is_file():
            try:
                with sqlite3.connect(db_path) as conn:
                    rows = conn.execute("SELECT word, rank FROM word_frequency").fetchall()
                self._ranks = {str(word).lower(): int(rank) for word, rank in rows}
                self.kind = f"sqlite ({db_path.name}, {len(self._ranks)} words)"
                return
            except sqlite3.Error as exc:
                print(f"  word_frequency.db unreadable ({exc}); falling back")

        try:
            import nltk
            from nltk.corpus import brown
        except ImportError:
            print("  nltk not installed; frequency classification will be a heuristic")
            return

        try:
            tokens = brown.words()
        except LookupError:
            print("  downloading NLTK 'brown' corpus (~1.5 MB) as a SUBTLEXus stand-in...")
            try:
                nltk.download("brown", quiet=True)
                tokens = brown.words()
            except Exception as exc:  # noqa: BLE001
                print(f"  could not download brown corpus ({exc}); using heuristic")
                return

        counts = Counter(token.lower() for token in tokens if token.isalpha())
        self._ranks = {word: rank for rank, (word, _) in enumerate(counts.most_common(), start=1)}
        self.kind = f"brown corpus ({len(self._ranks)} distinct words)"

    def rank(self, word: str) -> int | None:
        return self._ranks.get(word.lower())

    def difficulty(self, word: str, cutoff: int) -> tuple[float, bool, str]:
        """Return ``(score, is_hard, evidence)``."""
        rank = self.rank(word)
        if rank is None:
            # Unknown to the corpus: rare by definition, but say so honestly.
            return 0.95, True, "absent from corpus"
        score = min(1.0, rank / 20_000)
        return score, rank > cutoff, f"rank #{rank}"


def ensure_nltk_data() -> None:
    import nltk

    for package, probe in (
        ("wordnet", lambda: nltk.corpus.wordnet.synsets("test")),
        ("omw-1.4", lambda: None),
        ("cmudict", lambda: nltk.corpus.cmudict.dict()),
        ("stopwords", lambda: nltk.corpus.stopwords.words("english")),
    ):
        try:
            probe()
        except LookupError:
            print(f"  downloading NLTK data: {package}")
            nltk.download(package, quiet=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--difficulty", default="intermediate", choices=sorted(RANK_CUTOFF))
    parser.add_argument("--limit", type=int, default=12, help="max words to report")
    args = parser.parse_args()

    banner("Task 0.6/0.7 - word difficulty and offline dictionary")
    try:
        from nltk.corpus import cmudict, stopwords, wordnet
    except ImportError:
        die('nltk is missing - run: pip install -e ".[nlp]"')

    step("preparing NLTK data")
    ensure_nltk_data()

    try:
        stop_words = set(stopwords.words("english"))
    except LookupError:
        stop_words = FALLBACK_STOPWORDS

    step("frequency source")
    started = time.perf_counter()
    frequency = FrequencySource()
    print(f"  source: {frequency.kind}")
    print(f"  ready in {(time.perf_counter() - started) * 1_000:.0f} ms")
    if frequency.kind.startswith("brown"):
        print("  NOTE: Brown is a stand-in. Task 1.17 must ship SUBTLEXus (subtitle-tuned).")

    step("CMUdict pronunciation index")
    try:
        pronunciations = cmudict.dict()
        print(f"  entries: {len(pronunciations)}")
    except LookupError:
        pronunciations = {}
        print("  cmudict unavailable - IPA column will be empty")

    cutoff = RANK_CUTOFF[args.difficulty]
    tokens = [match.group(0) for match in TOKEN_RE.finditer(args.text)]
    candidates = [token for token in tokens if token.lower() not in stop_words and len(token) > 2]
    print(f"\ntext: {args.text!r}")
    print(f"tokens: {len(tokens)}, candidates after stopword filter: {len(candidates)}")

    step(f"analysis (level={args.difficulty}, hard when rank > {cutoff})")
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for token in candidates:
        word = token.lower()
        lemma = word
        score, is_hard, evidence = frequency.difficulty(lemma, cutoff)
        if not is_hard:
            continue

        synsets = wordnet.synsets(lemma)
        definition = synsets[0].definition() if synsets else None
        synonyms: list[str] = []
        pos = None
        if synsets:
            pos = synsets[0].pos()
            for lemma_obj in synsets[0].lemmas()[:4]:
                name = lemma_obj.name().replace("_", " ")
                if name.lower() != lemma and name.lower() not in synonyms:
                    synonyms.append(name)
        ipa = ""
        phones = pronunciations.get(lemma) or pronunciations.get(token.lower())
        if phones:
            ipa = f"/{arpabet_to_ipa(phones[0])}/"

        rows.append(
            {
                "word": token,
                "score": round(score, 2),
                "evidence": evidence,
                "pos": pos or "-",
                "definition": (definition or "(no WordNet entry)")[:80],
                "synonyms": ", ".join(synonyms[:3]) or "-",
                "ipa": ipa or "-",
            }
        )

    elapsed_ms = (time.perf_counter() - started) * 1_000

    if not rows:
        print("  no hard words found in this sentence (try a harder text)")
    for row in rows[: args.limit]:
        print(
            f"\n  {row['word']}  {row['ipa']}  [{row['pos']}]  score={row['score']} ({row['evidence']})"
        )
        print(f"    definition: {row['definition']}")
        print(f"    synonyms:   {row['synonyms']}")

    step("timing")
    per_word_ms = elapsed_ms / max(len(candidates), 1)
    print(f"  {len(candidates)} candidate words in {elapsed_ms:.1f} ms ({per_word_ms:.2f} ms/word)")
    print(
        f"  budget for a whole subtitle line: 100 ms -> ~{int(100 / max(per_word_ms, 0.01))} words"
    )

    ok = True
    ok &= verdict(bool(pronunciations), "CMUdict loaded offline")
    ok &= verdict(rows != [], "at least one hard word detected and defined")
    ok &= verdict(
        all(row["definition"] != "(no WordNet entry)" for row in rows) if rows else False,
        "every flagged word has a WordNet definition",
    )
    ok &= verdict(elapsed_ms < 100, f"one line analysed in {elapsed_ms:.1f} ms (< 100 ms)")

    banner("Phase 0.6/0.7 verdict")
    print("What to record in tasks.md 0.6/0.7:")
    print(f"  - frequency source available offline: {frequency.kind}")
    print("  - WordNet: definitions + synonyms work; it has NO IPA.")
    print("  - pronunciation must come from CMUdict + ARPAbet->IPA mapping")
    print("    (add `nltk.corpus.cmudict` to the download script).")
    print("  - contraction/hyphen tokens need explicit handling in Phase 1 (1.18).")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
