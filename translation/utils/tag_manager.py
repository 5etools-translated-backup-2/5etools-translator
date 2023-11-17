import re


class TagManager:
    # We decompose the tag in a more suitable structure.
    # keyword: the keyword
    # content: an array for each | separated portion of the tag
    # Ex @{highlight You can cast the @{spell Mage Hand|PHB|mage hand} twice a day|Hello world}
    # {
    #     "keyword": "highlight",
    #     "content": [
    #             "You can cast the @{spell Mage Hand|PHB|mage hand} twice a day",
    #             "Hello world",
    #     ],
    # }
    _tag_regex = r"{[#@=][^{}]*?}"  # {#itemEntry} {=amount1/V} {@keyword ...}

    def parse_tag(self, tag: dict) -> dict:
        parsed = self._parse_tag(tag)
        tran = self._add_translatable_info(parsed)
        return tran

    def unparse_tag(self, parsed_tag):
        tag = "{"
        tag += parsed_tag["keywordchar"]
        tag += parsed_tag["keyword"]
        if len(parsed_tag["content"]) > 0:
            tag += " "
        tag += "|".join(parsed_tag["content"])
        tag += "}"
        return tag

    def tags_to_placeholders(self, text: str) -> tuple[str, list]:
        # Replace links with specific markers we can put in place after translating later
        links = []
        count = 0
        link = re.search(self._tag_regex, text)
        while link is not None:
            links.append(link.group(0))
            text = re.sub(self._tag_regex, f"(%{count}%)", text, 1)
            count += 1
            link = re.search(self._tag_regex, text)

        return text, links

    def placeholders_to_tags(self, text: str, tags: list) -> str:
        # We start with the latest tag in case of imbricated tags
        for idx, tag in enumerate(tags[::-1]):
            text = re.sub(f"\(%{len(tags)-1-idx}%\)", tag, text)

        return text

    def _parse_tag(self, string):
        # print(f"Parsing {string}")
        out = {}

        keyword_idx = string.find(" ")
        if keyword_idx == -1:
            keyword_idx = len(string) - 1  # {=amount1/v}
        out["type"] = "tag"
        out["keywordchar"] = string[1:2]
        out["keyword"] = string[2:keyword_idx]
        out["content"] = []
        string = string[keyword_idx + 1 :]

        i = 0
        current_string = ""
        open_tag_count = 0

        while i < len(string):
            char = string[i]
            if i < len(string) - 1:
                char2 = string[i + 1]

            if i == len(string) - 1:  # Closing }
                out["content"].append(current_string)
                current_string = ""

            if char == "{" and char2 == "@":  # There is an subtag
                current_string += char
                open_tag_count += 1

            elif char == "}":
                current_string += char
                if open_tag_count > 0:
                    open_tag_count -= 1

            elif open_tag_count > 0:
                current_string += char

            # We reached the end of the part
            elif char == "|":
                out["content"].append(current_string)
                current_string = ""

            else:
                current_string = current_string + char

            i += 1
        return out

    def _is_tag_translatable(self, tag_keyword):
        # Returns the tag structure to know which part we can translate
        # Does not necessarily return the whole lenght. if unfound consider False
        # Return True if the |-separated part is translatable without risk (ie display text), else False
        # Refer to render.js or renderdemo.json
        # Sometime we choose not to translate the displayText since it is usually a variant of a noun. Mostly we translate only formatting tags
        match tag_keyword:
            case "b" | "bold" | "i" | "italic" | "s" | "strike" | "u" | "underline" | "sup" | "sub" | "kbd" | "code" | "note" | "comic" | "comicH1" | "comicH2" | "comicH3" | "comicH4" | "comicNote" | "dcYourSpellSave" | "hitYourSpellAttack":
                # {@tag displayText}
                return [True]
            case "font" | "style" | "color" | "highlight":
                # {@tag displayText|value}
                return [True, False]
            case "help":
                # {@help text|title}
                return [True, True]
            case "dice" | "autodice" | "damage" | "hit" | "d20" | "chance" | "recharge":
                # [rollText, displayText, name, ...others]
                return [False, True]
            case "ability" | "savingThrow", "skillCheck":
                # {@ability str 20|Display Text|Roll Name Text}
                return [False, True]
            case "coinflip":
                # {@coinflip display text|rollbox rollee name|success text|failure text}
                return [True, False, True, True]
            case "unit":
                # {@unit {=amount1/v|singular|plural}}
                return [False, True, True]
            case "dc":
                # [dcText, displayText]
                return [False, True]
            case "filter" | "link" | "5etools":
                # {@filter display text|page_without_file_extension|filter_name_1=filter_1_value_1;filter_1_value_2;...filter_1_value_n|...|filter_name_m=filter_m_value_1;filter_m_value_2;...}
                return [True, False]
            case "footnote":
                # [displayText, footnoteText, optTitle]
                return [True, True, True]
            case "area":
                # {@area area_name|id|mods}
                return []
            case "book" | "adventure":
                #  {@tag Display Text|DMG< |chapter< |section >< |number > >}
                # Choose not to translate as it's often a noun
                # return [True, False, False, False]
                return []
            case "class":
                # Class seems a bit complicated. Though it seems to be in _TagPipedDisplayTextThird below
                # {@class fighter} assumes PHB by default, {@class artificer|uaartificer} can have sources added with a pipe, {@class fighter|phb|optional link text added with another pipe}, {@class fighter|phb|subclasses added|Eldritch Knight} with another pipe, {@class fighter|phb|and class feature added|Eldritch Knight|phb|2-0} with another pipe (first number is level index (0-19), second number is feature index (0-n)).",
                return []
            case "action" | "background" | "boon" | "charoption" | "condition" | "creature" | "cult" | "disease" | "feat" | "hazard" | "item" | "itemMastery" | "language" | "legroup" | "object" | "optfeature" | "psionic" | "race" | "recipe" | "reward" | "vehicle" | "vehicleupgrade" | "sense" | "skill" | "spell" | "status" | "trap" | "variantrule":
                # _TagPipedDisplayTextThird in render.js
                # Choose not to translate as it's often a noun or a plural
                # return [False, False, True]
                return []
            case "table":
                # _TagPipedDisplayTextThird in render.js
                return [False, False, True]
            case "card" | "deity":
                # _TagPipedDisplayTextFourth in render.js
                # Choose not to translate as it's often a noun
                # return [False, False, False, True]
                return []
            case "classFeature":
                # _TagPipedDisplayTextSixth in render.js
                # Choose not to translate
                # return [False, False, False, False, False, True]
                return []
            case "subclassFeature":
                # _TagPipedDisplayTextEight in render.js
                # Choose not to translate
                # return [False, False, False, False, False, False, False, True]
                return []
            case "quickref":
                # {@quickref Adventuring Gear|PHB|1|0|Display Text}
                return [False, False, False, False, True]
            case "loader" | "atk" | "homebrew" | "scaledamage" | "scaledice" | "m" | "h"| "amount" | "deck" | "scaledamage" |"scaledice" :
                return []
            case _:
                print(f"TAG: Unknown=> {tag_keyword}")
                return []

    def _add_translatable_info(self, parsed_tag):
        keyword = parsed_tag["keyword"]
        content = parsed_tag["content"]
        translatable_info = []

        for part_index, _ in enumerate(content):
            translatable = False
            if part_index < len(self._is_tag_translatable(keyword)):
                translatable = self._is_tag_translatable(keyword)[part_index]
            translatable_info.append(translatable)
        parsed_tag["translatable"] = translatable_info
        return parsed_tag
