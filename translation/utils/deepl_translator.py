import os
import time
from sys import platform

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import pyperclip


class DeeplTranslator:
    def __init__(self, from_lang: str, to_lang: str, use_copy_paste: bool = True):
        self.from_lang = from_lang
        self.to_lang = to_lang
        self._use_copy_paste = use_copy_paste
        self.glossary = []
        self._webdriver = None
        self._init_webdriver()

    def set_glossary(self, glossary: dict):
        self.glossary = glossary
        if len(self.glossary) > 0:
            self._set_deepl_glossary()

    def translate(self, text: str, glossary: dict, max_retry: int = 10) -> str:
        # Sometimes Deepls pops A/B website
        try_count = 1
        while try_count <= max_retry:
            try:
                self.set_glossary(glossary)
                translation = self._translate(text)
                return translation
            except Exception as e:
                print(f"DeepL translator - Failed. Try {try_count}/{max_retry} ")
                print(e)
                self._init_webdriver()
                try_count += 1
        print("DeepL Translator - Too many retries. Returning empty string")
        return ""

    def _translate(self, text: str) -> str:
        if not self._webdriver:
            raise Exception("Webdriver not init")

        if len(text) > 1000:
            parts = self.split_text(text, 1000)
            translated_parts = []
            for part in parts:
                translated_parts.append(self._translate(part))
            if "" in translated_parts:
                return ""  # At least one failed
            return " ".join(list(translated_parts))

        control_key = Keys.COMMAND if platform == "darwin" else Keys.CONTROL
        self._wait_annoying_popup_close()
        self._inputField.click()
        actions = ActionChains(self._webdriver)
        actions.key_down(control_key).send_keys("A").key_up(control_key).send_keys(
            Keys.BACKSPACE
        )
        actions.perform()

        time.sleep(0.5)
        # Using copy paste is much quicker and robust as DeepL only display the loading indicator in that case
        # But it does not work if headless
        if self._use_copy_paste:
            pyperclip.copy(text)
            actions.key_down(control_key).send_keys("V").key_up(control_key)
            actions.perform()

            maxwait = 100  # 20s
            translated_text = ""
            while (
                len(
                    self._webdriver.find_elements(
                        By.XPATH,
                        '//*[@data-testid="translator-inline-loading-indicator"]',
                    )
                )
                > 0
            ):
                time.sleep(0.2)

                maxwait -= 1
                if maxwait <= 0:
                    # self._webdriver.save_screenshot("screenshot_timeout.png")
                    translated_text = self._outputField.get_attribute(
                        "textContent"
                    ).rstrip()
                    raise Exception(
                        f"Timed out. Translation probably incomplete ({len(translated_text) / len(text)}) '{text}' '{translated_text}'"
                    )
        else:
            actions.send_keys(text)
            actions.perform()
            time.sleep(5)

        translated_text = self._outputField.get_attribute("textContent")
        # Click the input to make sure the translation is really complete and we were not blocked
        # This will raise an exception otherwise
        self._inputField.click()
        return translated_text

    def _set_deepl_glossary(self):
        current_deepl_glossary = []
        self._safe_click(
            by=By.CLASS_NAME,
            value="lmt__glossary_button_label",
            close_extension_popup=True,
        )
        WebDriverWait(self._webdriver, 1).until(
            EC.presence_of_element_located(
                (By.XPATH, '//button[@data-testid="glossary-close-editor"]')
            )
        )

        current_glossary_words = self._webdriver.find_elements(
            By.XPATH, '//button[@data-testid="glossary-entry-delete-button"]'
        )

        # Delete the ones no longer in contains
        # We do it backwards because when removing an element at the top, the next one takes it's place in the dom
        # And it causes a crash when removing more than 1 word (click fails)
        for i in range(len(current_glossary_words) - 1, 0, -1):
            current_glossary_word = (
                current_glossary_words[i]
                .parent.find_elements(
                    By.XPATH,
                    '//span[@data-testid="glossary-entry-source-text"]',
                )[i]
                .text
            )
            if current_glossary_word not in self.glossary:
                print(f"Remove '{current_glossary_word}' from glossary")
                current_glossary_words[i].click()
            else:
                current_deepl_glossary.append(current_glossary_word)
                print(f"Keeping {current_glossary_word} in glossary")

        for word, translation in self.glossary.items():
            if word not in current_deepl_glossary:
                if len(current_deepl_glossary) < 10:
                    print(f"Adding {word}:{translation} to glossary")
                    self._set_deepl_glossary_add_word(word, translation)
                else:
                    print("no more space in glossary")
        self._safe_click(
            by=By.XPATH,
            value='//button[@data-testid="glossary-close-editor"]',
            close_extension_popup=True,
        )

    # Method to either close or wait for the firefox extension popup to close
    def _wait_annoying_popup_close(self, close: bool = True):
        while (
            len(
                self._webdriver.find_elements(
                    By.XPATH, '//*[@data-testid="firefox-extension-toast"]'
                )
            )
            > 0
        ):
            if close:
                try:
                    close_btn = self._webdriver.find_element(
                        By.XPATH, '//button[@aria-label="Close"]'
                    )
                    close_btn.click()
                except:
                    print("Couldn't close, waiting")
                    time.sleep(5)
            else:
                time.sleep(11)

    def _set_deepl_glossary_add_word(self, word, translation):
        self._webdriver.find_element(
            By.XPATH,
            '//input[@data-testid="glossary-newentry-source-input"]',
        ).send_keys(word)
        self._webdriver.find_element(
            By.XPATH,
            '//input[@data-testid="glossary-newentry-target-input"]',
        ).send_keys(translation)
        self._safe_click(
            by=By.XPATH,
            value='//button[@data-testid="glossary-newentry-accept-button"]',
            close_extension_popup=False,  # Closing the popup will close the glossary view
        )

    def _init_webdriver(self):
        if self._webdriver:
            self.quit()
        firefox_options = Options()
        if not self._use_copy_paste:
            firefox_options.add_argument("--headless")
        firefox_options.add_argument("--window-size=1920,1080")
        if "SOCKS_PROXY" in os.environ:
            proxy_host, proxy_port = os.environ["SOCKS_PROXY"].split(":")
            firefox_options.set_preference("network.proxy.type", 1)
            firefox_options.set_preference("network.proxy.socks", proxy_host)
            firefox_options.set_preference("network.proxy.socks_port", proxy_port)
        self._webdriver = webdriver.Firefox(options=firefox_options)
        self._webdriver.set_window_size(1920, 1080)

        self._webdriver.get(
            f"https://www.deepl.com/en/translator#{self.from_lang}/{self.to_lang}/"
        )
        self._wait_annoying_popup_close()

        self._inputField = self._webdriver.find_element(
            By.XPATH, '//*[@data-testid="translator-source-input"]'
        )
        self._outputField = self._webdriver.find_element(
            By.XPATH, '//*[@data-testid="translator-target-input"]'
        )

    def quit(self):
        if self._webdriver:
            self._webdriver.quit()

    def split_text(self, text, max_length=1500):
        sentences = text.split(".")
        result = []
        current_chunk = ""

        for sentence in sentences:
            sentence_with_period = sentence + "."
            if len(current_chunk) + len(sentence_with_period) <= max_length:
                current_chunk += sentence_with_period
            else:
                result.append(current_chunk)
                current_chunk = sentence_with_period

        # Add the last chunk if it's not empty
        if current_chunk:
            result.append(current_chunk)

        # Remove leading whitespace from each chunk
        result = [chunk.strip() for chunk in result]

        return result

    def _safe_click(self, by: str, value: str, close_extension_popup: bool):
        self._wait_annoying_popup_close(close=close_extension_popup)
        element = self._webdriver.find_elements(
            by,
            value,
        )
        if len(element) > 0:
            element[0].click()
