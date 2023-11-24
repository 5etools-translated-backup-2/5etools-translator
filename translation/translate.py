#!/usr/bin/env python3
import os
import sys
import re
import json
import time
from signal import signal, SIGINT
import argparse
import traceback

from utils.metric_converter import convertToMetric
from utils.cache_manager import CacheManager
from utils.deepl_translator import DeeplTranslator
from utils.tag_manager import TagManager

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

translatedCharCounter = 0
maxRuntime = 0
startTime = time.time()


class Translator:
    def __init__(
        self,
        language: str,
        cacheFile: str,
        recheckWords: list,
        retranslateGlossaryModified: bool,
        convertToMetricSystem: bool,
        translateTags: bool,
        useCopyPaste: bool,
    ):
        self._language = language
        self._tag_regex = "{.*?}"

        # Were we store the translations cache
        self.fileCache = CacheManager(cacheFilePath=cacheFile)

        # Were we store which glossary was used for a file
        glossaryCachePath = cacheFile.replace(
            f"/cache/{self._language}", f"/cache/{self._language}/glossary_used"
        )
        self.fileGlossaryCache = CacheManager(glossaryCachePath)
        # Same but with detail for each string. It's a temp file. If it is present it means the translation stopped in a middle of a file.
        self.glossaryPerStringCache = CacheManager(
            glossaryCachePath.replace(".json", "_per_string.json")
        )

        # Shared Entities Cache
        self.sharedCache = CacheManager(
            cacheFilePath=f"./cache/{self._language}/shared_cache.json"
        )
        self.sharedGlossaryCache = CacheManager(
            cacheFilePath=f"./cache/{self._language}/shared_cache_glossary_used.json"
        )
        self._recheckWordsForEntities = {}

        self._glossary = {}
        self._recheckWordsFromParams = recheckWords
        self._recheckWords = recheckWords
        self._convertToMetricSystem = convertToMetricSystem
        self._translate_tags = translateTags
        self._use_copy_paste = useCopyPaste
        self._tag_manager = TagManager()
        self._retranslateGlossaryModified = retranslateGlossaryModified
        self._recheckGlossaryForEachString = self.glossaryPerStringCache.cacheData != {}

        self.charCount = 0
        self.cachedCharCount = 0
        self.deepl_translator = None
        self._someTranslationFailed = False

        # We load the new glossary
        self._load_glossary()

        # We are not resuming from a previous run
        if not self._recheckGlossaryForEachString:
            self._add_glossary_changes_to_recheck_words()

        # We calculate the glossary change for entities
        self._recheckWordsForEntities = self._recheck_words_from_glossary_change(
            for_shared_entity_cache=True
        )

    def __enter__(self):
        signal(SIGINT, self._sigint_handler)
        return self

    def _sigint_handler(self, signal_received, frame):
        self.__exit__(None, None, None)
        sys.exit(0)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fileCache.sync()
        self.glossaryPerStringCache.sync()
        self.fileGlossaryCache.sync()
        self.sharedCache.sync()
        self.sharedGlossaryCache.sync()

        if self.deepl_translator:
            self.deepl_translator.quit()

    def _glossary_to_use_for_string(self, text: str) -> dict:
        contains = {}

        for word, translation in self._glossary.items():
            if re.match(r".*\b" + re.escape(word) + r"\b.*", text):
                contains[word] = translation
            # We do not want to add the lowercased value as is causes some weird translations.
            # For example th spell Command: Injonction in french. We do not want command to always be injuction.
            # if re.match(r".*\b" + re.escape(word.lower()) + r"\b.*", text):
            #     contains[word.lower()] = translation.lower()
        return contains

    def _add_glossary_changes_to_recheck_words(self, for_string: str = None):
        if self._retranslateGlossaryModified:
            recheck_words_from_glossary = self._recheck_words_from_glossary_change(
                for_string
            )

            self._recheckWords = list(
                set(self._recheckWordsFromParams + recheck_words_from_glossary)
            )

    def _needs_recheck(self, text: str, use_shared_cache: bool = False) -> bool:
        recheckWords = (
            self._recheckWordsForEntities if use_shared_cache else self._recheckWords
        )
        for word in recheckWords:
            # ignore vars and case
            checkText = re.sub(self._tag_regex, "", text)
            if re.match(r"(?i).*\b" + re.escape(word) + r"\b.*", checkText):
                print(f"{word} in Recheck words found in text.")
                return True

        return False

    # Returns the glossary to use
    def _load_glossary(self):
        glossary_folder = f"translation/glossary/{self._language}"
        glossary = {}
        os.makedirs(os.path.dirname(glossary_folder), exist_ok=True)
        if os.path.exists(glossary_folder):
            for file in os.listdir(glossary_folder):
                file_path = os.path.join(glossary_folder, file)
                if os.path.isfile(file_path) and file_path.endswith(".json"):
                    with open(file_path) as f:
                        glossary = json.load(f) | glossary

        # if a word is lowercased in glossary, we want to match the upper. Ex lawful => Lawful
        # not the other way around because it can cause weird translation and deepL keeps the glossary case. Ex Alarm => alarm
        uppered_glossary = {}
        for word in glossary:
            uppered_glossary[word] = glossary[word]
            if not word[0].isupper():
                uppered_glossary[word.capitalize()] = glossary[word].capitalize()

        # We sort the glossary to have the longuest key first.
        # That way "Orc Chieftain" will be check before "Orc" for since we have limited space
        # Sort the dictionary by key length and then alphabetically
        sorted_glossary = dict(
            sorted(uppered_glossary.items(), key=lambda item: (-len(item[0]), item[0]))
        )
        self._glossary = sorted_glossary

    # Returns new words in glossary, words for which the translation as changed and words that have been removed from the glossary
    def _recheck_words_from_glossary_change(
        self, for_string: str = None, for_shared_entity_cache: bool = False
    ):
        cached_glossary = {}
        if for_shared_entity_cache:
            cached_glossary = self.sharedGlossaryCache.cacheData
        else:
            if for_string:
                # We use the glossary used by this string
                cached_glossary = self.glossaryPerStringCache.get(for_string)

            if not cached_glossary:
                # If not found or if it's not a resume we use the one from previous run
                cached_glossary = self.fileGlossaryCache.cacheData
        recheck_from_glossary = []

        for key in self._glossary:
            if key not in cached_glossary:  # new key
                recheck_from_glossary.append(key)
            elif cached_glossary[key] != self._glossary[key]:  # changed key
                recheck_from_glossary.append(key)
        for key in cached_glossary:
            if key not in self._glossary:  # removed key
                recheck_from_glossary.append(key)
        return recheck_from_glossary

    def translate_tag(self, tag: str) -> str:
        if not self._translate_tags:
            return tag
        parsed_tag = self._tag_manager.parse_tag(tag)
        parsed_tag = self._translate_parsed_tag(parsed_tag)
        return self._tag_manager.unparse_tag(parsed_tag)

    def _translate_parsed_tag(self, parsed_tag: dict) -> dict:
        for idx, part in enumerate(parsed_tag["content"]):
            if parsed_tag["translatable"][idx]:
                # print(f"TAG TRANSLATE: {part}")
                parsed_tag["content"][idx] = self.translate(part)
        return parsed_tag

    def translate(self, text: str, use_shared_cache: bool = False) -> str:
        # Replace tags with placeholders
        text_with_placeholders, tags = self._tag_manager.tags_to_placeholders(text)

        # Convert to metric system
        # We must do it after pladceholders because of item names like rope(10-foot)
        if self._convertToMetricSystem:
            text_with_placeholders = convertToMetric(text_with_placeholders)

        # Translate the tags (if activated)
        for idx, tag in enumerate(tags):
            tags[idx] = self.translate_tag(tag)

        # Do not translate variable only and very short or non alpha texts or string that are entirely tags
        no_placeholder = re.sub(r"[\(%[0-9]%\)[0-9]", "", text_with_placeholders)
        if not re.search(r"[a-zA-Z]{2,}", no_placeholder):
            return self._tag_manager.placeholders_to_tags(text_with_placeholders, tags)

        # If the previous run failed in the middle we resume it using the same glossary
        if self._recheckGlossaryForEachString:
            self._add_glossary_changes_to_recheck_words(
                for_string=text_with_placeholders
            )

        # Serve from cache if present
        cacheFile = self.sharedCache if use_shared_cache else self.fileCache
        if (
            cacheFile.get(text_with_placeholders)
            and len(cacheFile.get(text_with_placeholders)) > 0
        ):
            if self._needs_recheck(
                text=text_with_placeholders, use_shared_cache=use_shared_cache
            ):
                print("Needs recheck")
                print(text)
                print(cacheFile.get(text_with_placeholders))
                cacheFile.delete(text_with_placeholders)
            else:
                translated_text = cacheFile.get(text_with_placeholders)
                if translated_text is not None:
                    self.cachedCharCount += len(text)
                    return self._tag_manager.placeholders_to_tags(translated_text, tags)

        # Serve from glossary if exact match
        if text_with_placeholders in self._glossary or text.lower() in self._glossary:
            translated_text = self._glossary.get(
                text_with_placeholders
            ) or self._glossary.get(text_with_placeholders.lower())
            self._save_translations_to_caches(
                text_with_placeholders, translated_text, use_shared_cache
            )
            return translated_text

        global maxRuntime, startTime
        if maxRuntime != 0 and time.time() - startTime > maxRuntime:
            raise Exception("maximum runtime exceeded - aborting")
        else:
            print(f"Running for {time.time() - startTime}/{maxRuntime}")

        self.charCount += len(text)

        deepl_translator_init_try = 0
        while self.deepl_translator is None and deepl_translator_init_try < 3:
            try:
                if self.deepl_translator is None:
                    self.deepl_translator = DeeplTranslator(
                        "en", self._language, self._use_copy_paste
                    )
            except:
                print("DeepL Translator Init failed")
                deepl_translator_init_try += 1

        glossary_to_use = self._glossary_to_use_for_string(text_with_placeholders)
        translated_text = self.deepl_translator.translate(
            text=text_with_placeholders, glossary=glossary_to_use
        )

        if len(translated_text) > 1:  # If deepL fails and returns ""
            self._save_translations_to_caches(
                text_with_placeholders, translated_text, use_shared_cache
            )

            # Replace back any placeholders for tags
            translated_text = self._tag_manager.placeholders_to_tags(
                translated_text, tags
            )

            return translated_text
        else:
            self._someTranslationFailed = True
            return text

    def _save_translations_to_caches(
        self, text: str, translated_text: str, use_shared_cache: bool = False
    ):
        print(text)
        print(translated_text)
        if use_shared_cache:
            self.sharedCache.set(text, translated_text)
        else:
            self.fileCache.set(text, translated_text)
            self.glossaryPerStringCache.set(text, self._glossary)
        print()


