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


    Icelandic-language text to speech via the Google Cloud API.

"""

# from typing import Optional

# import logging
# import uuid
# from pathlib import Path

# from google.cloud import texttospeech

# from . import AUDIO_SCRATCH_DIR, suffix_for_audiofmt


# NAME = "Google"
# VOICES = frozenset(("Anna",))
# AUDIO_FORMATS = frozenset(("mp3"))


# def text_to_audio_data(
#     text: str,
#     text_format: str,
#     audio_format: str,
#     voice_id: str,
#     speed: float = 1.0,
# ) -> Optional[bytes]:
#     """Feeds text to Google's TTS API and returns audio data received from server."""

#     # Instantiates a client
#     client = texttospeech.TextToSpeechClient()

#     # Set the text input to be synthesized
#     synthesis_input = texttospeech.SynthesisInput(text=text)

#     # Build the voice request, select the language code
#     # and the SSML voice gender.
#     voice = texttospeech.VoiceSelectionParams(
#         language_code="is-IS", ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
#     )

#     # Select the type of audio file you want returned.
#     # We only support mp3 for now.
#     audio_config = texttospeech.AudioConfig(
#         audio_encoding=texttospeech.AudioEncoding.MP3
#     )

#     try:
#         # Perform the text-to-speech request on the text input
#         # with the selected voice parameters and audio file type.
#         response = client.synthesize_speech(
#             input=synthesis_input, voice=voice, audio_config=audio_config
#         )
#         return response.audio_content
#     except Exception as e:
#         logging.error(f"Error communicating with Google Cloud STT API: {e}")


# def text_to_audio_url(
#     text: str,
#     text_format: str,
#     audio_format: str,
#     voice_id: str,
#     speed: float = 1.0,
# ) -> Optional[str]:
#     """Returns URL for speech-synthesized text."""

#     data = text_to_audio_data(**locals())
#     if not data:
#         return None

#     suffix = suffix_for_audiofmt(audio_format)
#     out_fn: str = str(AUDIO_SCRATCH_DIR / f"{uuid.uuid4()}.{suffix}")
#     try:
#         with open(out_fn, "wb") as f:
#             f.write(data)
#     except Exception as e:
#         logging.error(f"Error writing audio file {out_fn}: {e}")
#         return None

#     # Generate and return file:// URL to audio file
#     url = Path(out_fn).as_uri()
#     return url
