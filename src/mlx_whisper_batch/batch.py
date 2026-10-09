"""Batch orchestration: scan folder, transcribe, log timings."""

from __future__ import annotations

import time
from pathlib import Path

from mlx_whisper_batch.audio import (
    audio_duration_secs,
    collect_audio_files,
    format_mmss,
    needs_transcription,
    realtime_factor,
    require_cmd,
)
from mlx_whisper_batch.outputs import fix_whisper_output_names, remove_outputs, write_result_files
from mlx_whisper_batch.settings import Settings
from mlx_whisper_batch.transcribe import RepeatLoopDetected, transcribe_with_retry


def append_timing_log(
    log_file: Path,
    audio_file: Path,
    audio_mmss: str,
    whisper_mmss: str,
    factor: str,
    *,
    attempt: int | None = None,
) -> None:
    extra = f" attempt={attempt}" if attempt is not None and attempt > 1 else ""
    line = f"{audio_file} {audio_mmss} {whisper_mmss} {factor}{extra}"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"timing: {line}", flush=True)


def run_batch(settings: Settings) -> int:
    directory = settings.directory.resolve()
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", flush=True)
        return 2

    require_cmd("ffprobe")
    if not settings.dry_run:
        require_cmd("ffmpeg")

    log_file = directory / settings.log_name
    files = collect_audio_files(
        directory,
        recursive=settings.recursive,
        extensions=settings.audio_extensions,
    )

    count = 0
    skipped = 0
    failed = 0

    for audio in files:
        if not needs_transcription(audio, force=settings.force):
            skipped += 1
            continue

        count += 1
        try:
            audio_secs = audio_duration_secs(audio)
        except RuntimeError as exc:
            print(f"failed (no ffprobe duration): {audio} ({exc})", flush=True)
            failed += 1
            continue

        audio_mmss = format_mmss(audio_secs)
        if settings.dry_run:
            print(f"would transcribe: {audio} ({audio_mmss})", flush=True)
            continue

        print(f"==> [{count}] {audio} ({audio_mmss})", flush=True)
        t0 = time.perf_counter()
        attempt = 1
        try:
            remove_outputs(audio)
            result, attempt = transcribe_with_retry(
                audio,
                settings,
                audio_duration=audio_secs,
                # True → live segments; False → silent (None), not mlx progress bars
                verbose=True if settings.verbose else None,
            )
            whisper_secs = time.perf_counter() - t0
            whisper_mmss = format_mmss(whisper_secs)
            factor = realtime_factor(whisper_secs, audio_secs)
            append_timing_log(
                log_file,
                audio,
                audio_mmss,
                whisper_mmss,
                factor,
                attempt=attempt,
            )
            write_result_files(audio, result)
            fix = fix_whisper_output_names(
                audio,
                audio_extensions=settings.audio_extensions,
            )
            txt = audio.with_suffix(".txt")
            if fix.renamed > 0:
                print(f"ok: renamed outputs -> {txt}", flush=True)
            else:
                print(f"ok: {txt}", flush=True)
        except RepeatLoopDetected as exc:
            whisper_secs = time.perf_counter() - t0
            append_timing_log(
                log_file,
                audio,
                audio_mmss,
                format_mmss(whisper_secs),
                realtime_factor(whisper_secs, audio_secs),
                attempt=attempt,
            )
            remove_outputs(audio)
            print(f"failed (repeat loop): {audio}: {exc}", flush=True)
            failed += 1
        except Exception as exc:  # noqa: BLE001 — batch continues
            whisper_secs = time.perf_counter() - t0
            append_timing_log(
                log_file,
                audio,
                audio_mmss,
                format_mmss(whisper_secs),
                realtime_factor(whisper_secs, audio_secs),
                attempt=attempt,
            )
            print(f"failed: {audio}: {exc}", flush=True)
            failed += 1

    if settings.dry_run:
        print(
            f"dry-run: {count} file(s) pending ({skipped} already have .txt)",
            flush=True,
        )
        return 0

    print(
        f"done: {count} processed, {failed} failed, {skipped} skipped",
        flush=True,
    )
    print(f"timing log: {log_file}", flush=True)
    return 1 if failed else 0
