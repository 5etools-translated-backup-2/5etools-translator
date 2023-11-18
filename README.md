- [Purpose](#purpose)
- [Features and todo](#features-and-todo)
- [How to use with Plutonium](#how-to-use-with-plutonium)
- [Adding glossary](#adding-glossary)
- [Deploying locally](#deploying-locally)
- [Troubleshooting](#troubleshooting)

---

# Purpose

**For the main repository: 5etoolstranslated/5etoolstranslated.github.io**
The purpose of this repository is to provide mirrors of [5etools](https://5e.tools) with the **content** in other languages.
It aims at translating the most as possible without breaking any features.

This project is a fork from the awesome [5etools-translated](https://github.com/5etools-translated/5etools-translated.github.io) that does not seem actively maintained.
This projects no longer offer to switch language on the website because it has grown to big to be deployed on github pages with all the data. Instead there will be several forks and deployments to deploy in each language (which is anyway necessary to use with Plutonium)
This main repository is used to generate translations. Seveal repositories on another github account are used for deployments

It has many improvements compared to the original repository.

# Features and todo

-  [x] Translation of translatable content in 5etools "tags" (`{@keyword content|content|...`)
-  [x] Imperial to metric distance conversion
-  [x] Multiple glossary files per lang
-  [ ] Entity and tags translation from glossary only
-  [ ] Maybe find a way to automatically add plural to glossary.

# How to use with Plutonium

-  Open Plutonium Settings
-  Change the `Base Site URL` to the website
-  Tick `Avoid loading local data`
-  Save and refresh your game session

# Adding glossary

You can submit PRs to add glossary words in your language.
Please note the following points regarding glossary handling:

-  You can add has many json files as you want in the `translation/glossary/$your_lang` folder so try to split in relevant files names. See the [example in french](./translation/glossary/fr/)
-  Glossary will be used if there is a match in the string to translate for your glossary word or it's capitalized version.
   -  `lawful` will match `lawful` and `Lawful`.
   -  `Command` will match `Command` but not `command`. This is mostly because some spell names are very common words (aid, command) and it causes weird translations in sentences.
-  We search for exact words. Meaning `spells` will not match `spell` in the glossary. Add plurals for common words if it seems necessary
-  If you add many glossary words at once or very common words (spell, saving throw) it wil cause a LOT of strings to be retranslated and might take several days before the whole content is reprocessed and live.
-  **I (or anyone) will not review the glossary so please proofread you several times.**

# Deploying locally
Process is the same as the main 5etools website
Note some tech skills are required for this.

-  node and npm must be installed on the machine.
-  Clone this repository
-  Rename the `data` folder to `data.en` and rename `data.yourlang` to `data`
-  Serve 5etools locally

```bash
# install npm http-server (if you do not have it)
npm install -g http-server

# build the site
npm build
# server
http-server --cors
```

-  By default your site will be accessible at http://localhost:8080

# Troubleshooting

You can submit issues or PRs for any encountered problem. Be sure to do it on the [main 5etoolstranslator repository](https://github.com/5etools-translator-mirror-3/5etools-translator/issues).
