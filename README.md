# Ankirec

A tool for helping create your own anki flashcards, with screen and sound recording.

## Overview

A more detailed description of your project. Explain:
- What problem it solves
- Who it's for
- Key features or capabilities

- Records your screen and audio to automatically use in anki flashcards
    - Intended for using in immersion-based langauge learning
- Supports linux and windows


## Getting Started

### Prerequisites

- Python 3.10+
- ffmpeg MUST be on path
    - run `ffmpeg -version` anywhere to check
- Anki extension [ankiconnect](https://ankiweb.net/shared/info/2055492159)
- You will need to set up git gists if you want to sync your sources json

If you are on linux:
- pulseaudio-utils 

```bash
sudo apt install pulseaudio-utils
```

### Installation

I recommend using pipx to install the project

```bash
# Clone the repository
git clone https://github.com/pickled-pear/ankirec.git
cd ankirec

# Install project (choose your platform)
pipx install -editable .[linux]

pipx install -editable .[windows]

# run
ankirec --help
```

### Setup

You should then configure the tool

```bash
ankirec config open

# or

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

| Flag | Required | Effect |
| :---: | :---: | :--- |
| `image`, `screenshot` | Yes (for now) | Inserts the auto-taken screenshot |
| `sentenceaudio` | Yes | Inserts the auto-recorded audio |
| `word`, `term` | No | Indicates to auto-generate TTS from this field |
| `wordaudio` | Yes (if `word` is used) | Holds auto-generated TTS |
| `date` | No | Inserts today's date into the field |
| `source` | No | Inserts the active source |

Flags are not case sensitive, and spaces, underscores and hyphens are ignored, so `:wordaudio`, `:WordAudio` and `:word_audio` all work.

If a field's name already matches one of the flags (for example a field called `Image` or `Word Audio`), the flag is applied automatically and you don't need to write it.

Any field without a flag is not considered special, and you will be asked to fill it in when creating a card. To allow a field to be left blank, add `:optional` after it, e.g. `Notes:optional`.


## Usage

```bash
# initates the main listener setup
ankirec record

# ctrl + c in terminal to stop
```

```bash
# changing the config
ankirec config set [SETTING] [NEW]

# eg
ankirec config set deckname mydeck

```

### Configuration

Document any important configuration options, environment variables, or settings users should know about.

## Project Structure

```
project-name/
├── src/              # Source code
├── tests/            # Test files
├── docs/             # Documentation
├── config/           # Configuration files
└── README.md         # This file
```

## Development

### Running Tests

```bash
npm test
# or
pytest
```

### Building

```bash
npm run build
# or
python setup.py build
```

### Contributing

Guidelines for contributing to the project:
- Fork the repository
- Create a feature branch (`git checkout -b feature/amazing-feature`)
- Commit your changes (`git commit -m 'Add amazing feature'`)
- Push to the branch (`git push origin feature/amazing-feature`)
- Open a Pull Request

## API Reference

(If applicable) Document key functions, endpoints, or methods:

### `functionName(param1, param2)`

Description of what this function does.

**Parameters:**
- `param1` (type): Description
- `param2` (type): Description

**Returns:** Description of return value

## Troubleshooting

### Common Issues

**Issue:** Something isn't working
- **Solution:** Try this approach...

**Issue:** Another problem
- **Solution:** Check this...

## Performance

(If relevant) Note any performance considerations or benchmarks.

## License

This project is licensed under the [LICENSE NAME] – see the LICENSE file for details.

## Authors

- Your Name – Initial work

## Acknowledgments

- Thanks to [person/organisation] for [contribution]
- Inspired by [project name]

## Changelog

### [Version X.X.X] – YYYY-MM-DD
- Added new feature
- Fixed bug
- Improved performance

See [CHANGELOG.md](CHANGELOG.md) for full history.

## Support

For issues, questions, or suggestions:
- Open an [issue](https://github.com/yourusername/project-name/issues)
- Check [documentation](docs/)
- Email: your.email@example.com