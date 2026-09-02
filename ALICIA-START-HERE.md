# Clip Factory — Start Here

**What it does:** you give it one long video (a podcast, a livestream recording, a lecture, anything). It listens to the whole thing, finds the best moments, cuts them into short clips, turns them vertical for TikTok / Reels / Shorts, burns the captions right into the video, and hands you a folder of finished clips with title and hashtag ideas. The hours you spend scrubbing and captioning — that's the part it does.

---

## Get it onto the computer

1. Go to https://github.com/msjojo0819-boop/clip-factory (log in as the same GitHub account David uses).
2. Click the green **Code** button → **Download ZIP**.
3. Unzip it somewhere easy, like `Documents\clip-factory`. Remember where.

## One-time setup (Windows, about 10–15 minutes)

1. Open the `clip-factory` folder.
2. **Double-click `setup.bat`.** A black window opens and installs what it needs (Python, the video tools, the speech engine). Ignore the wall of text.
   - If it asks you to click **Yes** on a Windows permission box, click Yes.
   - If it says **"Close this window, then double-click setup.bat again"**, do exactly that. It sometimes needs two runs the first time.
3. When it says **"Setup done"**, you're set. You never do this part again.

## Every time you want to make clips

1. **Double-click `start.bat`.** A black window opens and, after a few seconds, your browser opens the app by itself (if not, go to **http://127.0.0.1:8000/ui/**). **Leave the black window open** the whole time — that's the engine running.
2. Click **New Upload**, pick your video (MP4, MOV or MKV), and set how many clips you want (15 is a good start).
3. Wait. It says what it's doing: transcribing → finding moments → cutting → adding captions. **The first time ever, it downloads the speech model (a couple hundred MB) — that's a one-time wait.** After that, a 1-hour video takes roughly 15–40 minutes on a laptop. Go do something else.
4. You land on the **Review** grid. Every clip has a score and a thumbnail. Open one to trim it, switch the caption style (bold pop / minimal / neon / podcast), or add your logo.
5. Click **Export → Download all**. That's a ZIP of every clip in vertical (9:16), square (1:1) and wide (16:9).
6. Post them yourself from your phone or desktop like normal.
7. Done for the day? Close the black window.

Your clips also live in the folder `app\storage\clips\` if you ever need them again.

## What it does NOT do (so you're not surprised)

- **It can't take a YouTube link.** Download the video to a file first, then upload the file.
- **It won't post for you.** The "Connect TikTok / Instagram / YouTube" buttons in Settings don't work yet — ignore them. You upload the clips yourself.
- **The Billing page is decoration.** There's nothing to pay. It's your copy.
- **"Speaker tracking" follows the biggest face**, not the person talking. On a two-person podcast, check the vertical version — it might frame the wrong person. The wide (16:9) version is always safe.
- **The profanity bleep is rough.** If you turn it on, watch the clip before you post it.
- **It runs only on this computer.** There's no login, so it's deliberately locked to your own machine.

## If something goes wrong

- **"ffprobe is not installed"** → double-click `setup.bat` again.
- **It's too slow** → close the black window, then open a Command Prompt in the folder and run `set CLIP_FACTORY_WHISPER_MODEL=tiny` then `start.bat`. Captions will be a little less accurate.
- **A job looks stuck forever** → close the black window, double-click `start.bat` again, and re-upload that video. Jobs don't resume where they left off.
- **"Address already in use"** → something else is on port 8000. In a Command Prompt in the folder: `set PORT=8010` then `start.bat`, and go to http://127.0.0.1:8010/ui/.
- **Windows says "Windows protected your PC"** when you double-click a .bat → click **More info** → **Run anyway**. It's your own file.
- **Anything else** → copy the last few lines from the black window and send them to David.

## Mac

Open Terminal, `cd` into the folder, run `./setup.sh` once, then `./start.sh` each time. Same app, same steps after that.
