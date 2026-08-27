#!/usr/bin/env python3
"""Wrapper for alignatt-eval that patches omnisteval to use serial execution.

The sandbox blocks multiprocessing semaphores, so we replace
``omnisteval.alignment.align_words`` (which uses ``multiprocessing.Pool``)
with a serial equivalent before calling the evaluate main function.
"""
from __future__ import annotations

import omnisteval.alignment as _align
import importlib
_reseg_mod = importlib.import_module('omnisteval.resegment')
from omnisteval.alignment import _process_single_recording


def _align_words_serial(ref_words, hyp_words, char_level):
    """Serial replacement for omnisteval.alignment.align_words."""
    new_segmentation = {}
    for inst_ref in ref_words:
        for ref in inst_ref:
            if ref.seq_id is not None:
                new_segmentation[ref.seq_id] = []
    args_list = [
        (i, ref, hyp, char_level)
        for i, (ref, hyp) in enumerate(zip(ref_words, hyp_words))
    ]
    results = [_process_single_recording(args) for args in args_list]
    for result in results:
        for word in result:
            if word.seq_id is not None and word.seq_id in new_segmentation:
                new_segmentation[word.seq_id].append(word)
    return new_segmentation


_align.align_words = _align_words_serial
_reseg_mod.align_words = _align_words_serial

from alignatt4llm.cli.evaluate import main

main()