def translate_data(translator: Translator, data):
    if type(data) is list:
        for element in data:
            translate_data(translator, element)
    elif type(data) is dict:
        for k, v in data.items():
            # We only translate specific keys from dicts
            if (
                # TODO? By safety maybe replace and name should use a shared global cache and not one per file.
                k in ["entry", "effect", "text", "m", "capCrewNote"]
                and type(v) is str
            ):
                data[k] = translator.translate(v)
            # We do not translate names that have a source as those a entities, often used in tags.
            elif (
                k in ["name", "names", "replace"]
                and type(v) is str
                and not data.get("source")
            ):
                data[k] = translator.translate(v, use_shared_cache=True)
            elif k == "other" and type(v) is dict:
                # Special hack for life.json
                for section, items in v.items():
                    for idx, item in enumerate(items):
                        data[k][section][idx] = translator.translate(item)
            elif (
                k
                in [
                    "entries",
                    "items",
                    "rows",
                    "headerEntries",
                    "reasons",
                    "other",
                    "lifeTrinket",
                    "row",
                    "headers",
                    "names",
                ]
                and type(v) is list
            ):
                # Do not translate for simple item lists withou type: list (to avoid translating item names)
                if k == "items" and ("type" not in data or data["type"] != "list"):
                    continue

                use_shared_cache = False
                if k in ["headers", "names"]:
                    use_shared_cache = True

                for idx, entry in enumerate(v):
                    if type(entry) is list:
                        for elidx, el in enumerate(entry):
                            if type(el) is str and len(el) > 2:
                                data[k][idx][elidx] = translator.translate(
                                    el, use_shared_cache
                                )

                    if type(entry) is str:
                        data[k][idx] = translator.translate(entry, use_shared_cache)
                    else:
                        translate_data(translator, entry)
            else:
                translate_data(translator, v)


