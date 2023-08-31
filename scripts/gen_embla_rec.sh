#!/usr/bin/env bash
#
# Script to generate local voice recordings for the Embla voice assistant
#

set -o errexit   # Exit when a command fails
# set -o nounset   # Disallow unset variables

if [[ $# = 0 ]]; then
    echo "You must provide a voice name as argument"
    exit 1
fi

VOICE=$1
VOICE_LOWER=$( echo "$VOICE" | tr '[:upper:]' '[:lower:]' )

# Dunno variants
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno01-${VOICE_LOWER}.wav" "Ég get ekki svarað því."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno02-${VOICE_LOWER}.wav" "Ég get því miður ekki svarað því."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno03-${VOICE_LOWER}.wav" "Ég kann ekki svar við því."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno04-${VOICE_LOWER}.wav" "Ég skil ekki þessa fyrirspurn."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno05-${VOICE_LOWER}.wav" "Ég veit það ekki."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno06-${VOICE_LOWER}.wav" "Því miður skildi ég þetta ekki."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "dunno07-${VOICE_LOWER}.wav" "Því miður veit ég það ekki."

# Error messages
python3 speak.py -w -f "pcm" --voice "$1" -n --override "err-${VOICE_LOWER}.wav" "Villa kom upp í samskiptum við netþjón."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "conn-${VOICE_LOWER}.wav" "Ekki næst samband við netið."
python3 speak.py -w -f "pcm" --voice "$1" -n --override "nomic-${VOICE_LOWER}.wav" "Mig vantar heimild til að nota hljóðnema."

# My name is
python3 speak.py -w -f "pcm" --voice "$1" -n --override "mynameis-${VOICE_LOWER}.wav" "Svona hljómar þessi rödd."

# Voice speed
python3 speak.py -w -f "pcm" --voice "$1" -n --override "voicespeed-${VOICE_LOWER}.wav" "Svona hljómar þessi hraði."
