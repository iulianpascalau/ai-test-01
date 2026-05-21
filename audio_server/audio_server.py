import os
import io
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI(title="GPU1 Audio Server")

print("Loading Faster-Whisper model onto GPU1...")
# We default to 'base' for raw speed, but 'small' or 'medium' fit easily on a Tesla P40.
from faster_whisper import WhisperModel
whisper_model = WhisperModel("base", device="cuda", compute_type="float32")

print("Loading XTTS-v2 model onto GPU1... (This might take a moment on first run to download)")
from TTS.api import TTS
# XTTS-v2 requires agreeing to Coqui terms on first download. 
os.environ["COQUI_TOS_AGREED"] = "1"
tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")

# You need a reference voice file for XTTS-v2. 
# Place any clear 3-10 second speech audio file named 'speaker.wav' in the same folder.
SPEAKER_WAV_PATH = "speaker.wav"

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Receives a WAV/WEBM file from the frontend, transcribes it to text."""
    try:
        # Save uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Transcribe using faster-whisper
        segments, info = whisper_model.transcribe(tmp_path, beam_size=5)
        
        text = " ".join([segment.text for segment in segments]).strip()
        
        # Cleanup temp file
        os.remove(tmp_path)
        
        return {"text": text, "language": info.language}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SynthesizeRequest(BaseModel):
    text: str
    language: str = "en"

@app.post("/synthesize")
async def synthesize_audio(req: SynthesizeRequest):
    """Receives text, clones the voice, and returns a generated WAV file."""
    if not os.path.exists(SPEAKER_WAV_PATH):
        raise HTTPException(
            status_code=400, 
            detail=f"Please place a '{SPEAKER_WAV_PATH}' file in this directory to use as the voice clone reference."
        )
        
    try:
        output_path = tempfile.mktemp(suffix=".wav")
        
        # Generate speech using XTTS-v2
        tts_model.tts_to_file(
            text=req.text,
            speaker_wav=SPEAKER_WAV_PATH,
            language=req.language,
            file_path=output_path
        )
        
        # Return the generated audio file
        # We use background tasks or standard FileResponse. 
        # Note: In production you might want a cleanup task for the generated file.
        return FileResponse(output_path, media_type="audio/wav")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Runs on port 8001 to avoid conflicting with your other services
    uvicorn.run(app, host="0.0.0.0", port=8001)
