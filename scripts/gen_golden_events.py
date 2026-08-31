#!/usr/bin/env python3
"""Generate the golden event streams from a per-clause spec.

The goldens encode the IDEAL timeline, NOT what the current models achieve.
Lags are the irreducible floor (causality: a translation cannot precede the
ASR event it translates; a release cannot precede the commit that enables
it). The delta between a captured stream and the golden is then the honest
gap between the live system and the ideal UX — not a rubber stamp of today's
model latencies.

Ideal timing (seconds):
  ASR_PROV_LAG     = 0.2  ASR provisional appears this long into a clause
                          (perception-level streaming; ideal is near-instant)
  MT_DRAFT_LAG     = 0.1  translation draft appears almost immediately after
                          ASR has the words (ideal MT ~= free)
  COMMIT_STABILIZE = 0.1  stable-prefix confirmation after a clause is spoken
  RELEASE_LAG      = 0.0  AlignAtt release from cached attention (free)
  MT_FINAL_LAG     = 0.2  final polish after the sentence commits

Clause speech durations: zh at 3.7 chars/s, en at 3.0 words/s (measured from
the source audio: zh_long 116 chars/31.6s, demo_en ~90 words/30s). Speech
rate includes natural pauses; no extra inter-sentence gap is added.

Contract (see _work/COMPACTION_SURVIVAL.md):
  - translation_provisional may draft over committed + tail (everything the
    ASR has produced), never beyond it.
  - `committed` field = source span AlignAtt has RELEASED against; must not
    exceed the cumulative transcription_final text at that timestamp.
  - fresh=true on the first draft of a sentence (new MT pass); fresh=false
    on releases from cached attention as the committed boundary advances.
"""
import json, pathlib

OUT = pathlib.Path("tests/golden")

ASR_PROV_LAG, MT_DRAFT_LAG = 0.2, 0.1
COMMIT_STABILIZE, RELEASE_LAG, MT_FINAL_LAG = 0.1, 0.0, 0.2

def emit(path, sentences, rate, unit):
    lines, t = [], 1.0  # audio starts at 1.0s (leading silence)
    for clauses, final_tgt in sentences:
        durs = [(len(src) / rate if unit == "chars" else len(src.split()) / rate) for src, _ in clauses]
        committed_src = ""
        for i, ((src, tgt_cum), d) in enumerate(zip(clauses, durs)):
            cstart, cend = t, t + d
            lines.append({"t": 0.0, "audio_t": round(cstart + ASR_PROV_LAG, 1),
                          "type": "transcription_provisional", "text": src})
            committed_now = committed_src + src
            lines.append({"t": 0.0, "audio_t": round(cstart + ASR_PROV_LAG + MT_DRAFT_LAG, 2),
                          "type": "translation_provisional", "text": tgt_cum,
                          "committed": committed_src, "source": committed_now,
                          "fresh": i == 0})
            committed_src = committed_now
            lines.append({"t": 0.0, "audio_t": round(cend + COMMIT_STABILIZE, 2),
                          "type": "transcription_final", "text": committed_src})
            if i < len(clauses) - 1:
                lines.append({"t": 0.0, "audio_t": round(cend + COMMIT_STABILIZE + RELEASE_LAG, 2),
                              "type": "translation_provisional", "text": tgt_cum,
                              "committed": committed_src, "source": committed_src, "fresh": False})
            t = cend
        # sentence-final: append terminator
        term = "。" if any("\u4e00" <= ch <= "\u9fff" for ch in committed_src[-1]) else "."
        committed_src = committed_src + term
        lines.append({"t": 0.0, "audio_t": round(t + COMMIT_STABILIZE, 2),
                      "type": "transcription_final", "text": committed_src})
        lines.append({"t": 0.0, "audio_t": round(t + COMMIT_STABILIZE + MT_FINAL_LAG, 2),
                      "type": "translation_final", "text": final_tgt})
        t += 0.0  # inter-sentence pause is already inside the measured rate
    with open(OUT / path, "w") as f:
        for e in lines:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return lines

