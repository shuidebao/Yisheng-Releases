from __future__ import annotations

import re


_EDGE_PUNCTUATION = "\\\"'`.,!?;:，。！？；：、…—-（）()[]【】<>《》"
_CJK_REPETITION = re.compile(
    r"(?P<unit>[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]{1,12})(?P=unit){2,}"
)


def _token_key(token: str) -> str:
    return token.strip(_EDGE_PUNCTUATION).casefold()


def _collapse_repeated_word_blocks(text: str, max_block_words: int = 8) -> str:
    """Collapse a word or short phrase repeated at least three times.

    Two consecutive occurrences are preserved because they can be intentional
    speech (for example, "very very"). Three or more consecutive copies are a
    common Whisper hallucination on music, silence and chunk boundaries.
    """
    words = text.split()
    if len(words) < 3:
        return text

    result: list[str] = []
    index = 0
    while index < len(words):
        matched = False
        largest = min(max_block_words, (len(words) - index) // 3)
        # Prefer the smallest repeating unit. Otherwise twelve copies of one
        # token can be mistaken for three copies of a four-token block and the
        # cleanup would incorrectly leave eight tokens behind.
        for width in range(1, largest + 1):
            block_keys = [_token_key(word) for word in words[index : index + width]]
            if not all(block_keys):
                continue
            copies = 1
            while index + (copies + 1) * width <= len(words):
                candidate = [
                    _token_key(word)
                    for word in words[index + copies * width : index + (copies + 1) * width]
                ]
                if candidate != block_keys:
                    break
                copies += 1
            if copies >= 3:
                # Keep two copies so legitimate emphasis is not destroyed.
                result.extend(words[index : index + width * 2])
                index += width * copies
                matched = True
                break
        if not matched:
            result.append(words[index])
            index += 1
    return " ".join(result)


def suppress_repetitions(text: str) -> str:
    """Limit runaway token/phrase loops without changing normal repetition."""
    text = _collapse_repeated_word_blocks(text)

    def keep_two_cjk_copies(match: re.Match[str]) -> str:
        return match.group("unit") * 2

    # CJK transcripts often contain no spaces, so handle repeated Han/Kana
    # phrases separately. As above, retain two copies for natural emphasis.
    previous = None
    while previous != text:
        previous = text
        text = _CJK_REPETITION.sub(keep_two_cjk_copies, text)
    return text


def clean_transcript(text: str) -> str:
    """Normalize model output without damaging CJK spacing."""
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\s+([,.!?;:，。！？；：])", r"\1", text)
    return suppress_repetitions(text)


def merge_overlap(previous: str, current: str, max_words: int = 12) -> str:
    """Remove repeated words caused by overlapping live audio chunks."""
    previous = clean_transcript(previous)
    current = clean_transcript(current)
    if not previous or not current:
        return current

    old_words = previous.casefold().split()
    new_words = current.split()
    folded_new = [word.casefold() for word in new_words]
    max_overlap = min(max_words, len(old_words), len(new_words))
    for width in range(max_overlap, 1, -1):
        if old_words[-width:] == folded_new[:width]:
            return " ".join(new_words[width:]).strip()
    return current


def merge_continuation(previous: str, current: str, language: str | None = None) -> str:
    """Join adjacent live chunks and remove their intentional audio overlap."""
    previous = clean_transcript(previous)
    current = clean_transcript(current)
    if not previous:
        return current
    if not current:
        return previous

    if language in {"ja", "zh", "ko"}:
        old_compact = re.sub(r"\s+", "", previous)
        new_compact = re.sub(r"\s+", "", current)
        max_overlap = min(48, len(old_compact), len(new_compact))
        for width in range(max_overlap, 1, -1):
            if old_compact[-width:] == new_compact[:width]:
                new_compact = new_compact[width:]
                break
        return clean_transcript(old_compact + new_compact)

    remainder = merge_overlap(previous, current, max_words=20)
    return clean_transcript(f"{previous} {remainder}" if remainder else previous)
