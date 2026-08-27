"""Terminal TUI renderer: a three-region persistent layout (scrolling captions,
OCR line, status line) built on rich.Live.

The contract mirrors the overlay renderer:
__enter__/__exit__, partial, final, translation, preview, flush_pending,
set_ocr_text. Both renderers can run together via MultiRenderer.

Committed captions persist and scroll above the live region (transient=False);
the live region shows the in-progress partial and the status line. This is the
inverse of the overlay, which clears after a hold.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime

from rich.console import Console, Group
from rich.text import Text

# Fixed styles that stay neutrally visible on both backgrounds.
_COMMON_STYLES = {
    "ts": "grey50",
    "partial": "grey50",
    "final": "",
    "diff_del": "grey50 strike",
    "diff_add": "bold green",
    "mem": "grey50",
}
_TRANSLATION_STYLE = {
    "default": "bold",
    "dark": "bold bright_cyan",
    "light": "deep_sky_blue4",
}
# Provisional (simul-MT draft) translation: dimmer than the final, marks it as
# uncommitted/in-progress. Final translations use _TRANSLATION_STYLE. Matches the
# livecaption partial-zh convention (grey50, no italic) rather than the final style.
_PREVIEW_STYLE = {
    "default": "grey50",
    "dark": "grey50",
    "light": "grey50",
}
_SPEAKER_PALETTE = {
    "default": ["bold magenta", "bold blue", "bold dark_orange3", "bold red"],
    "dark": ["bold bright_magenta", "bold bright_blue", "bold orange1", "bold bright_red"],
    "light": ["bold magenta", "bold blue", "bold dark_orange3", "bold red"],
}

_MAX_PENDING = 8


def _resolve_theme(theme: str) -> str:
    if theme in ("light", "dark", "default"):
        return theme
    bg = os.environ.get("COLORFGBG", "").split(";")[-1].strip()
    if bg in ("7", "15"):
        return "light"
    if bg.isdigit():
        return "dark"
    return "default"


def _segments_text(segments: list) -> str:
    """Flatten speaker segments to plain text."""
    parts = []
    for seg in segments:
        speaker, text = seg[0], seg[1]
        parts.append(f"[S{speaker + 1}] {text}" if speaker is not None else text)
    return "  ".join(parts)


class TuiRenderer:
    """Rich.Live terminal renderer. Committed captions persist and scroll above
    the live region; the live region shows the in-progress partial + status line.
    """

    def __init__(
        self,
        console: Console | None = None,
        theme: str = "auto",
        show_mem: bool = False,
        translate: bool = True,
        show_ocr: bool = False,
    ):
        self.console = console or Console()
        resolved = _resolve_theme(theme)
        self._sty = {**_COMMON_STYLES, "translation": _TRANSLATION_STYLE[resolved], "preview": _PREVIEW_STYLE[resolved]}
        self._palette = _SPEAKER_PALETTE[resolved]
        self._partials: dict[str, tuple[datetime, str, int | None, Text | None] | None] = {}
        self._lock = threading.Lock()
        self._translate = translate
        self._pending: list[dict] = []
        self._show_mem = show_mem
        self._mx = None
        if show_mem:
            import mlx.core as mx
            self._mx = mx
        self._show_ocr = show_ocr
        self._ocr_text: str = ""
        self._lat_asr: float | None = None
        self._lat_cap: float | None = None
        self._lat_alpha = 0.3
        self._mem_stop = threading.Event()
        self._mem_thread: threading.Thread | None = None
        from rich.live import Live
        self._live = Live(Text(""), console=self.console, refresh_per_second=12, transient=False)

    def __enter__(self) -> "TuiRenderer":
        self._live.start()
        self._live.update(self._render_active())
        self._mem_thread = threading.Thread(target=self._mem_loop, daemon=True, name="tui-tick")
        self._mem_thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._mem_stop.set()
        if self._mem_thread is not None:
            self._mem_thread.join(timeout=2)
        with self._lock:
            self._flush_pending_locked()
            self._partials.clear()
            self._live.update(Text(""))
        self._live.stop()

    def _speaker_style(self, spk: str) -> str:
        try:
            idx = int(spk[1:]) - 1
        except (ValueError, IndexError):
            return self._palette[0]
        return self._palette[min(max(idx, 0), len(self._palette) - 1)]

    def _render_active(self):
        lines = []
        for e in self._pending:
            lines.append(e["en"])
            zh = e["zh"] or e["zh_preview"]
            if zh is not None:
                lines.append(zh)
        for v in self._partials.values():
            if not v:
                continue
            started_at, text, speaker, zh_preview = v
            if not text:
                continue
            line = Text(f"[{started_at:%H:%M:%S}] ", style=self._sty["ts"])
            if speaker is not None:
                line.append(f"[S{speaker + 1}] ", style=self._speaker_style(f"S{speaker + 1}"))
            line.append(text, style=self._sty["partial"])
            lines.append(line)
            if zh_preview is not None:
                lines.append(zh_preview)
        if self._show_ocr:
            lines.append(self._ocr_line())
        if self._show_mem:
            lines.append(self._mem_line())
        return Group(*lines) if lines else Text("")

    def _append_segments(self, line: Text, segments: list, text_style: str) -> None:
        for i, (speaker, text, *rest) in enumerate(segments):
            if i:
                line.append("  ")
            if speaker is not None:
                line.append(f"[S{speaker + 1}] ", style=self._speaker_style(f"S{speaker + 1}"))
            line.append(text, style=text_style)

    def _mem_line(self) -> Text:
        g = 1 / 1e9
        parts = []
        if self._mx is not None:
            parts.append(
                f"MLX  active {self._mx.get_active_memory() * g:.2f} GB"
                f" · cache {self._mx.get_cache_memory() * g:.2f} GB"
                f" · peak {self._mx.get_peak_memory() * g:.2f} GB"
            )
        if self._lat_asr is not None:
            parts.append(f"asr {self._lat_asr:.1f}s")
        if self._lat_cap is not None:
            parts.append(f"cap {self._lat_cap:.1f}s")
        return Text("  ·  ".join(parts), style=self._sty["mem"])

    def _ocr_line(self) -> Text:
        line = Text()
        line.append("[ocr] ", style=self._sty["mem"])
        if self._ocr_text:
            line.append(self._ocr_text, style=self._sty["partial"])
        else:
            line.append("(waiting for slide...)", style=self._sty["mem"])
        return line

    def set_ocr_text(self, text: str | None) -> None:
        with self._lock:
            self._ocr_text = text or ""
            self._live.update(self._render_active())

    def _record_latency(self, started_at: datetime, which: str) -> None:
        lat = (datetime.now() - started_at).total_seconds()
        attr = "_lat_asr" if which == "asr" else "_lat_cap"
        prev = getattr(self, attr)
        setattr(self, attr, lat if prev is None else prev + self._lat_alpha * (lat - prev))

    def _mem_loop(self) -> None:
        while not self._mem_stop.wait(1.0):
            with self._lock:
                self._live.update(self._render_active())

    def partial(self, label: str, text: str, started_at: datetime, speaker: int | None = None) -> None:
        with self._lock:
            prev = self._partials.get(label)
            zh_preview = prev[3] if (prev and prev[0] == started_at) else None
            self._partials[label] = (started_at, text, speaker, zh_preview)
            self._live.update(self._render_active())

    def preview(self, label: str, zh_segments: list, started_at: datetime) -> None:
        line = Text()
        # Strip the Hunyuan placeholder artifact (fullwidth pipes ｜ U+FF5C,
        # e.g. <｜hy_place▁holder▁no▁2｜>) from the provisional so the TUI doesn't
        # show the raw model token; the final translation is clean.
        import re
        zh_segments = [(spk, re.sub(r"<[\|｜][^\|｜]*[\|｜]>", "", zh).strip()) for spk, zh in zh_segments]
        self._append_segments(line, [(spk, zh) for spk, zh in zh_segments], self._sty["preview"])
        with self._lock:
            prev = self._partials.get(label)
            if prev and prev[0] == started_at:
                self._partials[label] = (prev[0], prev[1], prev[2], line)
            else:
                for e in self._pending:
                    if e["zh"] is None and e["label"] == label and e["started_at"] == started_at:
                        e["zh_preview"] = line
                        break
            self._live.update(self._render_active())

    def final(self, label: str, segments: list, started_at: datetime) -> None:
        line = Text()
        line.append(f"[{started_at:%H:%M:%S}] ", style=self._sty["ts"])
        self._append_segments(line, segments, self._sty["final"])
        with self._lock:
            self._record_latency(started_at, "asr")
            prev = self._partials.get(label)
            zh_preview = prev[3] if (prev and prev[0] == started_at) else None
            self._partials[label] = None
            if self._translate:
                self._pending.append(
                    {"label": label, "started_at": started_at, "en": line, "zh": None, "zh_preview": zh_preview}
                )
                self._relieve_pending_locked()
            else:
                self._live.console.print(line)
            self._live.update(self._render_active())

    def _commit_locked(self, entry: dict) -> None:
        en = entry["en"]
        zh = entry["zh"] or entry["zh_preview"]
        self._live.console.print(en)
        if zh is not None:
            self._live.console.print(zh)

    def translation(self, label: str, zh_segments: list, started_at: datetime) -> None:
        line = Text()
        # Strip the Hunyuan placeholder artifact (fullwidth pipes) from finals too;
        # the final is normally clean but strip defensively so the token never shows.
        import re
        zh_segments = [(spk, re.sub(r"<[\|｜][^\|｜]*[\|｜]>", "", zh).strip()) for spk, zh in zh_segments]
        self._append_segments(line, [(spk, zh) for spk, zh in zh_segments], self._sty["translation"])
        with self._lock:
            self._record_latency(started_at, "cap")
            if not self._translate:
                self._live.console.print(line)
                self._live.update(self._render_active())
                return
            for entry in self._pending:
                if entry["zh"] is None and entry["label"] == label and entry["started_at"] == started_at:
                    entry["zh"] = line
                    break
            else:
                return
            while self._pending and self._pending[0]["zh"] is not None:
                self._commit_locked(self._pending.pop(0))
            self._live.update(self._render_active())

    def _relieve_pending_locked(self) -> None:
        while len(self._pending) > _MAX_PENDING:
            self._commit_locked(self._pending.pop(0))

    def _flush_pending_locked(self) -> None:
        for entry in self._pending:
            self._commit_locked(entry)
        self._pending.clear()
        self._translate = False

    def flush_pending(self) -> None:
        with self._lock:
            self._flush_pending_locked()
            self._live.update(self._render_active())

    def run_until(self, stop_event) -> None:
        """No-op: the terminal renderer's rich.Live runs in its own thread. The main thread
        returns immediately in terminal-only mode. When co-existing with the overlay, the
        overlay's run_until is used instead."""
        return


