"""Evaluate different voices for TTS using predefined voices and text snippets.

Read the text snippets from a file called 'tts_textar.txt' in the current directory.
Read the voices to be evaluated from a file called 'tts_voices.txt' in the current directory.

The text snippets are read from the file line by line, and each line is used as input
to the TTS engine. The text snippets are assumed to be in the Icelandic language.
After generating the audio data for each text snippet, the audio data is saved to a
file in the current directory. The file name is constructed from the sentence read.
The wav file is automatically played back after it has been saved.

After the audio has been played back, the user is prompted to enter a rating for the
voice used to generate the audio. The rating is a number between 1 and 5, where 1 is
the worst and 5 is the best. The rating is saved to a file called 'tts_ratings.tsv'.
Each voice is raited for 'naturalness' and 'correctness'.

The user is prompted to enter a rating for each voice for each text snippet.
The user can also enter 's' to skip the current text snippet, or 'q' to quit the
evaluation process and 'r' to repeat the current sound.

The results are saved continuously to the file 'tts_ratings.tsv'. If the program is
interrupted, the results can be read from this file and the evaluation process can
be resumed at a later time.
"""

from typing import List, Optional

from jsonargparse import CLI

from speak import _die, _fetch_audio_bytes, _is_data_uri, _play_audio_file
from speech import text_to_audio_url
from utility import sanitize_filename

tts_voices_file = "tts_voices.txt"
tts_textar_file = "tts_textar.txt"
tts_ratings_file = "tts_ratings.tsv"


def read_voices() -> List[str]:
    """Read the voices to be evaluated from a file."""
    voices = []
    with open(tts_voices_file) as f:
        for line in f:
            line = line.strip()
            if line:
                voices.append(line)
    return voices


def read_textar() -> List[str]:
    """Read the text snippets to be evaluated from a file."""
    textar = []
    with open(tts_textar_file) as f:
        for line in f:
            line = line.strip()
            if line:
                textar.append(line)
    return textar


def synthezise_speech(text: str, voice: str):
    """Synthesize speech for the given text and voice."""
    text_format = "text"
    audio_format = "mp3"
    # Generate URL
    url = text_to_audio_url(
        text,
        text_format=text_format,
        audio_format=audio_format,
        voice_id=voice,
        speed=1.0,
    )
    if not url:
        _die("Error generating speech synthesis URL.")

    # Download
    urldesc = f"data URI ({len(url)} bytes)" if _is_data_uri(url) else url
    print(f"Fetching {urldesc}")
    data: Optional[bytes] = _fetch_audio_bytes(url)
    if not data:
        _die("Unable to fetch audio data.")

    assert data is not None  # Silence typing complaints

    # Generate file name
    fn = sanitize_filename(text)
    fn = f"{fn}.{audio_format}"

    # Write audio data to file
    print(f'Writing to file "{fn}".')
    with open(fn, "wb") as f:
        f.write(data)
    return fn