def translate_file(
    language: str,
    fileName: str,
    writeJSON: bool,
    recheckWords: list,
    retranslateGlossaryModified: bool,
    convertToMetricSystem: bool,
    translateTags: bool,
    useCopyPaste: bool,
):
    cache_file = fileName.replace("data/", f"translation/cache/{language}/")
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)

    output_file = fileName.replace("data/", f"data.{language}/")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    data = {}
    with Translator(
        language,
        cache_file,
        recheckWords,
        retranslateGlossaryModified,
        convertToMetricSystem,
        translateTags,
        useCopyPaste,
    ) as translator:
        print(f"Translating\t{file}")
        try:
            with open(fileName) as f:
                data = json.load(f)
            translate_data(translator, data)
            # All strings were translated.
            # Save the glossary used on a file level
            translator.fileGlossaryCache.replaceCacheData(translator._glossary)
            translator.sharedGlossaryCache.replaceCacheData(translator._glossary)
            if not translator._someTranslationFailed:
                print("All strings where sucessfully translated")
                translator.glossaryPerStringCache.replaceCacheData(
                    {}
                )  # Will cause wipe on sync
        except Exception as e:
            print(f"Failed to translate {cache_file}")
            print(repr(e))
            traceback.print_exc()

        print(
            f"From Cache:{translator.cachedCharCount}\Translated: {translator.charCount}"
        )
        global translatedCharCounter
        translatedCharCounter += translator.charCount

    if writeJSON:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent="\t", ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate json data")
    parser.add_argument("--language", type=str, required=True)
    parser.add_argument(
        "--translate",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("--maxrun", type=int, default=False)
    parser.add_argument("--recheck-words", type=str, default=[], nargs="*")
    parser.add_argument(
        "--retranslate-glossary-modified",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--convert-to-metric-system",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--translate-tags",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--use-copy-paste",
        type=bool,
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("files", type=str, nargs="*")
    args = parser.parse_args()
    maxRuntime = args.maxrun

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
            args.translate,
            args.recheck_words,
            args.retranslate_glossary_modified,
            args.convert_to_metric_system,
            args.translate_tags,
            args.use_copy_paste,
        )

    print(f"Total translated: {translatedCharCounter}")
