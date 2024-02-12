# Sunnify (Spotify Downloader)

![GitHub Repo Stars](https://img.shields.io/github/stars/sunnypatell/sunnify-spotify-downloader?style=social)
![GitHub Issues](https://img.shields.io/github/issues/sunnypatell/sunnify-spotify-downloader)
![GitHub Pull Requests](https://img.shields.io/github/issues-pr/sunnypatell/sunnify-spotify-downloader)

---

Sunnify is a Spotify downloader application that allows you to download entire playlists locally onto your Mac/Linux/Windows PC.

![Sunnify Logo](./app.ico)

---

## Program Demonstration

Below are screenshots demonstrating the Sunnify application in action, downloading my personal Spotify playlist.

![Download in Progress](readmeAssets/demonstration 1.png)
![and](readmeAssets/demonstration 2.png)

## Installation

### Prerequisites

- Python 3.6 or above installed on your system. If not installed, download and install Python from [python.org](https://www.python.org/downloads/).
- Ensure that pip, Python's package manager, is installed. It usually comes with Python. You can verify by running `pip --version` in your terminal.

### Sunnify Executable (Windows)

If you're using Windows, you can directly download the executable file from [here](/dist/Sunnify%20(Spotify%20Downloader).exe)

### Building from Source

Clone the repository:

```bash
git clone https://github.com/sunnypatell/sunnify-spotify-downloader.git
```

Navigate to the project directory:

```bash
cd sunnify-spotify-downloader
```

Install the required dependencies:

```bash
pip install -r req.txt
```

Run the application:

```bash
python Spotify_Downloader.py
```

## Usage

1. Launch the Sunnify application.
2. Enter your Spotify playlist URL in the provided input field.
3. Check show preview box to see progress
4. Check metadata box if you want to download cover art, author, album, release-date etc...
5. Press enter in the URL field to start downloading.
4. The downloaded songs will be saved in the media directory (wherever your source or executable is located).

## Libraries Used

Sunnify utilizes the following Python libraries:

- [PyQt5](https://pypi.org/project/PyQt5/): Used for the GUI interface.
- [webbrowser](https://pypi.org/project/pycopy-webbrowser/): Used to bypass Spotify Network Traffic Detection.
- [requests](https://pypi.org/project/requests/): Used for making HTTP requests.
- [mutagen.id3](https://mutagen.readthedocs.io/en/latest/api/id3.html): Used for editing ID3 tags and scraping metadata.

## Common Debugging

If you encounter any issues while running Sunnify, try the following steps:

1. Ensure that you have a stable internet connection.
2. Verify that you have entered the correct Spotify playlist URL.
3. Check if there are any updates available for Sunnify. You can pull the latest changes from the repository and reinstall the dependencies. `git fetch`

## Legal and Ethical Notice

Sunnify (Spotify Downloader) is intended for educational purposes only. It is your responsibility to ensure that you comply with copyright laws and regulations in your country or region. Downloading copyrighted music without proper authorization may be illegal in certain jurisdictions.

## Author

Sunnify (Spotify Downloader) is developed and maintained by Sunny Jayendra Patel. For inquiries, suggestions, or feedback, please contact Sunny at sunnypatel124555@gmail.com.

## License

This project is licensed under the [Custom License](LICENSE). See the [LICENSE](LICENSE) file for details.

---
