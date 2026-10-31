"""Word difficulty classification plus offline dictionary lookup.

Status: **stub** — tasks 1.17-1.23 in ``tasks.md``. The working reference
implementation is ``spikes/spike_wordnet.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from frameshot.config import DifficultyLevel

# Rank cutoffs: a word is "hard" when its corpus rank exceeds the cutoff.
# (architecture.md §5.3 left this ambiguous - resolve in spike 0.6.)
DIFFICULTY_RANK_CUTOFF: dict[DifficultyLevel, int] = {
    DifficultyLevel.BEGINNER: 3_000,
    DifficultyLevel.INTERMEDIATE: 8_000,
    DifficultyLevel.ADVANCED: 15_000,
}


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

    def __init__(self, difficulty_level: DifficultyLevel = DifficultyLevel.INTERMEDIATE) -> None:
        self.difficulty_level = difficulty_level

    def analyze(self, text: str) -> list[WordResult]:
        """Full pipeline: tokenize -> filter stopwords -> classify -> lookup."""
        raise NotImplementedError("tasks.md 1.18-1.21 - see spikes/spike_wordnet.py")

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Split text into lowercase word tokens, expanding contractions."""
        raise NotImplementedError("tasks.md 1.18")

    def classify_difficulty(self, word: str) -> float:
        """Return a 0.0-1.0 difficulty score from the frequency database."""
        raise NotImplementedError("tasks.md 1.19")

    @staticmethod
    def lookup(word: str) -> WordResult | None:
        """WordNet definition, synonyms, and IPA pronunciation (FR-22..FR-24)."""
        raise NotImplementedError("tasks.md 1.20-1.21")
