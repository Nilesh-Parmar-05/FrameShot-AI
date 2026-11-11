"""Unit tests for frameshot.word_analyzer (Tasks 1.17-1.23)."""

from __future__ import annotations

import pytest

from frameshot.config import DifficultyLevel
from frameshot.word_analyzer import WordAnalyzer, arpabet_to_ipa


@pytest.fixture(scope="module")
def analyzer() -> WordAnalyzer:
    return WordAnalyzer(difficulty_level=DifficultyLevel.INTERMEDIATE)


def test_arpabet_to_ipa():
    # 'edifice' in CMUdict: ['EH1', 'D', 'AH0', 'F', 'AH0', 'S']
    phones = ["EH1", "D", "AH0", "F", "AH0", "S"]
    ipa = arpabet_to_ipa(phones)
    assert "ˈ" in ipa  # primary stress
    assert "d" in ipa
    assert "f" in ipa
    assert "s" in ipa


def test_tokenize_simple():
    tokens = WordAnalyzer.tokenize("Hello World!")
    assert tokens == ["hello", "world"]


def test_tokenize_contractions():
    tokens = WordAnalyzer.tokenize("Don't worry, it's they're wasn't can't.")
    assert "do" in tokens
    assert "not" in tokens
    assert "it" in tokens
    assert "is" in tokens
    assert "they" in tokens
    assert "are" in tokens
    assert "was" in tokens
    assert "cannot" in tokens or ("can" in tokens and "not" in tokens)


def test_tokenize_empty():
    assert WordAnalyzer.tokenize("") == []
    assert WordAnalyzer.tokenize("   .,!?-   ") == []


def test_classify_difficulty_common(analyzer: WordAnalyzer):
    score, is_hard = analyzer.classify_difficulty("the")
    assert not is_hard
    assert score < 0.1


def test_classify_difficulty_rare(analyzer: WordAnalyzer):
    score, is_hard = analyzer.classify_difficulty("resplendent")
    assert is_hard
    assert score > 0.3


def test_classify_difficulty_unknown(analyzer: WordAnalyzer):
    score, is_hard = analyzer.classify_difficulty("unobtainiumsuperfragilistic")
    assert is_hard
    assert score == 0.95


def test_lookup_known_word(analyzer: WordAnalyzer):
    result = analyzer.lookup("edifice")
    assert result.word == "edifice"
    assert result.definition is not None
    assert "structure" in result.definition or "building" in result.definition
    assert result.part_of_speech == "noun"
    assert result.pronunciation is not None
    assert result.pronunciation.startswith("/")
    assert result.pronunciation.endswith("/")


def test_lookup_unknown_word(analyzer: WordAnalyzer):
    result = analyzer.lookup("xyzzyplugh")
    assert result.word == "xyzzyplugh"
    assert result.definition is None
    assert result.pronunciation is None
    assert result.is_hard is True


def test_analyze_full_sentence(analyzer: WordAnalyzer):
    text = "The edifice was resplendent under the moonlight."
    results = analyzer.analyze(text)
    words = [r.word for r in results]

    assert "edifice" in words
    assert "resplendent" in words
    # Common words must NOT appear as hard words
    assert "the" not in words
    assert "was" not in words
    assert "under" not in words

    # Results should have definitions
    edifice_res = next(r for r in results if r.word == "edifice")
    assert edifice_res.definition is not None
    assert edifice_res.pronunciation is not None


def test_analyze_all_common(analyzer: WordAnalyzer):
    text = "The dog was very happy today."
    results = analyzer.analyze(text)
    assert len(results) == 0


def test_difficulty_threshold_levels():
    analyzer_beg = WordAnalyzer(difficulty_level=DifficultyLevel.BEGINNER)
    analyzer_adv = WordAnalyzer(difficulty_level=DifficultyLevel.ADVANCED)

    text = "A simple building with a resplendent garden."
    results_beg = analyzer_beg.analyze(text)
    results_adv = analyzer_adv.analyze(text)

    # Beginner cutoff is 3,000 rank -> flags more words
    # Advanced cutoff is 15,000 rank -> flags only very rare words
    assert len(results_beg) >= len(results_adv)
