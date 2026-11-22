# Composition Brief: SmartCam brag

Source of truth for story, timing and claims: `brag-plan.md`. This brief adds only what
Hyperframes needs to build the composition.

## LOOK
A dark operations console, not a product launch. Near-black field (#0a0d13) with one
raised surface (#12161f) and hairline rules (#232a38). Single accent: #4b8cff, used only
for detection brackets and one underline. Type is Inter at weight 600 with -0.02em
tracking for display, and ui-monospace for every figure, label and timecode. No glow, no
gradient, no glassmorphism, no 3D. Contrast does the work: white type on near-black,
with generous negative space around every line that must be read.

## Deliverables
- 1920x1080, 20.1s, 30fps, h264, yuv420p, faststart
- Holds: every caption settled for at least 0.8s; the description scene holds 2.5s
- Frame 0 must be the poster (wordmark or the darkest legible hook frame), not a black
  frame

## Scene intent
1. **Hook (0.00-3.00)** - 3x3 grid, nine tiles, all near-black, blinking on one per
   beat from 0.27s. This must read as a wall of cameras that are ON and UNWATCHED. Text
   at 1.9s: *You already own 32 cameras.*
2. **Cut (3.00-3.40)** - hard cut to pure black, 200ms of silence, then four words:
   *Nobody is watching them.* No fade, no motion. This is the most important beat in the
   video.
3. **Reveal (3.40-6.30)** - wordmark on the near-black field, a single #4b8cff underline
   sweeping left to right and settling. Nothing else moves.
4. **It writes (6.30-9.80)** - a dim real camera frame behind, the description text
   revealing line by line in mono. Caption below: *It watches. And writes down what it
   saw.*
5. **It detects (9.80-13.60)** - four corner brackets scale onto a figure, snapping with
   a 4-step tick; labels read person 0.87, Camera 07, 23:34. The brackets are the only
   accent colour on screen.
6. **It reports (13.60-16.90)** - an A4 page rises from below with slight parallax;
   header rules draw in; a still frame sits in the page. Caption: *One page. Time,
   camera, still frame.*
7. **Scale (16.90-18.50)** - eight small tiles snap into a 4x2 grid on beats; caption
   *8 cameras. Your DVR. One box.*
8. **Outro (18.50-20.10)** - three lines on the strong beats at 18.01 / 18.55 / 20.19:
   *Your DVR was already looking.* then *Now it tells you.* then wordmark + agay.tech.

## Motion rules
- Everything settles. No element should still be moving when the next one starts.
- Cuts land on the beat grid from the plan (0.27, 1.90, 3.01, 9.83, 18.01, 18.55).
- Brackets and tiles may use a short overshoot; text never does. Type fades and holds.
- No camera moves on text. No parallax on anything a viewer must read.

## Audio
- Music: `assets/music/happy-beats-business-moves-vol-10-by-ende-dot-app.mp3`, 109.96
  BPM, ducked to a bed under the hook, lifted at 3.40s, faded out by 20.0s.
- SFX: one soft tick per tile entrance (9 max), one low thud at 3.00s, one paper slide at
  13.60s. Nothing else.
- The 200ms gap at 3.00-3.20s is deliberate silence - do not fill it.

## Bans
No 'streamline', 'empower', 'revolutionary', 'AI-powered'. No fake UI. No stock footage of
people in suits shaking hands. No feature bullet lists. No logos other than SmartCam's
wordmark. If a claim is not in `brag-plan.md`, it does not go on screen.
