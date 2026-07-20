#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FRAMES="$ROOT/frames"
VIDEO="$ROOT/video"
PREPARED="$VIDEO/prepared"
SEGMENTS="$VIDEO/segments"
AUDIO="$ROOT/audio"
FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
VOICE="${VOICE:-Samantha}"
RATE="${RATE:-170}"

mkdir -p "$PREPARED" "$SEGMENTS" "$AUDIO"

prepare_full() {
  ffmpeg -y -hide_banner -loglevel error -i "$1" -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0xF5F8FA" -frames:v 1 "$2"
}

prepare_portrait() {
  local source="$1"
  local target="$2"
  local title="$3"
  local line1="$4"
  local line2="$5"
  local line3="$6"
  ffmpeg -y -hide_banner -loglevel error -f lavfi -i "color=c=0xF5F8FA:s=1280x720:d=1" -i "$source" -filter_complex "[1:v]scale=-2:680[shot];[0:v][shot]overlay=35:(H-h)/2,drawbox=x=680:y=110:w=5:h=500:color=0x2F855A:t=fill,drawtext=fontfile='$FONT_BOLD':text='$title':fontcolor=0x102A43:fontsize=38:x=730:y=170,drawtext=fontfile='$FONT':text='$line1':fontcolor=0x334E68:fontsize=25:x=730:y=270,drawtext=fontfile='$FONT':text='$line2':fontcolor=0x334E68:fontsize=25:x=730:y=325,drawtext=fontfile='$FONT':text='$line3':fontcolor=0x334E68:fontsize=25:x=730:y=380,drawtext=fontfile='$FONT_BOLD':text='BatchHelm AI':fontcolor=0x2F855A:fontsize=20:x=730:y=540" -frames:v 1 "$target"
}

ffmpeg -y -hide_banner -loglevel error -f lavfi -i "color=c=0xF5F8FA:s=1280x720:d=1" -vf "drawbox=x=0:y=0:w=20:h=720:color=0x2F855A:t=fill,drawbox=x=20:y=0:w=1260:h=14:color=0xD64545:t=fill,drawtext=fontfile='$FONT_BOLD':text='BatchHelm AI':fontcolor=0x102A43:fontsize=68:x=90:y=190,drawtext=fontfile='$FONT':text='Recall operations coordinated by Qwen':fontcolor=0x334E68:fontsize=35:x=94:y=290,drawtext=fontfile='$FONT_BOLD':text='Alibaba Cloud ECS':fontcolor=0x22543D:fontsize=27:x=95:y=420,drawtext=fontfile='$FONT_BOLD':text='Qwen text + vision':fontcolor=0x97266D:fontsize=27:x=430:y=420,drawtext=fontfile='$FONT_BOLD':text='Track 4':fontcolor=0x9C4221:fontsize=27:x=790:y=420,drawtext=fontfile='$FONT':text='Live demo 47.84.199.208':fontcolor=0x627D98:fontsize=23:x=96:y=520" -frames:v 1 "$PREPARED/01-title.png"

prepare_full "$FRAMES/02-qwen-proof.png" "$PREPARED/02-qwen.png"
prepare_portrait "$FRAMES/10-new-recall.png" "$PREPARED/03-intake.png" "Durable recall intake" "Notice and inventory CSV" "Optional shelf image" "Immutable file provenance"
prepare_full "$FRAMES/03-inventory.png" "$PREPARED/04-inventory.png"
prepare_full "$FRAMES/05-agents-complete.png" "$PREPARED/05-agents.png"
prepare_full "$FRAMES/06-agents-wave3.png" "$PREPARED/06-wave3.png"
prepare_full "$FRAMES/04-tasks.png" "$PREPARED/07-tasks.png"
prepare_portrait "$FRAMES/07-evidence-review.png" "$PREPARED/08-evidence.png" "Human approval gate" "Six release checks passed" "Immutable audit trail" "Approved for submission"
prepare_portrait "$FRAMES/08-evidence-qwen-vision.png" "$PREPARED/09-vision.png" "Qwen shelf vision" "Lot L2418 recognized" "100 percent confidence" "Source image preserved"
prepare_portrait "$FRAMES/09-memory.png" "$PREPARED/10-memory.png" "Learned operational memory" "23-unit decision persisted" "Supplier aliases retained" "Reusable across future recalls"
prepare_full "$ROOT/architecture.png" "$PREPARED/11-architecture.png"
prepare_portrait "$ROOT/alibaba-ecs-proof.png" "$PREPARED/12-ecs.png" "Alibaba Cloud ECS proof" "Instance status Running" "Health status Normal" "Public IP 47.84.199.208"

