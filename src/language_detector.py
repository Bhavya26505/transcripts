import re
from pathlib import Path
from typing import Dict, List, Any, Tuple

FINANCIAL_TERMS = {
    "ipo", "nsdl", "cdsl", "demat", "mutual", "fund", "funds", "stock", "market", "markets",
    "revenue", "business", "model", "risk", "portfolio", "return", "returns", "share", "shares",
    "equity", "bank", "banks", "investor", "investors", "trading", "profit", "loss", "dividend",
    "nifty", "sensex", "sebi", "rbi", "governor", "crypto", "bitcoin", "loan", "tax", "inflation",
    "recession", "gold", "dollar", "currency", "trade", "investment", "bonds", "sec", "fed"
}

ROMANIZED_HINDI_WORDS = {
    "aaj", "hum", "aap", "ke", "ki", "ka", "ko", "se", "mein", "me", "par", "baat", "karenge",
    "karna", "kar", "hai", "hain", "bhi", "toh", "to", "nahi", "nhi", "aur", "ye", "yeh", "woh",
    "wo", "saath", "dusra", "pehle", "kya", "kyun", "kab", "kahan", "kaise", "jaise", "lekin",
    "magar", "kyunki", "isliye", "sabse", "bohot", "bahut", "rahe", "raha", "rahi", "hoga",
    "hogi", "hoge", "karte", "karta", "karti", "dekh", "dekho", "dekhiye", "matlab", "yani",
    "achha", "arrey", "samajhte", "bataunga", "karte", "rahenge", "jana", "hua", "huye", "par"
}

ENGLISH_TECHNICAL_LOANWORDS_DEVANAGARI = {
    "आईपीओ", "सीडीएसएल", "एनएसडीएल", "बिजनेस", "बिज़नेस", "मॉडल", "डीमैट", "स्टॉक", "मार्केट",
    "म्यूचुअल", "फंड", "शेयर", "रेवेन्यू", "नेक्स्ट", "कैलेंडर", "सीरीज", "नेटफ्लिक्स", "ऑयल",
    "प्राइस", "कंट्री", "डॉलर", "गोल्ड", "रिटर्न", "इक्विटी", "इन्वेस्टर", "इन्वेस्टर्स"
}

def compute_script_ratios(text: str) -> Tuple[float, float, int, int]:
    """
    Computes Devanagari and Latin character counts and ratios.
    Returns (devanagari_ratio, latin_ratio, devanagari_count, latin_count).
    """
    devanagari_count = 0
    latin_count = 0

    for char in text:
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            devanagari_count += 1
        elif (65 <= code <= 90) or (97 <= code <= 122):
            latin_count += 1

    total_alpha = devanagari_count + latin_count
    if total_alpha == 0:
        return 0.0, 0.0, 0, 0

    dev_ratio = round(devanagari_count / total_alpha, 3)
    lat_ratio = round(latin_count / total_alpha, 3)
    return dev_ratio, lat_ratio, devanagari_count, latin_count

