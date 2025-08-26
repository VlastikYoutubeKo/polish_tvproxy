# Telka Proxy 📺

A simple yet powerful proxy server written in Python (Flask) that allows watching publicly available internet TV streams in players like VLC. The application automatically downloads a list of channels, intelligently searches for working sources, and provides a clear web interface for easy selection.

## ✨ Key Features

-   **Clear Web Interface:** A list of all channels with logos, a search function, and a modern design.
-   **Automatic Updates:** The channel list is downloaded from a public JSON file and is always up-to-date.
-   **Intelligent Source Discovery:** The script automatically iterates through all available sources for a given channel until a working one is found.
-   **Stream Validation:** Actively validates found streams to avoid serving dead links.
-   **Persistent Cache:** Remembers which source worked for a channel and tries it first on the next request. The cache is saved to a file, so it persists even after a script restart.
-   **Multi-language Support:** The interface automatically displays in **English, Polish, or Czech** based on the user's browser language settings.
-   **M3U Export:** Provides an option to download a complete M3U playlist of all channels for use in IPTV players.
-   **Reverse Proxy Support:** Designed to run flawlessly behind Nginx Proxy Manager or a similar tool, automatically generating correct public URLs.
-   **Fallback Sources:** Automatically generates fallback source URLs for channels that are missing sources in the official list, based on their logo filename.

---

## 🚀 Installation & Setup

### Prerequisites

-   Python 3.8+
-   `pip` (Python package manager)

### 1. Preparation

Clone the repository or download the project files into a single folder. Name the main script `telka_proxy.py`.

### 2. Install Dependencies

In your terminal, navigate to the project folder and run the following command to install all required libraries:

```bash
pip install Flask requests beautifulsoup4 Werkzeug
````

Alternatively, you can create a `requirements.txt` file and run `pip install -r requirements.txt`.

### 3\. Configuration (Optional)

Open the `telka_proxy.py` file. At the top, you can modify the following constants:

  - `HOST_ADDRESS`: Set to `"0.0.0.0"` to allow access from other devices on your network (recommended for Docker/proxy setups).
  - `PORT`: The port on which the server will run (default is `8080`).
  - `FALLBACK_EMBED_URL_TEMPLATE`: The template for generating fallback source URLs.

### 4\. Running the Server

In your terminal, run the script:

```bash
python telka_proxy.py
```

The server will start, and the terminal will display a confirmation and the address where it is accessible.

-----

## 🛠️ How to Use

1.  **Open your browser** and navigate to the server's address (e.g., `http://127.0.0.1:8080` or `http://your.domain.com` if using a proxy).
2.  **Select a channel** from the list.
3.  **Copy the Link:** **Right-click** on the desired channel and choose **"Copy link address"** from the context menu. Do NOT left-click.
4.  **Open VLC Media Player.**
5.  **Paste the Link:** Press `Ctrl+N` (or `Cmd+N`) to open the "Open Network Stream" dialog. Paste the copied link (`Ctrl+V` or `Cmd+V`) and click "Play".

To get the complete playlist file, click the **"Export M3U"** button on the web page or navigate directly to the `/export.m3u` URL.

-----

## 🐳 Advanced Deployment with Docker

For an easy and isolated setup, you can use Docker.

### `Dockerfile`

Create a file named `Dockerfile` in your project folder with the following content:

```dockerfile
# Use a lightweight official Python image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
# This step is cached to speed up future builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# The command to run the application
CMD ["python", "telka_proxy.py"]
```

### `requirements.txt`

Create a `requirements.txt` file with this content:

```
Flask
requests
beautifulsoup4
Werkzeug
```

### Running with Docker

Now you can build and run the application using Docker:

```bash
# Build the Docker image
docker build -t telka-proxy .

# Run the Docker container
# This command also creates a persistent volume for the cache
docker run -d -p 8080:8080 --name telka-proxy-container -v ./cache:/app/cache --restart unless-stopped telka-proxy
```

*Note: The Python script is already configured to use a `./cache` subdirectory, so this volume mapping will work out of the box.*

-----

## 🔌 Nginx Proxy Manager Setup

If you want to access the application via your own domain (e.g., `tv.yourdomain.com`):

1.  In Nginx Proxy Manager, create a new **Proxy Host**.
2.  Set the **Domain Name** to your desired domain.
3.  Set the **Forward Hostname / IP** to the IP address of the machine running the script/Docker container.
4.  Set the **Forward Port** to `8080`.
5.  Navigate to the **Advanced** tab and ensure the following options are enabled. This is crucial for dynamic URL generation in the M3U playlist.
      - ✅ **Forward Hostname**
      - ✅ **Forward Scheme**

\!(https://www.google.com/search?q=https://i.imgur.com/your-nginx-settings-image.png) ---

## 📄 License

This project is provided under the MIT License. It is intended for educational purposes only. The functionality of the streams is not guaranteed and depends on the availability of third-party sources.

```
```
