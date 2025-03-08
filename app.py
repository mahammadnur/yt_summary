from flask import Flask, request, render_template, flash, redirect, url_for
import os
import re
import subprocess
from google import genai  # Gemini API client

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Needed for flash messaging

# Set your Gemini API key here
GEMINI_API_KEY = 'AIzaSyCRObA-BWBi7GBNNq6DBuWeJe7HM3o0Vrw'
client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})

def extract_video_title(youtube_url):
    """Extracts full video title using yt-dlp."""
    try:
        title_output = subprocess.check_output(["yt-dlp", "--get-title", youtube_url]).decode("utf-8").strip()
        return title_output
    except subprocess.CalledProcessError as e:
        print("Error fetching video title:", e)
        return "audio"

def extract_video_id(youtube_url):
    """Extracts video id from a YouTube URL."""
    if "v=" in youtube_url:
        return youtube_url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in youtube_url:
        return youtube_url.split("youtu.be/")[-1].split("?")[0]
    else:
        return None

def sanitize_title(title, num_words=3):
    """Extract the first num_words from title and sanitize for file naming."""
    words = title.split()
    if len(words) >= num_words:
        short_title = "_".join(words[:num_words])
    else:
        short_title = title
    # Remove non-alphanumeric and non-underscore characters
    safe_title = re.sub(r'[^a-zA-Z0-9_]', '', short_title)
    if not safe_title:
        safe_title = "audio"
    return safe_title

def download_audio(youtube_url, safe_title):
    """Downloads the audio from the YouTube video using yt-dlp."""
    output_template = f"{safe_title}.%(ext)s"
    subprocess.run(["yt-dlp", "--extract-audio", "--audio-format", "mp3", "-o", output_template, youtube_url])
    final_audio_filename = f"{safe_title}.mp3"
    return final_audio_filename

def generate_transcript(audio_filename):
    """
    Uses Gemini API to generate a transcript of the speech from the audio file.
    (Adjust the prompt or processing as needed.)
    """
    # Upload the audio file
    try:
        myfile = client.files.upload(file=audio_filename)
    except Exception as e:
        print("File upload error:", e)
        return None

    prompt = 'Generate a transcript of the speech.'
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, myfile]
        )
        return response.text
    except Exception as e:
        print("Error generating transcript:", e)
        return None

def generate_summary(transcript_text):
    """
    Summarizes the transcript using Gemini API.
    You can adjust the prompt as needed.
    """
    prompt_text = ("Please summarize the following transcript from a YouTube video. "
                   "The transcript may be long or short, so please adjust the level of detail in your summary accordingly. "
                   "Cover all important major topics point-to-point. "
                   "If emoji are required, use them for a clearer UI, and insert new lines automatically. "
                   f"Transcript: {transcript_text}")
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-thinking-exp',
            contents=[prompt_text]
        )
        return response.text
    except Exception as e:
        print("Error generating summary:", e)
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    summary = None
    transcript_text = None
    thumbnail_url = None
    full_title = None
    if request.method == 'POST':
        youtube_url = request.form.get('youtube_url')
        if not youtube_url:
            flash("Please provide a YouTube URL.")
            return redirect(url_for('index'))
        
        # Extract video ID and construct thumbnail URL
        video_id = extract_video_id(youtube_url)
        if video_id:
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        
        # Step 1: Extract video title and sanitize for filename
        full_title = extract_video_title(youtube_url)
        safe_title = sanitize_title(full_title, num_words=3)
        
        # Step 2: Download the audio file
        final_audio_filename = download_audio(youtube_url, safe_title)
        if not os.path.isfile(final_audio_filename):
            flash("Audio file could not be downloaded.")
            return render_template('index.html', summary="Error downloading audio.", thumbnail_url=thumbnail_url, full_title=full_title)
        
        # Step 3: Generate transcript using Gemini API
        transcript_text = generate_transcript(final_audio_filename)
        if not transcript_text:
            flash("Transcript generation failed.")
            return render_template('index.html', summary="Error generating transcript.", thumbnail_url=thumbnail_url, full_title=full_title)
        
        # Step 4: Generate summary from transcript
        summary = generate_summary(transcript_text)
        if not summary:
            flash("Summary generation failed.")
            summary = "Error generating summary."

        # total_time= 'Estimated time: 1-2 minutes'
        # return render_template('index.html', summary=summary, thumbnail_url=thumbnail_url, full_title=full_title)
        
    return render_template('index.html', summary=summary, thumbnail_url=thumbnail_url, full_title=full_title)

if __name__ == '__main__':
    app.run(debug=True)
