#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    Friendly command line interface for Icelandic speech synthesis.
    Returns 0 on success, 1 on error.

    Run the following command for a list of options:

        ./speak.py --help

"""

from typing import Optional, cast, List

import sys
import subprocess
import logging
from pathlib import Path
from shutil import which
from urllib.request import urlopen
import wave

import requests

from speech import (
    text_to_audio_url,
    DEFAULT_VOICE,
    SUPPORTED_VOICES,
    DEFAULT_TEXT_FORMAT,
    DEFAULT_AUDIO_FORMAT,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_TEXT_FORMATS,
)
from speech.voices import suffix_for_audiofmt
from utility import sanitize_filename


def _die(msg: str, exit_code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(exit_code)


_DATA_URI_PREFIX = "data:"


def _is_data_uri(s: str) -> bool:
    """Returns whether a URL is a data URI (RFC2397). Tolerates upper/mixed case prefix."""
    return s[: len(_DATA_URI_PREFIX)].lower() == _DATA_URI_PREFIX


def _is_file_uri(s: str) -> bool:
    """Returns whether a URL is a file URI (RFC8089)."""
    return s.startswith("file://")


def _bytes4file_or_data_uri(uri: str) -> bytes:
    """Returns bytes of file at file URI (RFC8089) or in data URI (RFC2397)."""
    with urlopen(uri) as response:
        return response.read()


def _fetch_audio_bytes(url: str) -> Optional[bytes]:
    """Returns bytes of audio file at URL."""
    if _is_data_uri(url) or _is_file_uri(url):
        return _bytes4file_or_data_uri(url)

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            raise Exception(
                f"Received HTTP status code {r.status_code} when fetching {url}"
            )
        return r.content
    except Exception as e:
        logging.error(f"Error fetching audio file: {e}")


def _write_wav(
    fn: str, data: bytes, num_channels=1, sample_width=2, sample_rate=16000
) -> None:
    """Write audio data to WAV file. Defaults to 16-bit mono 16 kHz PCM."""
    with wave.open(fn, "wb") as wav:
        wav.setnchannels(num_channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(data)


def _play_audio_file(path: str) -> None:
    """Play audio file at path via command line player. This only works
    on systems with afplay (macOS), mpv, mpg123 or cmdmp3 installed."""

    AFPLAY = "/usr/bin/afplay"  # afplay is only present on macOS systems
    MPV = which("mpv")  # mpv is a cross-platform player
    MPG123 = which("mpg123")  # mpg123 is a cross-platform player
    CMDMP3 = which("cmdmp3")  # cmdmp3 is a Windows command line mp3 player

    cmd: Optional[List[str]] = None
    if Path(AFPLAY).is_file():
        cmd = [AFPLAY, path]
    elif MPV:
        cmd = [MPV, path]
    elif MPG123:
        cmd = [MPG123, "--quiet", path]
    elif CMDMP3:
        cmd = [CMDMP3, path]

    if not cmd:
        _die("Couldn't find suitable command line audio player.")

    print(f"Playing file '{path}'")
    subprocess.run(cast(List[str], cmd))


DEFAULT_TEXT = ["Góðan daginn og til hamingju með lífið."]


def main() -> None:
    """Main program function."""
    from argparse import ArgumentParser

    parser = ArgumentParser()

    parser.add_argument(
        "-v",
        "--voice",
        help="specify which voice to use",
        default=DEFAULT_VOICE,
        choices=list(SUPPORTED_VOICES),
    )
    parser.add_argument(
        "-l",
        "--list-voices",
        help="print list of supported voices",
        action="store_true",
    )
    parser.add_argument(
        "-f",
        "--audioformat",
        help="select audio format",
        default=DEFAULT_AUDIO_FORMAT,
        choices=list(SUPPORTED_AUDIO_FORMATS),
    )
    parser.add_argument(
        "-s",
        "--speed",
        help="set speech speed",
        default=1.0,
        type=float,
    )
    parser.add_argument(
        "-t",
        "--textformat",
        help="set text format",
        default=DEFAULT_TEXT_FORMAT,
        choices=list(SUPPORTED_TEXT_FORMATS),
    )
    parser.add_argument(
        "-o",
        "--override",
        help="override default audio output filename",
        default="",  # Empty string means use default filename
    )
    parser.add_argument(
        "-w", "--wav", help="generate WAV file from PCM", action="store_true"
    )
    parser.add_argument(
        "-u", "--url", help="dump audio URL to stdout", action="store_true"
    )
    parser.add_argument(
        "-n", "--noplay", help="do not play resulting audio file", action="store_true"
    )
    parser.add_argument(
        "-r", "--remove", help="remove audio file after playing", action="store_true"
    )
    parser.add_argument(
        "text",
        help="text to synthesize",
        nargs="*",
        default=DEFAULT_TEXT,
    )

    args = parser.parse_args()

    if args.list_voices:
        for voice in SUPPORTED_VOICES:
            print(voice)
        sys.exit(0)

    if len(args.text) == 0:
        _die("No text provided.")
    text = " ".join(args.text).strip()
    if len(text) == 0:
        _die("No text provided.")

    if args.wav and args.audioformat != "pcm":
        _die("WAV output flag only supported for PCM format.")

    # Synthesize the text according to CLI options
    url = text_to_audio_url(
        text,
        text_format=args.textformat,
        audio_format=args.audioformat,
        voice_id=args.voice,
        speed=args.speed,
    )
    if not url:
        _die("Error generating speech synthesis URL.")

    # Command line flag specifies that we should just dump the URL to stdout
    if args.url:
        print(url)
        sys.exit(0)

    # Download
    urldesc = f"data URI ({len(url)} bytes)" if _is_data_uri(url) else url
    print(f"Fetching {urldesc}")
    data: Optional[bytes] = _fetch_audio_bytes(url)
    if not data:
        _die("Unable to fetch audio data.")

    assert data is not None  # Silence typing complaints

    if args.override:
        # Override default filename
        fn = args.override
    else:
        # Generate file name
        fn = sanitize_filename(text)
        fn = f"{fn}.{suffix_for_audiofmt(args.audioformat)}"

    # Write audio data to file
    print(f'Writing to file "{fn}".')
    if args.wav:
        _write_wav(fn, data)
    else:
        with open(fn, "wb") as f:
            f.write(data)

    # Play audio file using command line tool (if available)
    if not args.noplay:
        _play_audio_file(fn)

    # Remove file after playing
    if args.remove:
        print(f'Deleting file "{fn}".')
        Path(fn).unlink()


if __name__ == "__main__":
    """Perform speech synthesis of Icelandic text via the command line."""
    main()