ZH = [
    ([("我们今天来讨论", "Today we will discuss"),
      ("镭射在医学上的应用", "Today, we will discuss the applications of laser technology in medicine")],
     "Today, we will discuss the applications of laser technology in medicine."),
    ([("镭射技术可以精确的切除肿瘤组织", "Laser technology can precisely remove tumor tissue"),
      ("减少对周围健康组织的伤害", "Laser technology can precisely remove tumor tissue, reducing damage to surrounding healthy tissue")],
     "Laser technology can precisely remove tumor tissue, reducing damage to surrounding healthy tissue."),
    ([("在眼科手术中，镭射用来矫正视力", "In eye surgery, lasers are used to correct vision"),
      ("治疗近视和远视", "In eye surgery, lasers are used to correct vision, treating myopia and farsightedness")],
     "In eye surgery, lasers are used to correct vision, treating myopia and farsightedness."),
    ([("牙医也使用镭射来进行口腔手术", "Dentists also use lasers for oral surgery"),
      ("减少出血", "Dentists also use lasers for oral surgery, reducing bleeding")],
     "Dentists also use lasers for oral surgery, reducing bleeding."),
    ([("皮肤科用镭射去除斑点", "Dermatology uses lasers to remove spots"),
      ("和纹身", "Dermatology uses lasers to remove spots and tattoos")],
     "Dermatology uses lasers to remove spots and tattoos."),
    ([("总之，镭射在现代医学中扮演着越来越重要的角色", "In summary, lasers play an increasingly important role in modern medicine"),
      ("未来的应用将更加广泛", "In summary, lasers play an increasingly important role in modern medicine, with future applications becoming even more widespread")],
     "In summary, lasers play an increasingly important role in modern medicine, with future applications becoming even more widespread."),
]

EN = [
    ([("Hello everyone.", "大家好。"),
      ("My name is Ihab Bilad", "大家好。我叫Ihab Bilad"),
      ("and I will give a short overview of the paper", "大家好。我叫Ihab Bilad，我将简要介绍这篇论文"),
      ("\"Prompting Parm from Translation: Assessing Strategies and Performance.\"", "大家好。我叫Ihab Bilad，我将简要介绍这篇论文《Prompting Parm from Translation: 评估策略与性能》。")],
     "大家好。我叫Ihab Bilad，我将简要介绍这篇论文《Prompting Parm from Translation: 评估策略与性能》。"),
    ([("This is joint work with my colleagues", "这是我与同事们共同完成的工作"),
      ("from Google Translate.", "这是我与Google Translate的同事们共同完成的工作。")],
     "这是我与Google Translate的同事们共同完成的工作。"),
    ([("Parm is a 540 billion parameters large language model", "Parm是一个拥有5400亿参数的大型语言模型"),
      ("presented last year in 2022.", "Parm是一个拥有5400亿参数的大型语言模型，于2022年发布。")],
     "Parm是一个拥有5400亿参数的大型语言模型，于2022年发布。"),
    ([("It's trained on a large collection of text", "它在一个大型文本集合上训练"),
      ("comprising 780 billion tokens.", "它在一个大型文本集合上训练，包含7800亿个token。")],
     "它在一个大型文本集合上训练，包含7800亿个token。"),
    ([("At the time of publication, it achieves state of the art", "在发表时，它达到了当时的最佳水平"),
      ("in hundreds of NLP tasks.", "在发表时，它在数百个NLP任务上达到了当时的最佳水平。")],
     "在发表时，它在数百个NLP任务上达到了当时的最佳水平。"),
]

if __name__ == "__main__":
    a = emit("zh_long_ideal.jsonl", ZH, rate=3.7, unit="chars")
    b = emit("demo_en_30s_ideal.jsonl", EN, rate=3.0, unit="words")
    for name, ev in (("zh→en", a), ("en→zh", b)):
        finals = sum(1 for e in ev if e["type"] == "translation_final")
        provs = [e for e in ev if e["type"] == "translation_provisional"]
        fresh = sum(1 for e in provs if e["fresh"])
        last_t = max(e["audio_t"] for e in ev)
        first_en = next(e["audio_t"] for e in ev if e["type"] == "translation_provisional")
        print(f"{name}: {len(ev)} events, {finals} finals, {len(provs)} prov ({first_en if False else first_en}s first provisional), last audio_t={last_t}")
