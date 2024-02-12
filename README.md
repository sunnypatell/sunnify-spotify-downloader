# Sunnify (Spotify Downloader)

Sunnify is a Spotify downloader application that allows you to download entire playlists locally onto your Mac/Linux/Windows PC.

![Sunnify Logo](./app.ico)

## Installation

### Prerequisites

- Python 3.6 or above installed on your system. If not installed, download and install Python from [python.org](https://www.python.org/downloads/).
- Ensure that pip, Python's package manager, is installed. It usually comes with Python. You can verify by running `pip --version` in your terminal.

### Dependencies

Install the required Python libraries using pip:

```bash
pip install -r requirements.txt
```

### Executable (Windows)

If you're using Windows, you can directly download the executable file from the [dist] folder.

### Building from Source

Clone the repository:

```bash
git clone https://github.com/sunnypatell/sunnify-spotify-downloader.git
```

Navigate to the project directory:

```bash
cd sunnify
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python Spotify_Downloader.py
```

## Usage

1. Launch the Sunnify application.
2. Enter your Spotify playlist URL in the provided input field.
3. Click on the "Download" button to start downloading the playlist.
4. The downloaded songs will be saved in the specified output directory.

## Libraries Used

Sunnify utilizes the following Python libraries:

- [PyQt5](https://pypi.org/project/PyQt5/): Used for the GUI interface.
- [beautifulsoup4](https://pypi.org/project/beautifulsoup4/): Used for web scraping.
- [requests](https://pypi.org/project/requests/): Used for making HTTP requests.
- [mutagen.id3](https://mutagen.readthedocs.io/en/latest/api/id3.html): Used for editing ID3 tags and scraping metadata.

## Common Debugging

If you encounter any issues while running Sunnify, try the following steps:

1. Ensure that you have a stable internet connection.
2. Verify that you have entered the correct Spotify playlist URL.
3. Check if there are any updates available for Sunnify. You can pull the latest changes from the repository and reinstall the dependencies.

## Legal and Ethical Notice

Sunnify (Spotify Downloader) is intended for educational purposes only. It is your responsibility to ensure that you comply with copyright laws and regulations in your country or region. Downloading copyrighted music without proper authorization may be illegal in certain jurisdictions.

## Author

Sunnify (Spotify Downloader) is developed and maintained by Sunny Jayendra Patel. For inquiries, suggestions, or feedback, please contact Sunny at sunnypatel124555@gmail.com.

## License

This project is licensed under the [Custom License](LICENSE). See the [LICENSE](LICENSE) file for details.

---

![GitHub Repo Stars](https://img.shields.io/github/stars/yourusername/sunnify?style=social)
![GitHub License](https://img.shields.io/github/license/yourusername/sunnify)
![GitHub Issues](https://img.shields.io/github/issues/yourusername/sunnify)
![GitHub Pull Requests](https://img.shields.io/github/issues-pr/yourusername/sunnify)
