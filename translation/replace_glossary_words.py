#!/usr/bin/env python3
import os
import json
import argparse
import traceback
import re

supported_languages = {
    "es": "es-ES",
    "de": "de-DE",
    "it": "it-IT",
    "ru": "ru-RU",
    "zh": "zh-ZH",
    "pl": "pl-PL",
    "sv": "sv-SV",
    "fr": "fr-FR",
    "nl": "nl-NL",
}


def _load_glossary(language):
    glossary_folder = f"translation/glossary/{language}"
    glossary = {}
    os.makedirs(os.path.dirname(glossary_folder), exist_ok=True)
    if os.path.exists(glossary_folder):
        for file in os.listdir(glossary_folder):
            file_path = os.path.join(glossary_folder, file)
            if os.path.isfile(file_path) and file_path.endswith(".json"):
                with open(file_path) as f:
                    glossary = json.load(f) | glossary
    return glossary


PROTECTED_KEYS = [
    "savingThrowForcedSpell",
    "savingThrowForced",
    "savingThrow",
    "damageInflict",
    "resist",
]  # in case skill and stats are in glosssary


def replace_glossary_words(data: any, glossary: dict):
    if type(data) is list:
        for idx, element in enumerate(data):
            data[idx] = replace_glossary_words(element, glossary)
    elif type(data) is dict:
        for k, v in data.items():
            if k in PROTECTED_KEYS:
                continue
            # We only translate specific keys from dicts
            if type(v) is str:
                data[k] = replace_glossary_words(v, glossary)
            elif type(v) is dict or list:
                data[k] = replace_glossary_words(v, glossary)
    elif type(data) is str:
        for key, value in glossary.items():
            if re.findall(key, data, flags=re.IGNORECASE):
                pattern = (
                    r"([=\|])(" + re.escape(key) + r"'{0,1}s{0,1})"
                )  # =X (filters) ou |X (tags)
                data = re.sub(pattern, r"\1" + value, data)
                data = re.sub(pattern, r"\1" + value.lower(), data, flags=re.IGNORECASE)

                pattern = (
                    r"(" + re.escape(key) + r"'{0,1}s{0,1}" + r")([\|\}])"
                )  # X| (tags) ou X} (tags close) + often the display name is 's or pluralized
                data = re.sub(pattern, value + r"\2", data)
                data = re.sub(pattern, value.lower() + r"\2", data, flags=re.IGNORECASE)

                if data == key:
                    data = value
                if data.lower() == key.lower():
                    data = value.lower()
    return data


def translate_file(
    language: str,
    fileName: str,
):
    data = {}
    glossary = _load_glossary(language)
    file = fileName.replace("data", f"data.{language}")
    try:
        with open(file) as f:
            data = json.load(f)
        new_data = replace_glossary_words(data, glossary)
    except Exception as e:
        print(repr(e))
        traceback.print_exc()

    with open(file, "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent="\t", ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate json data")
    parser.add_argument("--language", type=str, required=True)
    parser.add_argument("files", type=str, nargs="*")
    args = parser.parse_args()

    if args.language.lower() not in supported_languages:
        raise Exception(
            f"Unsupported language {args.language} - Valid are: {supported_languages.keys()}"
        )

    for file in args.files:
        if file.startswith("data/generated"):
            continue

        translate_file(
            args.language.lower(),
            file,
        )
