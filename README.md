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

![Download in Progress](/readmeAssets/demonstration%201.jpg)
![and](/readmeAssets/demonstration%202.jpg)

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
3. Check if there are any updates available for Sunnify. You can pull the latest changes from the repository and reinstall the dependencies. `git pull`


## Running the Web App

If you want to run the Sunnify web app locally, follow these steps to set up both the backend and frontend:

### Backend Setup (Sunnify Backend)

1. Navigate to the `web-app/sunnify-backend` directory in your terminal:

    ```bash
    cd web-app/sunnify-backend
    ```

2. Install the required dependencies if not done already:

    ```bash
    pip install -r requirements.txt
    ```

3. Run the backend server:

    ```bash
    python app.py
    ```

   Alternatively, you can use:

    ```bash
    python -m app.py
    ```

   This will start the backend on `http://127.0.0.1:5000`.

### Frontend Setup (Sunnify Web Client)

1. Once the backend is running, navigate to the `web-app/sunnify-webclient` directory:

    ```bash
    cd ../sunnify-webclient
    ```

2. Install the required frontend dependencies:

    ```bash
    npm install
    ```

3. Start the frontend development server:

    ```bash
    npm run dev
    ```

   The frontend will now be running locally on `http://localhost:3000` and can communicate with the backend on `http://127.0.0.1:5000`.

### Important Note

The backend for Sunnify is hosted on Render under the free compute plan. If there hasn't been an API call to the Render-hosted backend for a while, it might "fall asleep" and take a moment to wake up when the frontend sends a request (e.g., downloading a playlist). Please be patient as it may take a few seconds for the backend to wake up and process the request.

---


## Coming Soon

I'm currently working on integrating Sunnify with iTunes for seamless transfer of downloaded music to iOS devices, specifically adding them to the Apple Music library. Additionally, I'm also working on adding support for Android filesystems to enable direct transfer of downloaded music to Android devices.

Stay tuned for these exciting updates, which will enhance the functionality of Sunnify and provide a more seamless experience for users across different platforms.

## ⚖️Legal and Ethical Notice⚖️

Sunnify (Spotify Downloader) is intended for educational purposes only. It is your responsibility to ensure that you comply with copyright laws and regulations in your country or region. Downloading copyrighted music without proper authorization may be illegal in certain jurisdictions.

## Author

Sunnify (Spotify Downloader) is developed and maintained by Sunny Jayendra Patel. For inquiries, suggestions, or feedback, please contact Sunny at sunnypatel124555@gmail.com.

## License

This project is licensed under the [Custom License](LICENSE). See the [LICENSE](LICENSE) file for details.

---

## Contributing

If you encounter any bugs, have feature requests, or would like to contribute enhancements, feel free to submit a pull request on GitHub.

### Reporting Issues

If you encounter any issues while using Sunnify, please [open an issue](https://github.com/sunnypatell/sunnify-spotify-downloader/issues) on GitHub. Be sure to include detailed information about the problem, including steps to reproduce it and any error messages you may have encountered. Your feedback helps me improve the application for everyone else.

---
