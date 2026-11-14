"""The src-row reading buffer (view-side state machine, pure).

SrcReadingBuffer accumulates committed source clauses for the reading row and
suppresses promoted sentences from the live hypothesis. These are view-layer
tests; the caption display policy's own tests live with the model
(test_caption_display.py on the display branch).
"""

# ---- SrcReadingBuffer (the src row state machine, pure) ----

def test_src_buffer_full_zh_long_sequence():
    """Drive the real src buffer through the golden sentence-2 sequence:
    clause commits accumulate, the sentence completes at the terminator,
    the next sentence's words promote it to history."""
    from whisperlivekit.src_buffer import SrcReadingBuffer
    b = SrcReadingBuffer()
    # sentence 1
    assert b.tail("我们今天来讨论") == "我们今天来讨论"
    b.commit("我们今天来讨论")
    assert b.tail("镭射在医学上的应用") == "我们今天来讨论镭射在医学上的应用"
    assert b.commit("镭射在医学上的应用。") == "我们今天来讨论镭射在医学上的应用。"
    assert b.sentence_complete
    # sentence 2 starts: sentence 1 promotes
    assert b.tail("镭射技术可以精确的切除肿瘤组织") == "镭射技术可以精确的切除肿瘤组织"
    assert b.consume_promotion() == "我们今天来讨论镭射在医学上的应用。"
    b.commit("镭射技术可以精确的切除肿瘤组织")
    assert b.tail("减少对周围健康组织的伤害") == "镭射技术可以精确的切除肿瘤组织减少对周围健康组织的伤害"
    assert b.commit("减少对周围健康组织的伤害。") == "镭射技术可以精确的切除肿瘤组织减少对周围健康组织的伤害。"
    assert b.sentence_complete


def test_src_join_cjk_no_space_latin_space():
    from whisperlivekit.src_buffer import src_join
    assert src_join("我们今天来讨论", "镭射在医学上的应用。") == "我们今天来讨论镭射在医学上的应用。"
    assert src_join("Hello everyone.", "My name is Ihab Bilad") == "Hello everyone. My name is Ihab Bilad"
    assert src_join("", "text") == "text"
    assert src_join("text", "") == "text"


def test_src_buffer_suppresses_promoted_sentence_in_tail():
    """After a promote, backends' rolling buffers still carry the promoted
    sentence — it must NOT re-appear as a dim draft in the same row."""
    from whisperlivekit.src_buffer import SrcReadingBuffer
    b = SrcReadingBuffer()
    b.commit("我们今天来讨论镭射在医学上的应用。")   # sentence 1 complete
    # next sentence's words arrive: promote fires, but the raw hypothesis
    # still carries the promoted sentence + the new tail
    display = b.tail("我们今天来讨论镭射在医学上的应用。镭射技术可")
    assert "我们今天来讨论镭射在医学上的应用。" not in display, (
        f"promoted sentence re-appeared in the draft: {display!r}")
    assert display == "镭射技术可", display
    assert b.consume_promotion() == "我们今天来讨论镭射在医学上的应用。"
    # once the hypothesis moves past the promoted text, suppression ends
    display = b.tail("镭射技术可以精确")
    assert display == "镭射技术可以精确"


