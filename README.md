# Ankirec

A tool for helping create your own anki flashcards, with screen and sound recording.

## Overview

Making flashcards from immersion material (YouTube, games, podcasts ect) is slow: you have to pause, screenshot, clip the audio, look up the word, and paste everything into Anki by hand. Ankirec does most of that for you from the command line.

Aimed at language learners who use immersion and want sentence cards.
 
Key features:
 
- Records your screen and audio to automatically use in Anki flashcards
    - Intended for use in immersion-based language learning
- Generates TTS audio for the target word
- Fills in today's date and the current "source" (what you were watching or reading) automatically
- Works with any Anki note type. You map your fields to Ankirec's features in the config
- Keeps a tree of sources (folders and items) that can optionally be synced between devices
- Supports Linux and Windows


## Getting Started

### Prerequisites

- Python 3.10+
- ffmpeg MUST be on your path
    - run `ffmpeg -version` anywhere to check
- Anki, with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed
    - Anki must be open when sending notes
- (Optional) an account for syncing your sources between devices. See [Syncing sources](#syncing-sources)


If you are on linux:
- pulseaudio-utils 

```bash
sudo apt install pulseaudio-utils
```

### Installation

I recommend using [pipx](https://pipx.pypa.io/) to install the project

```bash
# Clone the repository
git clone https://github.com/pickled-pear/ankirec.git
cd ankirec

# Install project (choose your platform)
pipx install -editable ".[linux]"

pipx install -editable ".[windows]"

# run
ankirec --help
```

### Setup

You should then configure the tool

```bash
# open the config file in your default text editor
ankirec config open
 
# or view the current settings in the terminal
ankirec config list
```


The important settings to change are:

* deckname
    * The name of the deck in anki you want to send notes to
* cardmodel
    * The card model in anki you want to use
    * In anki, configure with Tools &rarr; Manage Note Types (ctrl+shift+n)
* cardmodel_fields
    * The fields of the card model you are using

Note these are all case sensitive.

`cardmodel_fields` is the list of fields in your card model. Each field name must match the name in Anki exactly (field names are case sensitive).

To give a field special behaviour, add a flag after its name, separated by a colon:

    "cardmodel_fields": ["Picture:image", "Clip:sentenceaudio", "Expression:word", "ExpressionAudio:wordaudio", "Meaning", "Notes:optional"]

| Flag | Required | Unique | Effect |
| :---: | :---: | :---: | :--- |
| `image`, `screenshot` | Yes (for now) | Yes | Inserts the auto-taken screenshot |
| `sentenceaudio` | Yes | Yes | Inserts the auto-recorded audio |
| `word`, `term` | No | Yes |Indicates to auto-generate TTS from this field |
| `wordaudio` | Yes (if `word` is used)  | Yes | Holds auto-generated TTS |
| `date` | No | Yes | Inserts today's date into the field |
| `source` | No | Yes | Inserts the active source |
| `optional` | No | No | Marks a manual field as optional |

Flags are not case sensitive, and spaces, underscores and hyphens are ignored, so `:wordaudio`, `:WordAudio` and `:word_audio` all work.

If a field's name already matches one of the flags (for example a field called `Image` or `Word Audio`), the flag is applied automatically and you don't need to write it.

Any field without a flag is not considered special, and you will be asked to fill it in when creating a card. To allow a field to be left blank, add `:optional` after it, e.g. `Notes:optional`.


## Usage

Generally, just using `--help` on any command should be sufficient for usage since this is a simple tool. Some more examples are provided below.

The typical workflow is:
 
1. Set the source you're about to watch or read (`ankirec source set`)
2. Start recording (`ankirec record`) and make cards as you go
3. Send the saved notes to Anki (`ankirec notes send`), happens automatically if set to

### Recording
 
```bash
# starts the main listener setup
ankirec record
 
# show extra output while recording
ankirec record --verbose
 
# Ctrl+C in the terminal to stop
```
 
Notes you create while recording are saved locally to `notes.json` first, so nothing is lost if Anki isn't open.


### Sending notes to Anki
 
Make sure Anki is open with AnkiConnect installed, then:
 
```bash
ankirec notes send
```

### Sources
 
A "source" is whatever you're learning from, e.g. a show, a book or a channel. Sources are kept in a tree of folders, and the active source is inserted into any field flagged with `source`.

```bash
ankirec source --help
```

### Syncing sources
 
You can optionally sync your sources tree between devices using an online account.
 
```bash
# create an account (you'll be asked for a password)
ankirec source sync signup you@example.com
 
# verify your email from the link in your inbox, then log in
ankirec source sync login you@example.com
 
# turn syncing on or off
ankirec source sync toggle
 
# upload your local sources (OVERWRITES the online copy)
ankirec source sync push --confirm
 
# download the online sources (OVERWRITES your local copy)
ankirec source sync pull --confirm
 
# log out on this device
ankirec source sync logout
```

`push` and `pull` replace the other side entirely rather than merging, so be sure which direction you want before running them.

### Configuration
 
```bash
# show all settings
ankirec config list
 
# show a single setting
ankirec config list --key deckname
ankirec config list --key anki.deckname
 
# change a setting
ankirec config set deckname mydeck
 
# use section.key if a name is ambiguous
ankirec config set anki.deckname mydeck
 
# give several values (or a [bracketed, list]) to store a list
ankirec config set cardmodel_fields "Picture:image" "Clip:sentenceaudio" "Expression:word" "ExpressionAudio:wordaudio" "Meaning"
 
# open the config json in your text editor
ankirec config open
 
# after updating ankirec, add any new default settings to your config (moreso for development)
ankirec config update
 
# reset everything to defaults
ankirec config reset --confirm
```

Settings worth knowing about besides the ones in [Setup](#setup):
 
| Setting | Default | Effect |
| :--- | :---: | :--- |
| `anki.ankiconnect_port` | `8765` | Port AnkiConnect listens on. Only change this if you changed it in AnkiConnect |
| `anki.ankiconnect_api_ver` | `6` | AnkiConnect API version |
| `anki.tts_voices` | [] | Sets the tts voices to choose from. [A full list is available here](https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8690a20462), eg af-ZA-AdriNeural |
| `anki.anki_profile` | `User1` | The name of your anki profile, found by File->Switch Profile in anki |
| `recording.recording_volume_lufs` | `-23` | How much to normalise your audio volume. Set somewhere lower than -18. I like -23. [See this video if you don't know what a luf is](https://www.youtube.com/watch?v=Is_wu0VRIqQ&t=256s) |
| `recording.blocksize` | `4096` | A parameter to tweak audio quality. Set higher on weaker machines. Lower (in theory) improves quality |
| `recording.image_compression_factor` | `5` | How much ffmpeg will compress the image. 2 is barely noticable, 10 is very noticable |

## Project Structure

```
project-name/
├── src/              # Source code
└── README.md         # This file
```

## Development

Install in editable mode (see [Installation](#installation)) so your changes take effect without reinstalling.
 
Commands are built with [Click](https://click.palletsprojects.com/). To add a new command group, create a file in `cli/commands/` and register it in `cli/cli.py` with `cli.add_command(...)`.


### Contributing

I will not review pull requests (probably). There are poor practises used that I didn't realise until too late, so have fun reading the code.

## Troubleshooting
 
### Common Issues
 
**Issue:** `Bad working directory: ...`
- **Solution:** Ankirec refuses to run from system folders (e.g. `C:\Windows`, `/usr`, `/etc`) or the root of a drive, to avoid writing files somewhere dangerous. `cd` into a normal folder such as your home directory and try again.
**Issue:** Sending notes fails or can't connect
- **Solution:** Check that Anki is open and that AnkiConnect is installed. If you changed AnkiConnect's port, set `anki.ankiconnect_port` to match.
**Issue:** Anki says the deck, note type or a field doesn't exist
- **Solution:** `deckname`, `cardmodel` and each name in `cardmodel_fields` must match Anki exactly, including capitals and spaces.
**Issue:** Recording fails, or there's no audio
- **Solution:** Run `ffmpeg -version` to check ffmpeg is on your path. On Linux, make sure `pulseaudio-utils` is installed.
**Issue:** `Not signed in. Sign in first`
- **Solution:** Run `ankirec source sync login YOUR_EMAIL`. If you've just signed up, verify your email first.
**Issue:** Settings I expected are missing from the config after updating
- **Solution:** Run `ankirec config update` to add any new default settings to your existing config.


## Authors
 
- [pickled-pear](https://github.com/pickled-pear)

## Support
 
For issues, questions or suggestions, open an [issue](https://github.com/pickled-pear/ankirec/issues).