def classify_text_language(text: str) -> Tuple[str, float, str]:
    """
    Deterministic language classification for a text string.
    Supports HINDI, ENGLISH, HINGLISH, MIXED, UNKNOWN.
    Returns (detected_language, confidence_score, explanation_reason).
    """
    if not text or not text.strip():
        return "UNKNOWN", 0.0, "Empty text"

    dev_ratio, lat_ratio, dev_cnt, lat_cnt = compute_script_ratios(text)
    total_alpha = dev_cnt + lat_cnt

    if total_alpha < 3:
        return "UNKNOWN", 0.30, "Insufficient alphabetic characters"

    words = re.findall(r'\b[a-zA-Z\u0900-\u097F]+\b', text)
    total_words = len(words)

    # CASE A: Predominantly Devanagari Script (>= 85%)
    if dev_ratio >= 0.85:
        # Check for English loanwords / technical terms in Devanagari or embedded Latin
        has_loanwords = False
        loanword_count = 0
        for w in words:
            w_lower = w.lower()
            if w in ENGLISH_TECHNICAL_LOANWORDS_DEVANAGARI or w_lower in FINANCIAL_TERMS or re.match(r'^[a-zA-Z]+$', w):
                has_loanwords = True
                loanword_count += 1

        loanword_ratio = loanword_count / total_words if total_words > 0 else 0.0

        if has_loanwords and loanword_ratio >= 0.05:
            conf = min(0.95, round(0.85 + loanword_ratio * 0.2, 2))
            reason = f"Devanagari script ({dev_ratio*100:.0f}%) with {loanword_count} English/financial loanword(s) (Code-Switching)"
            return "HINGLISH", conf, reason
        else:
            return "HINDI", 0.96, f"Pure Devanagari script ({dev_ratio*100:.0f}%)"

    # CASE B: Mixed Devanagari and Latin Script (Code-Switching / Mixed)
    if dev_ratio >= 0.15 and lat_ratio >= 0.15:
        reason = f"Mixed Devanagari ({dev_ratio*100:.0f}%) and Latin ({lat_ratio*100:.0f}%) script code-switching"
        return "HINGLISH", 0.92, reason

    # CASE C: Predominantly Latin Script (>= 85%)
    if lat_ratio >= 0.85:
        words_latin = [w.lower() for w in words if re.match(r'^[a-zA-Z]+$', w)]
        if not words_latin:
            return "ENGLISH", 0.85, "Latin script"

        # Count Romanized Hindi words and financial terms
        romanized_hindi_cnt = sum(1 for w in words_latin if w in ROMANIZED_HINDI_WORDS)
        financial_cnt = sum(1 for w in words_latin if w in FINANCIAL_TERMS)

        # Exclude financial terms when determining non-English Romanized Hindi ratio
        non_financial_words = [w for w in words_latin if w not in FINANCIAL_TERMS]
        num_non_financial = len(non_financial_words)

        rom_hindi_ratio = (romanized_hindi_cnt / num_non_financial) if num_non_financial > 0 else (romanized_hindi_cnt / len(words_latin))

        if rom_hindi_ratio >= 0.12 or (romanized_hindi_cnt >= 2 and total_words <= 15):
            conf = min(0.96, round(0.75 + rom_hindi_ratio * 0.4, 2))
            reason = f"Latin script with {romanized_hindi_cnt} Romanized Hindi word(s) ({rom_hindi_ratio*100:.0f}%)"
            return "HINGLISH", conf, reason
        elif romanized_hindi_cnt > 0:
            reason = f"Latin script with sparse Romanized Hindi ({romanized_hindi_cnt} word(s)) and English"
            return "MIXED", 0.82, reason
        else:
            return "ENGLISH", 0.95, f"Pure Latin script ({lat_ratio*100:.0f}%)"

    # Fallback
    return "UNKNOWN", 0.50, "Ambiguous script ratios"

def enrich_segmented_transcript_with_language(segmented_transcript: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches Phase 4 segmented transcript with Phase 5 language detection metadata.
    Preserves exact text, timestamps, segment boundaries, and source subtitle IDs.
    """
    video_id = segmented_transcript["video_id"]
    segments = segmented_transcript.get("segments", [])
    duration_seconds = segmented_transcript["duration_seconds"]

    enriched_segments = []
    lang_counts = {"HINDI": 0, "ENGLISH": 0, "HINGLISH": 0, "MIXED": 0, "UNKNOWN": 0}

    for seg in segments:
        text = seg["text"]
        det_lang, conf, reason = classify_text_language(text)

        lang_counts[det_lang] = lang_counts.get(det_lang, 0) + 1

        enriched_seg = dict(seg)
        enriched_seg["language"] = det_lang
        enriched_seg["language_confidence"] = conf
        enriched_seg["language_reason"] = reason
        enriched_segments.append(enriched_seg)

    total_segs = len(enriched_segments)
    lang_distribution = {}
    for l_key in ["HINDI", "ENGLISH", "HINGLISH", "MIXED", "UNKNOWN"]:
        cnt = lang_counts.get(l_key, 0)
        lang_distribution[l_key] = round(cnt / total_segs, 3) if total_segs > 0 else 0.0

    # Determine primary language
    primary_lang = max(lang_distribution, key=lang_distribution.get) if total_segs > 0 else "UNKNOWN"

    # Code switching detection
    non_zero_languages = [l for l, dist in lang_distribution.items() if dist > 0.05]
    code_switching = len(non_zero_languages) > 1 or lang_counts["HINGLISH"] > 0 or lang_counts["MIXED"] > 0

    language_profile = {
        "primary_language": primary_lang,
        "language_distribution": lang_distribution,
        "code_switching": code_switching,
        "segment_counts": lang_counts
    }

    return {
        "video_id": video_id,
        "source_language_header": segmented_transcript["language"],
        "duration_seconds": duration_seconds,
        "language_profile": language_profile,
        "statistics": segmented_transcript["statistics"],
        "segments": enriched_segments
    }