ffmpeg -y -hide_banner -loglevel error -f lavfi -i "color=c=0xF5F8FA:s=1280x720:d=1" -vf "drawbox=x=0:y=0:w=20:h=720:color=0xD64545:t=fill,drawbox=x=20:y=706:w=1260:h=14:color=0x2F855A:t=fill,drawtext=fontfile='$FONT_BOLD':text='Faster. Traceable. Recoverable.':fontcolor=0x102A43:fontsize=56:x=90:y=210,drawtext=fontfile='$FONT':text='Qwen-powered recall response with human approval':fontcolor=0x334E68:fontsize=31:x=94:y=315,drawtext=fontfile='$FONT_BOLD':text='BatchHelm AI':fontcolor=0x2F855A:fontsize=34:x=95:y=445,drawtext=fontfile='$FONT':text='github.com/ankitranjan-dsai/batchhelm-ai':fontcolor=0x627D98:fontsize=24:x=95:y=510" -frames:v 1 "$PREPARED/13-outro.png"

images=(
  "$PREPARED/01-title.png"
  "$PREPARED/02-qwen.png"
  "$PREPARED/03-intake.png"
  "$PREPARED/04-inventory.png"
  "$PREPARED/05-agents.png"
  "$PREPARED/06-wave3.png"
  "$PREPARED/07-tasks.png"
  "$PREPARED/08-evidence.png"
  "$PREPARED/09-vision.png"
  "$PREPARED/10-memory.png"
  "$PREPARED/11-architecture.png"
  "$PREPARED/12-ecs.png"
  "$PREPARED/13-outro.png"
)

narrations=(
  "This is BatchHelm AI, a recall operations command center deployed on Alibaba Cloud E C S. It turns an incident packet into an auditable, coordinated response, with Qwen at the center of extraction, reasoning, vision, and management briefing."
  "The live application exposes a Qwen Cloud evidence receipt. This session verified Qwen three point seven plus against Alibaba Cloud Model Studio, including the verification time, latency, and response fingerprint."
  "A manager starts with the original recall notice, structured inventory C S V, and an optional shelf image. BatchHelm preserves the uploaded files and their provenance before processing."
  "For this spinach incident, the authoritative inventory match found twenty three affected units across two stores and quarantined every matching lot."
  "The orchestration service runs nine specialist agents as a dependency graph, in parallel waves. Every event is persisted, with retries and typed checkpoints, so a run can recover and replay without losing its audit trail."
  "Here, Inventory Matching reconciles twenty three units and supplier aliases. Shelf Vision uses Qwen to read the real shelf image, identify lot L twenty four eighteen, and return a one hundred percent confidence recall match."
  "The Operations Task agent turns those decisions into an accountable staff task board, with owners, due times, stores, and completion state."
  "Before anything leaves the organization, a human approval gate checks the inventory impact, communications, disposal records, and regulatory filing package."
  "The same Qwen vision result is preserved as evidence, including product, lot, U P C, confidence, recommended action, model source, and input filename."
  "The Memory agent persists decisions and supplier aliases so future recalls can reuse learned patterns while still keeping human review in control."
  "The architecture is intentionally compact. React and Fast A P I run in Docker on E C S, Qwen text and vision come from Alibaba Cloud Model Studio, and SQLite backed stores preserve artifacts, events, reviews, and memory."
  "This Alibaba Cloud console view shows the live E C S instance running in Singapore with normal health and public I P forty seven dot eighty four dot one ninety nine dot two zero eight, the same address serving the demo."
  "BatchHelm AI makes recall response faster, traceable, recoverable, and ready for human approved submission. Thank you."
)

for i in "${!narrations[@]}"; do
  number="$(printf '%02d' "$((i + 1))")"
  audio="$AUDIO/$number.aiff"
  segment="$SEGMENTS/$number.mp4"
  say -v "$VOICE" -r "$RATE" -o "$audio" "${narrations[$i]}"
  audio_duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$audio")"
  duration="$(awk -v d="$audio_duration" 'BEGIN { printf "%.3f", d + 0.6 }')"
  fade_out="$(awk -v d="$duration" 'BEGIN { printf "%.3f", d - 0.25 }')"
  ffmpeg -y -hide_banner -loglevel error -loop 1 -framerate 30 -i "${images[$i]}" -i "$audio" -filter_complex "[0:v]format=yuv420p,fade=t=in:st=0:d=0.25,fade=t=out:st=$fade_out:d=0.25[v];[1:a]adelay=300|300,apad=pad_dur=0.3[a]" -map "[v]" -map "[a]" -t "$duration" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -c:a aac -b:a 160k -ar 48000 -ac 2 "$segment"
done

ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$VIDEO/concat.txt" -c copy -movflags +faststart "$VIDEO/batchhelm-ai-demo.mp4"
ffprobe -v error -show_entries format=duration,size:stream=index,codec_name,codec_type,width,height,sample_rate,channels -of default=noprint_wrappers=1 "$VIDEO/batchhelm-ai-demo.mp4"
