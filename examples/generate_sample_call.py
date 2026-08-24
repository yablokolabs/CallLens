"""Generate a two-speaker sample call with live ElevenLabs TTS.

No recording handy? Run this to synthesize a short consultative_sales call
(representative + customer), then feed the MP3 to `calllens analyze`:

    python examples/generate_sample_call.py
    calllens analyze sample_call.mp3 --rubric consultative_sales --output report.json

Requires `ELEVENLABS_API_KEY` in the environment (or `.env`), `ffmpeg` on PATH,
and the ElevenLabs SDK (`pip install -e ".[dev]"`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from calllens.config import get_settings
from calllens.providers.speech.elevenlabs.client import (
    ElevenLabsNotConfigured,
    get_elevenlabs_client,
)

# (role, line) — alternate between representative and customer.
SCRIPT: list[tuple[str, str]] = [
    (
        "rep",
        "Hi Sarah, thanks for taking the time to talk today. I know you're busy, so "
        "let's jump right in. What's the biggest operational bottleneck you're "
        "dealing with right now?",
    ),
    (
        "cust",
        "Thanks for calling. Yeah, we're still doing manual reporting, and it eats "
        "up about twelve hours a week for my team.",
    ),
    ("rep", "Interesting. And how long has that been affecting your team?"),
    ("cust", "Honestly, it's been like this for over a year now."),
    (
        "rep",
        "Got it. If we could cut that reporting time in half, what would that mean "
        "for your bottom line?",
    ),
    ("cust", "It would probably save us around forty thousand dollars a year."),
    (
        "rep",
        "Great. Based on what you've told me, I think we can get you there within "
        "sixty days. Does that timeline work for you?",
    ),
    ("cust", "That timeline sounds good to me. Let's do it."),
]

PAUSE_SECS = 0.5  # silence between turns so Scribe separates speakers cleanly


def _pick_voices(client) -> tuple[object, object]:
    """Return (rep_voice, customer_voice), preferring one male and one female."""
    voices = client.voices.get_all().voices
    if len(voices) < 2:
        raise SystemExit(f"need at least 2 voices, got {len(voices)}")
    by_gender: dict[str, object] = {}
    for v in voices:
        label = (getattr(v, "labels", None) or {})
        gender = (label.get("gender") or "").lower()
        if gender in ("male", "female") and gender not in by_gender:
            by_gender[gender] = v
    return by_gender.get("male", voices[0]), by_gender.get("female", voices[-1])


def main() -> None:
    settings = get_settings()
    try:
        client = get_elevenlabs_client(settings)
    except ElevenLabsNotConfigured as exc:
        raise SystemExit(f"{exc}\nSet ELEVENLABS_API_KEY in .env and try again.") from exc

    rep_voice, cust_voice = _pick_voices(client)
    tmp = Path("examples/.sample_segments")
    tmp.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    for i, (role, text) in enumerate(SCRIPT):
        voice_id = rep_voice.voice_id if role == "rep" else cust_voice.voice_id
        print(f"[{i:02d}] {role} ({voice_id}): {text[:60]}...")
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=settings.elevenlabs_tts_model,
            output_format="mp3_44100_128",
        )
        seg = tmp / f"{i:02d}_{role}.mp3"
        seg.write_bytes(b"".join(audio))
        segments.append(seg)

    # Concatenate the segments with a short pause between each turn.
    inputs: list[str] = []
    for seg in segments:
        inputs += ["-i", str(seg)]
    filters = [f"[{i}:a]apad=pad_dur={PAUSE_SECS}[a{i}]" for i in range(len(segments))]
    joined = "".join(f"[a{i}]" for i in range(len(segments)))
    filters.append(f"{joined}concat=n={len(segments)}:v=0:a=1[out]")
    out = Path("sample_call.mp3")
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]", str(out)],
        check=True,
        capture_output=True,
    )
    for seg in segments:
        seg.unlink()
    tmp.rmdir()
    print(f"\nCreated {out} ({len(SCRIPT)} turns, rep={rep_voice.name}, cust={cust_voice.name})")
    print(f"Next: calllens analyze {out} --rubric consultative_sales --output report.json")


if __name__ == "__main__":
    main()