class MultiRenderer:
    """Fan-out: forwards every call to a terminal TuiRenderer and an optional overlay."""

    def __init__(self, terminal: TuiRenderer, overlay: object | None = None) -> None:
        self._terminal = terminal
        self._overlay = overlay

    def __enter__(self) -> "MultiRenderer":
        self._terminal.__enter__()
        if self._overlay is not None:
            self._overlay.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._overlay is not None:
            self._overlay.__exit__(*exc)
        self._terminal.__exit__(*exc)

    def __getattr__(self, name: str):
        if self._overlay is not None and hasattr(self._overlay, name):
            return getattr(self._overlay, name)
        return getattr(self._terminal, name)

    def partial(self, label, text, started_at, speaker=None):
        self._terminal.partial(label, text, started_at, speaker=speaker)
        if self._overlay is not None:
            self._overlay.partial(label, text, started_at, speaker=speaker)

    def final(self, label, segments, started_at):
        self._terminal.final(label, segments, started_at)
        if self._overlay is not None:
            self._overlay.final(label, segments, started_at)

    def translation(self, label, zh_segments, started_at):
        self._terminal.translation(label, zh_segments, started_at)
        if self._overlay is not None:
            self._overlay.translation(label, zh_segments, started_at)

    def preview(self, label, zh_segments, started_at):
        self._terminal.preview(label, zh_segments, started_at)
        if self._overlay is not None:
            self._overlay.preview(label, zh_segments, started_at)

    def flush_pending(self):
        self._terminal.flush_pending()
        if self._overlay is not None:
            self._overlay.flush_pending()

    def set_ocr_text(self, text):
        self._terminal.set_ocr_text(text)
