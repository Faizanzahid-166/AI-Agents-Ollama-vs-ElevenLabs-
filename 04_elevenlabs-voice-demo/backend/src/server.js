import './config/dotenv.js';
import app from './app.js';

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`ElevenLabs demo backend listening on http://localhost:${PORT}`);
});
