from pathlib import Path
import requests

# Save folder
SAVE_DIR = Path(r"D:\07_code_2025\25_MODELS\models\04_piper")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# Files to download
files = {
    "en_US-amy-medium.onnx":
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",

    "en_US-amy-medium.onnx.json":
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
}

# Download function
def download_file(url, output_path):
    print(f"Downloading: {output_path.name}")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Saved: {output_path}")

# Download all files
for filename, url in files.items():
    download_file(url, SAVE_DIR / filename)

print("\n✅ Piper voice model downloaded successfully!")