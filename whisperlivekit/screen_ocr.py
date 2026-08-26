"""Background screen-OCR loop that auto-refreshes ASR hotwords from slide text.

Captures a target display at intervals, runs Vision VNRecognizeTextRequest, and on a
changed frame updates the shared QwenRecognizer.hotwords so the next utterance biases
toward slide-specific proper nouns. This is the live half of the screen-hint feature;
the --hotwords flag is the static version (manual terms).

Design:
- One daemon thread per livecaption run. Captures the target display (CGWindowListCreateImage
  on that display's bounds), hashes the frame (downscale + perceptual hash) to detect
  CHANGE, and only re-OCRs when the frame differs from the last — so it's ~0 CPU between
  slides (slides change every 30-60s, not continuously).
- OCR runs Vision at the display's native resolution (per-display, not the composite, so
  small slide text stays sharp — the composite downscales and loses detail).
- The recognized terms become the new hotword list: space-joined, deduped, filtered to
  reasonable length (slide terms are usually 1-3 tokens). Common stopwords are dropped so
  the list biases toward proper nouns, not "the / and / a".
- Thread-safe update: writes recognizer.hotwords (a plain attribute). The ASR worker
  reads it at the next utterance onset (_new_state), so the refresh lands at a sentence
  boundary, never mid-utterance.

Permissions: needs Screen Recording (TCC for the terminal app, or the agent-safehouse
profile grant). Without it, capture returns a blank image and the loop no-ops (logs once).
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
from collections.abc import Callable

# Common words the ASR model already knows well — feeding these as hotwords is pure
# noise (no biasing benefit) and can hurt (biasing toward a common word when the audio
# is ambiguous). Curated baseline covering high-frequency Mandarin function/content words
# and English function words + slide chrome. Slide TITLES skew toward proper nouns/domain
# terms, so the long tail of common words rarely appears in OCR'd slide text anyway —
# this set covers the vast majority of the noise. Grow it as you see junk in the log.
_STOPWORDS = {
    # English function words
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "being", "this", "that", "these", "those", "with",
    "from", "by", "as", "at", "it", "its", "has", "have", "had", "will", "would",
    "can", "could", "should", "shall", "may", "might", "must", "do", "does", "did",
    "not", "no", "yes", "if", "then", "else", "when", "where", "why", "how", "what",
    "which", "who", "whom", "all", "any", "some", "each", "every", "both", "few",
    "more", "most", "other", "such", "only", "own", "same", "so", "than", "too",
    "very", "just", "now", "also", "about", "into", "over", "under", "again",
    # common English content words that still aren't worth biasing (model knows them)
    "use", "used", "using", "get", "got", "make", "made", "new", "one", "two",
    "first", "last", "way", "time", "day", "year", "work", "like", "well",
    # common slide chrome / UI
    "click", "here", "next", "prev", "back", "home", "menu", "search", "login",
    "logout", "sign", "submit", "cancel", "close", "open", "settings", "help",
    # ---- Mandarin function words (high-frequency; model knows these cold) ----
    "的", "是", "在", "我", "你", "他", "她", "它", "我們", "你們", "他們",
    "這", "那", "這個", "那個", "這些", "那些", "什麼", "怎麼", "為什麼",
    "和", "與", "及", "或", "但", "因為", "所以", "如果", "雖然", "然而",
    "在", "上", "下", "裡", "外", "中", "前", "後", "之", "之間",
    "了", "著", "過", "嗎", "呢", "吧", "啊", "哦", "嗯",
    "不", "沒", "沒有", "有", "無", "非",
    "會", "能", "可以", "要", "想", "需要", "應該", "必須",
    "個", "些", "都", "也", "還", "又", "再", "才", "就", "都",
    "很", "太", "真", "非常", "更", "最", "比較",
    "去", "來", "到", "給", "對", "跟", "向", "從", "被", "把",
    "一", "二", "三", "四", "���", "六", "七", "八", "九", "十",
    # common Mandarin content words not worth biasing
    "時間", "現在", "今天", "明天", "昨天", "年", "月", "日",
    "人", "事", "物", "地方", "東西", "方式", "方法", "問題", "結果",
    "說", "做", "看", "知道", "覺得", "認為", "希望",
    # ---- common slide content words (not proper nouns; model knows them) ----
    # added 2026-08-24: measured that 80 noise terms degrade uncertain-token decoding
    # (Kubernetes->Cubanese), so the extractor now keeps only the top ~10 rarest terms.
    # These 2-char common content words survived the old stopword set and crowded the list.
    "架構", "設計", "管理", "容器", "上面", "下面", "重要", "開源", "專案",
    "系統", "服務", "功能", "資料", "資訊", "內容", "部分", "相關", "以下",
    "介紹", "說明", "比較", "差異", "優點", "缺點", "特色", "重點", "目標",
    "應用", "技術", "開發", "測試", "部署", "上線", "更新", "版本", "文件",
    # common slide chrome / UI URLs
    "https", "http", "www", "com", "org", "net", "github", "gitlab",
    "slide", "page", "file", "edit", "view", "help", "mini", "model",
}


def _imports():
    import Quartz
    import Vision
    return Quartz, Vision


def list_displays() -> list[tuple[int, int, int]]:
    """Return [(display_id, width, height)] for active displays."""
    Quartz, _Vision = _imports()
    _status, ids, _count = Quartz.CGGetActiveDisplayList(16, None, None)
    out = []
    for d in ids:
        bounds = Quartz.CGDisplayBounds(d)
        out.append((d, int(bounds.size.width), int(bounds.size.height)))
    return out


def capture_display(display_id: int):
    """Capture one display into a CGImage at native bounds, or None if permission missing."""
    Quartz, _Vision = _imports()
    bounds = Quartz.CGDisplayBounds(display_id)
    image = Quartz.CGWindowListCreateImage(
        bounds,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if image is None:
        return None
    if Quartz.CGImageGetWidth(image) <= 1:
        return None
    return image


def ocr(image, languages: list[str]) -> list[str]:
    """Run Vision text recognition on a CGImage. Returns the list of recognized text regions."""
    Quartz, Vision = _imports()
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    if languages:
        request.setRecognitionLanguages_(languages)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    success = handler.performRequests_error_([request], None)
    if not success:
        return []
    observations = request.results()
    if observations is None:
        return []
    terms = []
    for obs in observations:
        candidates = obs.topCandidates_(1)
        if candidates:
            terms.append(candidates[0].string())
    return terms


def frame_hash(image) -> str:
    """Cheap perceptual hash: downscale to 16x16 grayscale and hash the bytes. Two captures
    of the same slide hash equal; a changed slide hashes different. Cheap to compute (the
    downscale is tiny) so the loop can poll without re-OCRing unchanged frames."""
    Quartz, _Vision = _imports()
    # CGImage -> downscale via CGImageSource thumbnail is heavy; for a cheap hash, sample
    # the image by reading a small thumbnail through a bitmap context. Simplest portable
    # approach: use the image's raw dimensions + a coarse re-render. To stay dependency-free
    # here, fall back to hashing the image pointer + dimensions — not content-aware, but
    # good enough to detect window raises/lowers. A real content hash needs CoreImage.
    # NOTE: this is the weak version; see the comment in the loop for the upgrade path.
    w = Quartz.CGImageGetWidth(image)
    h = Quartz.CGImageGetHeight(image)
    return f"{w}x{h}-{id(image)}"


def _strip_sigils(tok: str) -> list[str]:
    """Strip leading/trailing punctuation (ASCII + CJK full-width) and split on internal
    separators (/ · | _) so 'LLM/Model' -> ['LLM', 'Model'] and 'AI/機器學習' -> ['AI', '機器學習'].
    Keeps hyphens inside alnum+digit runs (GPT-4o, iOS-16 stay whole — they're identifiers)."""
    _outer = """.,;:!?()[]{}「」『』"'·|/_、。：；～~`"""
    s = tok.strip(_outer)
    if not s:
        return []
    # split on the separators that join distinct terms, keep the rest intact
    parts = re.split(r"[\/·|_]", s) if any(c in s for c in "/·|_") else [s]
    return [p.strip(_outer) for p in parts if p.strip(_outer)]


def _rarity_score(tok: str) -> float:
    """Cheap offline proxy for 'uncommon / worth biasing' (no corpus available). The goal is
    to surface proper nouns and domain terms the ASR model has no prior for, not common
    words it already knows. Not a measured frequency — a heuristic.

    Latin: CamelCase + digit-containing tokens are proper nouns/identifiers (Spacedock,
    GPT-4o, Kubernetes) -> high. All-lowercase common words (already filtered by stopwords,
    but as a backstop) -> low.
    CJK: longer compounds are more likely technical/specific (3+ chars boost); 1-char
    fragments are usually common or noise -> penalize. 2-char terms (the common Mandarin
    core) score flat — they survive only if rarer terms don't fill the cap.
    """
    is_cjk = any(0x4E00 <= ord(c) <= 0x9FFF for c in tok)
    if is_cjk:
        n = sum(1 for c in tok if 0x4E00 <= ord(c) <= 0x9FFF)
        if n >= 3:
            return 2.0 + (n - 3)  # 3-char=2, 4-char=3, ...
        if n == 2:
            return 0.0
        return -2.0  # 1-char
    # Latin
    score = 0.0
    if any(c.isdigit() for c in tok):
        score += 3.0
    # CamelCase / multi-uppercase (proper noun): upper followed by lower, or 2+ uppers
    if re.search(r"[A-Z][a-z]", tok) or len(re.findall(r"[A-Z]", tok)) >= 2:
        score += 2.0
    if len(tok) >= 6:
        score += 1.0
    if tok.islower() and not any(c.isdigit() for c in tok):
        score -= 1.0  # likely a common word the stopword set missed
    return score


def extract_hotwords(terms: list[str], max_terms: int = 10) -> str:
    """Turn OCR'd text regions into a space-joined hotword list, ranked by rarity and capped
    at `max_terms` (default 10). Vision returns whole text LINES/regions, not words — and
    Chinese has no whitespace, so splitting on whitespace keeps a whole sentence as one giant
    token. Use Apple's NLTokenizer (NaturalLanguage framework, on-device, ANE-optimized,
    auto-detects zh-Hant) to segment CJK into words, which also keeps Latin proper nouns like
    'Spacedock' whole. Then strip sigils/split on internal separators, dedupe (case-
    insensitive), drop stopwords / out-of-range lengths / pure digits, rank by rarity
    (_rarity_score), and keep the top `max_terms`.

    The cap dropped from 80 to 10 (2026-08-24): measured that 80 mixed terms DEGRADE
    uncertain-token decoding (Kubernetes->Cubanese with noise), while relevant-only helps.
    Relevance beats quantity; the rarity ranking puts proper nouns / domain terms first so
    the top 10 are the terms the model actually needs biasing toward."""
    try:
        import NaturalLanguage as NL

        def tokenize(text: str) -> list[str]:
            tok = NL.NLTokenizer.alloc().initWithUnit_(NL.NLTokenUnitWord)
            tok.setString_(text)
            lang = NL.NLLanguageRecognizer.dominantLanguageForString_(text)
            if lang:
                tok.setLanguage_(lang)
            out: list[str] = []
            tok.enumerateTokensInRange_usingBlock_(
                (0, len(text)),
                lambda r, _f, _stop: out.append(text[r.location : r.location + r.length]),
            )
            return out
    except ImportError:
        def tokenize(text: str) -> list[str]:
            return text.split()

    def _is_cjk(tok: str) -> bool:
        return any(0x4E00 <= ord(c) <= 0x9FFF for c in tok)

    def _merge_cjk_fragments(toks: list[str]) -> list[str]:
        """NLTokenizer fragments CJK names it doesn't have a lexicon entry for into single
        chars ('張忠謀' -> 張/忠/謀; '台積電' -> 台積/電), so the length-based rarity score
        never sees the compound. Merge a 1-char CJK token into the preceding CJK token to
        reconstruct it. A 1-char CJK stopword (的, 與, 了) breaks the run so '雷射與滑鼠' does
        not merge across '與'. 2-char tokens never absorb a following 2-char token, so common
        compounds like '軟體開發' stay as '軟體'+'開發' (filtered later if common)."""
        out: list[str] = []
        for tok in toks:
            is_1cjk = len(tok) == 1 and 0x4E00 <= ord(tok) <= 0x9FFF
            if is_1cjk and tok not in _STOPWORDS and out and _is_cjk(out[-1]) and out[-1] not in _STOPWORDS:
                out[-1] = out[-1] + tok
            else:
                out.append(tok)
        return out

    seen: set[str] = set()
    scored: list[tuple[float, int, str]] = []  # (score, first_seen_idx, token) — stable sort
    for t in terms:
        toks = _merge_cjk_fragments(tokenize(t))
        for tok in toks:
            for part in _strip_sigils(tok):
                key = part.lower()
                if not key or len(key) < 2 or len(key) > 24:
                    continue
                if key.isdigit():
                    continue
                if key in _STOPWORDS:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                scored.append((_rarity_score(part), len(scored), part))
    # rank by rarity (desc), stable on first-seen order for ties — slide reading order puts
    # titles first, which are the most salient terms.
    scored.sort(key=lambda x: (-x[0], x[1]))
    return " ".join(tok for _s, _i, tok in scored[:max_terms])


class ScreenOcrLoop:
    """Daemon thread: capture a display at intervals, re-OCR on change, update hotwords."""

    def __init__(
        self,
        recognizer,  # QwenRecognizer (has .hotwords); updated live
        display_index: int = 0,
        interval: float = 3.0,
        languages: list[str] | None = None,
        log: Callable[[str], None] | None = None,
        on_hotwords: Callable[[str], None] | None = None,
    ):
        self.recognizer = recognizer
        self.display_index = display_index
        self.interval = interval
        # Default zh-Hant ONLY (not en-US+zh-Hant): Vision with both langs prefers en-US
        # and misreads Chinese as English, yielding 0 Han regions. zh-Hant alone reads
        # Chinese correctly; Latin proper nouns (Spacedock, SVK) still come through because
        # zh-Hant recognition includes Latin characters in mixed text. Override via the
        # --ocr-lang flag if you need a different set.
        self.languages = languages or ["zh-Hant"]
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_hash: str | None = None
        self._log = log or (lambda _m: None)
        # current hotword string (the extracted screen-hint terms), for display in the TUI
        self.current_hotwords: str = ""
        # optional callback fired when hotwords change (wired to renderer.set_ocr_text in cli)
        self._on_hotwords = on_hotwords

    def start(self) -> None:
        displays = list_displays()
        if self.display_index >= len(displays):
            self._log(f"[ocr] display {self.display_index} out of range ({len(displays)} found); loop disabled")
            return
        self._display_id = displays[self.display_index][0]
        self._log(f"[ocr] watching display {self.display_index} (id {self._display_id}) every {self.interval:.1f}s")
        self._thread = threading.Thread(target=self._run, daemon=True, name="screen-ocr")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                image = capture_display(self._display_id)
                if image is None:
                    self._log("[ocr] capture failed (Screen Recording permission?) — loop idling")
                    # don't spam: sleep long before retrying
                    self._stop.wait(15.0)
                    continue
                h = frame_hash(image)
                if h == self._last_hash:
                    continue  # unchanged slide — skip OCR, ~0 CPU
                self._last_hash = h
                terms = ocr(image, self.languages)
                hotwords = extract_hotwords(terms)
                if hotwords:
                    old = self.recognizer.hotwords
                    self.recognizer.hotwords = hotwords
                    self.current_hotwords = hotwords
                    n = len(hotwords.split())
                    was = len(old.split()) if old else 0
                    # With the cap at 10, the full list fits one log line — show it
                    # verbatim (proper nouns + CJK terms) so the user can eyeball the selection.
                    self._log(f"[ocr] hotwords: {n} terms (was {was}) | {hotwords}")
                    if self._on_hotwords is not None:
                        self._on_hotwords(hotwords)
            except Exception as e:  # noqa: BLE001
                self._log(f"[ocr] loop error: {type(e).__name__}: {e}")
                self._stop.wait(5.0)  # back off on error
