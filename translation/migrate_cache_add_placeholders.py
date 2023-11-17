#!/usr/bin/env python3
import os
import json
import argparse

from utils.tag_manager import TagManager


def migrate(
    language: str,
    fileName: str,
):
    cache_file = fileName.replace("data/", f"translation/cache/{language}/")
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    tag_manager = TagManager()
    data = {}
    try:
        with open(cache_file) as f:
            data = json.load(f)

        data2 = {}
        for k, v in data.items():
            text, tags = tag_manager.tags_to_placeholders(k)
            text2, tags2 = tag_manager.tags_to_placeholders(v)
            data2[text] = text2

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data2, f, indent="\t", ensure_ascii=False)
    except:
        print()
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate json data")
    parser.add_argument("--language", type=str, required=True)
    parser.add_argument("files", type=str, nargs="*")
    args = parser.parse_args()

    for file in args.files:
        if file.startswith("data/generated"):
            continue

        migrate(args.language.lower(), file)
