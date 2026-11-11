"""Word difficulty classification plus offline dictionary lookup.

Tasks 1.17-1.23 in ``tasks.md``. Promoted from ``spikes/spike_wordnet.py``.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from frameshot.config import DifficultyLevel

logger = logging.getLogger(__name__)

# Rank cutoffs: a word is "hard" when its corpus rank exceeds the cutoff.
DIFFICULTY_RANK_CUTOFF: dict[DifficultyLevel, int] = {
    DifficultyLevel.BEGINNER: 3_000,
    DifficultyLevel.INTERMEDIATE: 8_000,
    DifficultyLevel.ADVANCED: 15_000,
}

TOKEN_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")

CONTRACTION_MAP: dict[str, str] = {
    "ain't": "am not",
    "aren't": "are not",
    "can't": "cannot",
    "could've": "could have",
    "couldn't": "could not",
    "didn't": "did not",
    "doesn't": "does not",
    "don't": "do not",
    "hadn't": "had not",
    "hasn't": "has not",
    "haven't": "have not",
    "he'd": "he would",
    "he'll": "he will",
    "he's": "he is",
    "how'd": "how did",
    "how'll": "how will",
    "how's": "how is",
    "i'd": "i would",
    "i'll": "i will",
    "i'm": "i am",
    "i've": "i have",
    "isn't": "is not",
    "it'd": "it would",
    "it'll": "it will",
    "it's": "it is",
    "let's": "let us",
    "ma'am": "madam",
    "might've": "might have",
    "must've": "must have",
    "mustn't": "must not",
    "needn't": "need not",
    "shan't": "shall not",
    "she'd": "she would",
    "she'll": "she will",
    "she's": "she is",
    "should've": "should have",
    "shouldn't": "should not",
    "that'd": "that would",
    "that's": "that is",
    "there's": "there is",
    "they'd": "they would",
    "they'll": "they will",
    "they're": "they are",
    "they've": "they have",
    "wasn't": "was not",
    "we'd": "we would",
    "we'll": "we will",
    "we're": "we are",
    "we've": "we have",
    "weren't": "were not",
    "what'll": "what will",
    "what're": "what are",
    "what's": "what is",
    "what've": "what have",
    "where's": "where is",
    "who'll": "who will",
    "who's": "who is",
    "won't": "will not",
    "would've": "would have",
    "wouldn't": "would not",
    "you'd": "you would",
    "you'll": "you will",
    "you're": "you are",
    "you've": "you have",
}

# Default stop words used if NLTK stopwords are unavailable
FALLBACK_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
        "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
        "between", "both", "but", "by", "can", "did", "do", "does", "doing", "down",
        "during", "each", "few", "for", "from", "further", "had", "has", "have",
        "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
        "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
        "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
        "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over",
        "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
        "their", "theirs", "them", "themselves", "then", "there", "these", "they",
        "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
        "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
        "will", "with", "you", "your", "yours", "yourself", "yourselves",
    }
)

# ARPAbet -> IPA (American English, simplified).
ARPABET_TO_IPA: dict[str, str] = {
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

POS_MAP: dict[str, str] = {
    "n": "noun",
    "v": "verb",
    "a": "adj",
    "s": "adj",
    "r": "adv",
}


def arpabet_to_ipa(phones: list[str]) -> str:
    """Convert a CMUdict phone list to an IPA string."""
    pieces: list[str] = []
    for phone in phones:
        stress = ""
        clean_phone = phone
        if clean_phone and clean_phone[-1].isdigit():
            if clean_phone[-1] == "1":
                stress = "ˈ"
            elif clean_phone[-1] == "2":
                stress = "ˌ"
            clean_phone = clean_phone[:-1]
        pieces.append(stress + ARPABET_TO_IPA.get(clean_phone, clean_phone.lower()))
    return "".join(pieces)


@dataclass(frozen=True, slots=True)
class WordResult:
    word: str
    difficulty_score: float  # 0.0 = very common, 1.0 = very rare
    is_hard: bool
    definition: str | None = None
    synonyms: list[str] = field(default_factory=list)
    pronunciation: str | None = None  # IPA
    part_of_speech: str | None = None


class WordAnalyzer:
    """Turns a subtitle line into a ranked list of hard words with definitions."""

    def __init__(
        self,
        difficulty_level: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        freq_db_path: Path | None = None,
    ) -> None:
        self.difficulty_level = difficulty_level
        self._ranks: dict[str, int] = {}
        self._pronunciations: dict[str, list[list[str]]] = {}
        self._stop_words: set[str] = set(FALLBACK_STOPWORDS)

        self._load_frequency_source(freq_db_path)
        self._load_dictionary_resources()

    def _load_frequency_source(self, freq_db_path: Path | None) -> None:
        """Load word ranks from SQLite database or fallback to NLTK Brown."""
        # 1. Try provided database path or default data/word_frequency.db
        candidate_paths = []
        if freq_db_path is not None:
            candidate_paths.append(Path(freq_db_path))
        candidate_paths.append(Path("data/word_frequency.db"))

        for path in candidate_paths:
            if path.is_file():
                try:
                    with sqlite3.connect(path) as conn:
                        rows = conn.execute("SELECT word, rank FROM word_frequency").fetchall()
                    if rows:
                        self._ranks = {str(word).lower(): int(rank) for word, rank in rows}
                        logger.info("Loaded frequency source from SQLite %s (%d words)", path, len(self._ranks))
                        return
                except sqlite3.Error as exc:
                    logger.debug("Could not read frequency DB from %s: %s", path, exc)

        # 2. Try NLTK Brown corpus
        try:
            from nltk.corpus import brown

            tokens = brown.words()
            counts = Counter(token.lower() for token in tokens if token.isalpha())
            self._ranks = {
                word: rank for rank, (word, _) in enumerate(counts.most_common(), start=1)
            }
            logger.info("Loaded frequency source from NLTK Brown corpus (%d words)", len(self._ranks))
            return
        except Exception as exc:
            logger.debug("NLTK Brown corpus unavailable: %s", exc)

        logger.warning("No corpus available; word difficulty classification will use heuristics")

    def _load_dictionary_resources(self) -> None:
        """Load NLTK CMUdict and stopwords."""
        try:
            from nltk.corpus import stopwords

            self._stop_words = set(stopwords.words("english"))
        except Exception:
            self._stop_words = set(FALLBACK_STOPWORDS)

        try:
            from nltk.corpus import cmudict

            self._pronunciations = cmudict.dict()
        except Exception:
            self._pronunciations = {}

    # ------------------------------------------------------------ API

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Split text into lowercase word tokens, expanding contractions."""
        if not text:
            return []

        # Split into raw words / tokens
        raw_tokens = TOKEN_RE.findall(text)
        tokens: list[str] = []

        for raw in raw_tokens:
            lowered = raw.lower()
            if lowered in CONTRACTION_MAP:
                # Replace with expanded words
                expanded = CONTRACTION_MAP[lowered]
                tokens.extend(TOKEN_RE.findall(expanded))
            else:
                tokens.append(lowered)

        return tokens

    def classify_difficulty(self, word: str) -> tuple[float, bool]:
        """Return (difficulty_score, is_hard) based on frequency rank."""
        lemma = word.lower()
        cutoff = DIFFICULTY_RANK_CUTOFF.get(self.difficulty_level, 8_000)

        rank = self._ranks.get(lemma)
        if rank is None:
            # Word not in corpus: considered rare / advanced
            return 0.95, True

        score = min(1.0, rank / 20_000.0)
        is_hard = rank > cutoff
        return score, is_hard

    def lookup(self, word: str) -> WordResult:
        """WordNet definition, synonyms, POS, and IPA pronunciation (FR-22..FR-24)."""
        lemma = word.lower()
        score, is_hard = self.classify_difficulty(lemma)

        definition: str | None = None
        pos: str | None = None
        synonyms: list[str] = []

        try:
            from nltk.corpus import wordnet

            synsets = wordnet.synsets(lemma)
            if synsets:
                primary = synsets[0]
                definition = primary.definition()
                raw_pos = primary.pos()
                pos = POS_MAP.get(raw_pos, raw_pos)

                for l_obj in primary.lemmas()[:4]:
                    syn_name = l_obj.name().replace("_", " ")
                    if syn_name.lower() != lemma and syn_name.lower() not in synonyms:
                        synonyms.append(syn_name)
        except Exception as exc:
            logger.debug("WordNet lookup error for '%s': %s", lemma, exc)

        # Pronunciation
        ipa: str | None = None
        phones = self._pronunciations.get(lemma)
        if phones:
            ipa = f"/{arpabet_to_ipa(phones[0])}/"

        return WordResult(
            word=word,
            difficulty_score=round(score, 3),
            is_hard=is_hard,
            definition=definition,
            synonyms=synonyms,
            pronunciation=ipa,
            part_of_speech=pos,
        )

    def analyze(self, text: str) -> list[WordResult]:
        """Full pipeline: tokenize -> filter stopwords -> classify -> lookup."""
        tokens = self.tokenize(text)
        candidates = [
            t for t in tokens if t.lower() not in self._stop_words and len(t) > 2 and t.isalpha()
        ]

        # Preserve order while removing duplicates
        seen: set[str] = set()
        unique_candidates: list[str] = []
        for word in candidates:
            if word not in seen:
                seen.add(word)
                unique_candidates.append(word)

        results: list[WordResult] = []
        for word in unique_candidates:
            res = self.lookup(word)
            if res.is_hard:
                results.append(res)

        # Sort hardest words first
        results.sort(key=lambda r: r.difficulty_score, reverse=True)
        return results
