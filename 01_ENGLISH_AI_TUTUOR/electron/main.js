'use strict';

require('dotenv').config();

const { app, BrowserWindow, ipcMain, shell, session } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const isDev = !app.isPackaged;

// ─── Whisper paths ─────────────────────────────────────────────
const whisperExeEnv = process.env.WHISPER_BIN_DIR;
const whisperModelEnv = process.env.WHISPER_MODEL;

let whisperExePath;
let whisperModelPath;

// Resolve whisper exe path
if (whisperExeEnv && path.isAbsolute(whisperExeEnv)) {
  whisperExePath = whisperExeEnv;
} else if (whisperExeEnv) {
  whisperExePath = path.join(__dirname, whisperExeEnv);
} else {
  whisperExePath = path.join(__dirname, 'whisper/whisper-cli.exe');
  console.warn('WHISPER_BIN_DIR not set. Using default path.');
}

// Resolve whisper model path
if (whisperModelEnv && path.isAbsolute(whisperModelEnv)) {
  whisperModelPath = whisperModelEnv;
} else if (whisperModelEnv) {
  whisperModelPath = path.join(__dirname, whisperModelEnv);
} else {
  whisperModelPath = path.join(
    __dirname,
    'whisper/models/ggml-base.en-q5_1.bin'
  );
  console.warn('WHISPER_MODEL not set. Using default path.');
}

const WHISPER_EXE = whisperExePath;
const WHISPER_MODEL = whisperModelPath;

console.log('WHISPER_EXE:', WHISPER_EXE);
console.log('WHISPER_MODEL:', WHISPER_MODEL);
console.log('EXE EXISTS:', fs.existsSync(WHISPER_EXE));
console.log('MODEL EXISTS:', fs.existsSync(WHISPER_MODEL));

// ─── Chromium flags ───────────────────────────────────────────────────────────
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

