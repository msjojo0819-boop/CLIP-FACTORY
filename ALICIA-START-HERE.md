# Clip Factory — Start Here

**What it does:** you give it one long video (a podcast, a livestream recording, a lecture, anything). It listens to the whole thing, finds the best moments, cuts them into short clips, turns them vertical for TikTok / Reels / Shorts, burns the captions right into the video, and hands you a folder of finished clips with title and hashtag ideas. The hours you spend scrubbing and captioning — that's the part it does.

---

## One-time setup (about 10–15 minutes, Mac)

1. Open **Terminal** (press ⌘ + Space, type `Terminal`, hit Enter).
2. Type `cd ` (with a space), then **drag the `clip-factory` folder into the Terminal window**, and press Enter.
3. Type `./setup.sh` and press Enter. Let it run. It installs the video tools and the speech model. Ignore the wall of text.
   - If it says **"Homebrew isn't installed"** — go to https://brew.sh, copy the one command on that page into Terminal, run it, then run `./setup.sh` again.
4. When it says **"Setup done"**, you're set. You never do this part again.

## Every time you want to make clips

1. In Terminal, `cd` into the folder like before, then type `./start.sh` and press Enter.
2. Your browser opens the app by itself (if not, go to **http://127.0.0.1:8000/ui/**). **Leave the Terminal window open** the whole time — that's the engine running.
3. Click **New Upload**, pick your video (MP4, MOV or MKV), and set how many clips you want (15 is a good start).
4. Wait. It says what it's doing: transcribing → finding moments → cutting → adding captions. **The first time ever, it downloads the speech model (a couple hundred MB) — that's a one-time wait.** After that, a 1-hour video takes roughly 15–40 minutes on a laptop. Go do something else.
5. You land on the **Review** grid. Every clip has a score and a thumbnail. Open one to trim it, switch the caption style (bold pop / minimal / neon / podcast), or add your logo.
6. Click **Export → Download all**. That's a ZIP of every clip in vertical (9:16), square (1:1) and wide (16:9).
7. Post them yourself from your phone or desktop like normal.

Your clips also live in the folder `app/storage/clips/` if you ever need them again.

## What it does NOT do (so you're not surprised)

- **It can't take a YouTube link.** Download the video to a file first, then upload the file.
- **It won't post for you.** The "Connect TikTok / Instagram / YouTube" buttons in Settings don't work yet — ignore them. You upload the clips yourself.
- **The Billing page is decoration.** There's nothing to pay. It's your copy.
- **"Speaker tracking" follows the biggest face**, not the person talking. On a two-person podcast, check the vertical version — it might frame the wrong person. The wide (16:9) version is always safe.
- **The profanity bleep is rough.** If you turn it on, watch the clip before you post it.
- **It runs only on this computer.** There's no login, so it's deliberately locked to your own machine.

## If something goes wrong

- **"ffprobe is not installed"** → run `./setup.sh` again (or in Terminal: `brew install ffmpeg`).
- **It's too slow** → stop it (Ctrl+C), then start with the small fast model: `CLIP_FACTORY_WHISPER_MODEL=tiny ./start.sh`. Captions will be a little less accurate.
- **A job looks stuck forever** → stop (Ctrl+C), run `./start.sh` again, and re-upload that video. Jobs don't resume where they left off.
- **"Address already in use"** → something else is on port 8000. Run `PORT=8010 ./start.sh` and go to http://127.0.0.1:8010/ui/.
- **Anything else** → copy the last few lines from the Terminal window and send them to David.

## Windows

Install [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) (add it to PATH), [Python 3.11+](https://www.python.org/downloads/) (tick "Add to PATH"), and [Node LTS](https://nodejs.org). Then in PowerShell, inside the folder:

```
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cd frontend; npm ci; npm run build; cd ..
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/ui/ in your browser.