def evaluate_voices():
    # Read the voices to be evaluated
    voices = read_voices()
    if not voices:
        _die("No voices to evaluate.")
    texts = read_textar()
    if not texts:
        _die("No text snippets to evaluate.")
    # read the ratings file
    ratings = {}
    try:
        with open(tts_ratings_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    voice, text, naturalness, correctness = line.split("\t")
                    ratings[(voice, text)] = (naturalness, correctness)
    except FileNotFoundError:
        pass
    # Evaluate each voice for each text snippet
    for text in texts:
        for voice in voices:
            # Skip text snippets that have already been rated
            if (voice, text) in ratings:
                print(f"Skipping {voice} for '{text}'")
                continue
            # Synthesize speech
            fn = synthezise_speech(text, voice)
            # Play it
            _play_audio_file(fn)
            # And display the text
            print(f"Text: '{text}'")
            # Prompt user to enter a rating
            while True:
                naturalness = input("Naturalness (1-5): ")
                if naturalness == "r":
                    _play_audio_file(fn)
                    continue
                if naturalness == "q":
                    return
                if naturalness == "s":
                    break
                if naturalness.isdigit():
                    naturalness = int(naturalness)
                    if 1 <= naturalness <= 5:
                        break
            if naturalness == "s":
                continue
            while True:
                correctness = input("Correctness (1-5): ")
                if correctness == "r":
                    _play_audio_file(fn)
                if correctness == "q":
                    return
                if correctness == "s":
                    break
                if correctness.isdigit():
                    correctness = int(correctness)
                    if 1 <= correctness <= 5:
                        break
            if correctness == "s":
                continue
            # Save the rating
            with open(tts_ratings_file, "a") as f:
                f.write(f"{voice}\t{text}\t{naturalness}\t{correctness}\n")
    # Done
    print("Done.")


def report_results():
    """Read the ratings file and report average correctness and naturalness of each voice."""
    # Read the ratings file
    ratings = {}
    try:
        with open(tts_ratings_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    voice, text, naturalness, correctness = line.split("\t")
                    naturalness = int(naturalness)
                    correctness = int(correctness)
                    if voice not in ratings:
                        ratings[voice] = ([], [])
                    ratings[voice][0].append(naturalness)
                    ratings[voice][1].append(correctness)
    except FileNotFoundError:
        _die("No ratings file found.")
    # Report results
    for voice, (naturalness, correctness) in ratings.items():
        print(
            f"{voice}: naturalness={sum(naturalness) / len(naturalness):.2f} correctness={sum(correctness) / len(correctness):.2f}"
        )


def result_stats():
    """Report statistics on the ratings.

    - number of ratings per voice
    - number of ratings per text snippet
    - most difficult (according to correctness) text snippet)
    - most difficult (according to naturalness) text snippet)
    """
    # Read the ratings file
    ratings = {}
    max_count_for_difficulty = 5
    try:
        with open(tts_ratings_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    voice, text, naturalness, correctness = line.split("\t")
                    naturalness = int(naturalness)
                    correctness = int(correctness)
                    if voice not in ratings:
                        ratings[voice] = {}
                    if text not in ratings[voice]:
                        ratings[voice][text] = ([], [])
                    ratings[voice][text][0].append(naturalness)
                    ratings[voice][text][1].append(correctness)
    except FileNotFoundError:
        _die("No ratings file found.")
    # Report results
    print("Number of ratings per voice:")
    for voice, texts in ratings.items():
        print(f"{voice}: {len(texts.values())}")
    # create a better datastructure for texts
    text_raitings = {}
    for voice, texts in ratings.items():
        for text, (naturalness, correctness) in texts.items():
            if text not in text_raitings:
                text_raitings[text] = ([], [])
            text_raitings[text][0].append(sum(naturalness) / len(naturalness))
            text_raitings[text][1].append(sum(correctness) / len(correctness))
    print("Number of ratings per text snippet:")
    for text, (naturalness, correctness) in text_raitings.items():
        print(f"{text}: {len(naturalness)}")
    count = 0
    # sort the texts by correctness
    print("Most difficult (according to correctness) text snippet:")
    for text, (naturalness, correctness) in sorted(
        text_raitings.items(), key=lambda x: sum(x[1][1]) / len(x[1][1]), reverse=False
    ):
        print(f"{text}: {sum(correctness) / len(correctness):.2f}")
        count += 1
        if count >= max_count_for_difficulty:
            break
    count = 0
    # sort the texts by naturalness
    print("Most difficult (according to naturalness) text snippet:")
    for text, (naturalness, correctness) in sorted(
        text_raitings.items(), key=lambda x: sum(x[1][0]) / len(x[1][0]), reverse=False
    ):
        print(f"{text}: {sum(naturalness) / len(naturalness):.2f}")
        count += 1
        if count >= max_count_for_difficulty:
            break


if __name__ == "__main__":
    # jsonargparse exposes the main functions
    CLI([evaluate_voices, report_results, result_stats])