// ─── App ready ────────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  // Grant microphone automatically — no OS popup
  session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) => {
    cb(['media', 'audioCapture', 'microphone'].includes(permission));
  });
  session.defaultSession.setPermissionCheckHandler((_wc, permission) => {
    return ['media', 'audioCapture', 'microphone'].includes(permission);
  });

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// ─── Create main window ───────────────────────────────────────────────────────
function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0d0f14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,   // renderer cannot touch Node
      nodeIntegration: false,   // no Node in renderer
      sandbox: false,           // preload needs require()
    },
    show: false,
  });

  win.once('ready-to-show', () => win.show());

  // Grant mic at webContents level too
  win.webContents.session.setPermissionRequestHandler((_wc, permission, cb) => {
    cb(['media', 'audioCapture', 'microphone'].includes(permission));
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
    win.webContents.openDevTools({ mode: 'detach' });
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ─── WAV encoder — pure JS, zero deps ────────────────────────────────────────
// Encodes a Float32Array of mono PCM samples into a 16-bit WAV ArrayBuffer
function encodeWAV(samples, sampleRate) {
  const numSamples = samples.length;
  const buffer     = new ArrayBuffer(44 + numSamples * 2);
  const view       = new DataView(buffer);

  const str = (offset, s) => { for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i)); };

  str(0,  'RIFF');
  view.setUint32( 4, 36 + numSamples * 2, true); // file size - 8
  str(8,  'WAVE');
  str(12, 'fmt ');
  view.setUint32(16, 16,            true); // PCM chunk size
  view.setUint16(20, 1,             true); // PCM format
  view.setUint16(22, 1,             true); // mono
  view.setUint32(24, sampleRate,    true);
  view.setUint32(28, sampleRate * 2,true); // byte rate
  view.setUint16(32, 2,             true); // block align
  view.setUint16(34, 16,            true); // bits per sample
  str(36, 'data');
  view.setUint32(40, numSamples * 2,true);

  let offset = 44;
  for (let i = 0; i < numSamples; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buffer;
}

// ─── Linear resampler ─────────────────────────────────────────────────────────
function resample(samples, fromRate, toRate) {
  if (fromRate === toRate) return samples;
  const ratio  = fromRate / toRate;
  const length = Math.round(samples.length / ratio);
  const out    = new Float32Array(length);
  for (let i = 0; i < length; i++) {
    const pos  = i * ratio;
    const idx  = Math.floor(pos);
    const frac = pos - idx;
    const a    = samples[idx]     !== undefined ? samples[idx]     : 0;
    const b    = samples[idx + 1] !== undefined ? samples[idx + 1] : 0;
    out[i]     = a + frac * (b - a);
  }
  return out;
}

// ─── Parse whisper-cli stdout → plain text ────────────────────────────────────
function parseWhisperOutput(raw) {
  if (!raw) return '';
  return raw
    .split('\n')
    .map(l => l.trim())
    // Strip timestamp tokens like [00:00:00.000 --> 00:00:02.500]
    .map(l => l.replace(/^\[[\d:.]+\s*-->\s*[\d:.]+\]\s*/g, ''))
    // Drop internal whisper/ggml log lines
    .filter(l => l && !/^(whisper_|ggml_|system_|main:|log_)/.test(l))
    .join(' ')
    .trim();
}

// ─── Spawn whisper-cli subprocess ─────────────────────────────────────────────
function runWhisper(wavPath) {
  return new Promise((resolve, reject) => {
    // whisper-cli.exe flags:
    //  -m     model file
    //  -f     input wav
    //  -l     language
    //  -nt    no timestamps  (cleaner output)
    //  -np    no progress bar
    //  -nth   logprob threshold (lower = more sensitive)
    //  -et    entropy threshold (higher = more tolerant of noise)
    //  -wt    word threshold (lower = detect quieter words)
    //  -sns   suppress non-speech tokens (filters out breathing, coughing)
    const proc   = spawn(WHISPER_EXE, [
      '-m', WHISPER_MODEL,
      '-f', wavPath,
      '-l', 'en',
      '-nt',
      '-np',
      '-nth', '-2.0',       // More sensitive to quiet speech
      '-et',  '3.5',        // More tolerant of noisy audio
      '-wt',  '0.001',      // Lower word threshold
      '-sns',               // Suppress non-speech tokens
    ]);
    let stdout   = '';
    let stderr   = '';

    proc.stdout.on('data', d => { stdout += d.toString(); });
    proc.stderr.on('data', d => { stderr += d.toString(); });

    proc.on('error', err =>
      reject(new Error(`Cannot launch whisper-cli.exe: ${err.message}`))
    );

    proc.on('close', code => {
      const text = parseWhisperOutput(stdout);
      console.log('[Whisper] Exit code:', code, 'Stdout len:', stdout.length, 'Parsed text:', text || '(empty)');
      if (text)       return resolve(text);
      if (code !== 0) return reject(new Error(`whisper-cli exited ${code}: ${stderr.slice(0, 300)}`));
      resolve('');
    });

    // 30-second hard timeout
    setTimeout(() => { proc.kill(); reject(new Error('Whisper timed out (30 s)')); }, 30000);
  });
}

// ─── Convert audio to WAV using ffmpeg ─────────────────────────────────────────
async function convertToWav(inputPath, outputPath) {
  return new Promise((resolve, reject) => {
    // whisper-cli requires 16kHz mono PCM wav
    const ffmpeg = spawn('ffmpeg', [
      '-y',                       // overwrite output
      '-i', inputPath,            // input file
      '-ar', '16000',             // sample rate 16kHz (whisper.cpp requirement)
      '-ac', '1',                 // mono
      '-f', 'wav',                // wav format
      outputPath,
    ]);

    let stderr = '';
    ffmpeg.stderr.on('data', d => { stderr += d.toString(); });

    ffmpeg.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(0, 300)}`));
    });

    ffmpeg.on('error', err => reject(new Error(`ffmpeg spawn error: ${err.message}`)));

    setTimeout(() => { ffmpeg.kill(); reject(new Error('ffmpeg timed out')); }, 30000);
  });
}

// ─── IPC: Whisper STT ─────────────────────────────────────────────────────────
// Renderer sends raw audio bytes (Uint8Array) + mimeType string.
// whisper-cli supports: flac, mp3, ogg, wav
// For webm (not supported), we convert to wav using ffmpeg.
ipcMain.handle('whisper:transcribeAudio', async (_event, { audioBytes, mimeType }) => {
  let tmpFile = null;
  let wavFile = null;

  try {
    if (!fs.existsSync(WHISPER_EXE)) {
      return { success: false, error: `whisper-cli.exe not found at:\n${WHISPER_EXE}` };
    }
    if (!fs.existsSync(WHISPER_MODEL)) {
      return { success: false, error: `Model not found at:\n${WHISPER_MODEL}` };
    }

    // Pick file extension from mime type
    const isWebm = mimeType.includes('webm');
    const ext =
      mimeType.includes('ogg')  ? 'ogg'  :
      mimeType.includes('mp4')  ? 'mp4'  :
      mimeType.includes('wav')  ? 'wav'  :
      'webm';

    // Write raw audio bytes to temp file
    tmpFile = path.join(os.tmpdir(), `speakwise_${Date.now()}.${ext}`);
    fs.writeFileSync(tmpFile, Buffer.from(audioBytes));
    console.log('[Whisper] Saved audio:', tmpFile, 'Size:', audioBytes.length, 'bytes', 'Mime:', mimeType);

    // If webm (unsupported by whisper-cli), convert to wav
    if (isWebm) {
      wavFile = path.join(os.tmpdir(), `speakwise_${Date.now()}.wav`);
      console.log('[Whisper] Converting webm → wav...');
      await convertToWav(tmpFile, wavFile);
      console.log('[Whisper] Converted to:', wavFile);
    }

    const fileToTranscribe = wavFile || tmpFile;
    let transcript = '';
    try {
      transcript = await runWhisper(fileToTranscribe);
    } finally {
      try { if (tmpFile) fs.unlinkSync(tmpFile); } catch (_) {}
      try { if (wavFile) fs.unlinkSync(wavFile); } catch (_) {}
    }

    return { success: true, transcript };

  } catch (err) {
    console.error('[Whisper]', err.message);
    if (tmpFile) try { fs.unlinkSync(tmpFile); } catch (_) {}
    if (wavFile) try { fs.unlinkSync(wavFile); } catch (_) {}
    return { success: false, error: err.message };
  }
});

// ─── IPC: Whisper health check ────────────────────────────────────────────────
ipcMain.handle('whisper:health', () => ({
  exeExists:   fs.existsSync(WHISPER_EXE),
  modelExists: fs.existsSync(WHISPER_MODEL),
  exePath:     WHISPER_EXE,
  modelPath:   WHISPER_MODEL,
}));

// Keep old handle name as alias so nothing breaks
ipcMain.handle('whisper:transcribe', async (_event, args) => {
  return { success: false, error: 'Use transcribeAudio instead.' };
});

// ─── IPC: Ollama generate (STREAMING) ────────────────────────────────────────
// Uses stream:true so tokens arrive one-by-one.
// Each token is forwarded to the renderer via webContents.send('ollama:token').
// When the full response is assembled, we parse the JSON and send 'ollama:done'.
// Timeout is 120 s (generous for cold-start / slow CPU).
ipcMain.handle('ollama:generate', async (event, { userMessage, history }) => {
  const sender = event.sender;           // renderer webContents

  const systemPrompt = `You are SpeakWise, a friendly and encouraging AI English speaking coach.
For EVERY user message, respond ONLY in this exact JSON (no markdown, no extra text):
{
  "corrected":    "grammatically corrected version of the user sentence",
  "mistakes":     ["mistake 1", "mistake 2"],
  "improved":     "more natural / fluent version with better vocabulary",
  "response":     "your conversational reply (2-3 sentences, warm tone)",
  "score":        85,
  "scoreFeedback":"one-sentence reason for the score",
  "followUp":     "one engaging follow-up question"
}
Score 0-100: 90+=perfect, 70-89=good, 50-69=fair, below 50=needs work. Always be encouraging.`;

  const messages = [...history.slice(-6), { role: 'user', content: userMessage }];
  const prompt   = messages
    .map(m => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
    .join('\n') + '\nAssistant:';

  const controller = new AbortController();
  const timeoutId  = setTimeout(() => controller.abort(), 120000); // 120 s

  try {
    const res = await fetch('http://127.0.0.1:11434/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'llama3:latest',
        prompt,
        system: systemPrompt,
        stream: true,              // ← streaming on
        options: { temperature: 0.7, top_p: 0.9, num_predict: 600 },
      }),
      signal: controller.signal,
    });

    if (!res.ok) {
      clearTimeout(timeoutId);
      const msg = `Ollama HTTP ${res.status}: ${res.statusText}`;
      sender.send('ollama:error', msg);
      return { success: false, error: msg };
    }

    // Read the NDJSON stream line by line
    let fullText = '';
    const decoder = new TextDecoder();
    let buffer    = '';

    for await (const chunk of res.body) {
      buffer += decoder.decode(chunk, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();          // keep incomplete last line

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const obj = JSON.parse(line);
          const token = obj.response || '';
          fullText += token;

          // Forward each token to renderer for live display
          if (!sender.isDestroyed()) sender.send('ollama:token', token);

          if (obj.done) break;
        } catch {
          // malformed line — skip
        }
      }
    }

    clearTimeout(timeoutId);

    // Parse the complete JSON response
    let data;
    try {
      const match = fullText.match(/\{[\s\S]*\}/);
      if (match) {
        data = JSON.parse(match[0]);
      } else {
        throw new Error('no JSON block found');
      }
    } catch {
      // Fallback: treat full text as plain response
      data = {
        corrected: userMessage, mistakes: [], improved: userMessage,
        response: fullText.trim() || 'I had trouble understanding. Please try again.',
        score: 75,
        scoreFeedback: 'Keep practicing!',
        followUp: 'What would you like to talk about next?',
      };
    }

    if (!sender.isDestroyed()) sender.send('ollama:done', data);
    return { success: true, data };

  } catch (err) {
    clearTimeout(timeoutId);
    console.error('[Ollama]', err.message);

    const isTimeout    = err.name === 'AbortError';
    const isOffline    = err.message.includes('ECONNREFUSED') || err.message.includes('fetch failed');
    const friendlyMsg  = isTimeout  ? 'Ollama timed out (120 s). Try a shorter message or restart Ollama.'
                       : isOffline  ? 'Ollama is not running. Start it with: ollama serve'
                       : err.message;

    if (!sender.isDestroyed()) sender.send('ollama:error', friendlyMsg);
    return { success: false, error: friendlyMsg };
  }
});

// ─── IPC: Ollama health ───────────────────────────────────────────────────────
ipcMain.handle('ollama:health', async () => {
  try {
    const res    = await fetch('http://127.0.0.1:11434/api/tags', { signal: AbortSignal.timeout(10000) });
    const data   = await res.json();
    const models = (data.models || []).map(m => m.name);
    return { online: true, models, hasLlama3: models.some(m => m.includes('llama3')) };
  } catch {
    return { online: false, models: [], hasLlama3: false };
  }
});

// ─── Lifecycle ────────────────────────────────────────────────────────────────
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});