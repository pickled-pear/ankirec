# Ankirec

A tool for helping create your own anki flashcards, with screen and sound recording.

## Overview

A more detailed description of your project. Explain:
- What problem it solves
- Who it's for
- Key features or capabilities

## Getting Started

### Prerequisites

- Python 3.10+
- ffmpeg MUST be on path
    - run `ffmpeg -version` anywhere to check

If you are on linux:
- pulseaudio-utils 

```bash
sudo apt install pulseaudio-utils
```

### Installation

```bash
# Clone the repository
git clone https://github.com/pickled-pear/ankirec.git
cd ankirec

# Install project (choose your platform)
pip install -e .[linux]

pip install -e .[windows]

# run
ankirec --help
```

Make sure you choose the correct platform. Linux is supported on debian systems.

## Usage

### Basic Example

Show how to use your project with a simple example:

```bash
# Example command
command --flag "argument"
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