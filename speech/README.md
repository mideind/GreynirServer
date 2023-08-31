# Speech-To-Text voices

Herein you will find Icelandic-language speech-synthesis code used by Greynir. Voice modules are
found in the `voices` directory. Each module declares the names of the voices it support and
implements the `text_to_audio_data` and `text_to_audio_url` functions.
Functions/methods for performing phonetic transcription are found in the `trans` directory,
along with `speech/__init__.py`. The function `gssml` marks portions of text
which get phonetically transcribed when parsed by `GreynirSSMLParser` from `__init__.py`
