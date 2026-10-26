/**
 * AetherCut Studio - Consolidated Video HUD Player
 */
export function setupHudPlayer(videoEl, options = {}) {
    if (!videoEl) return null;
    const {
        hudOverlay,
        playBtn,
        muteBtn,
        timecode,
        speedBtn,
        downloadBtn,
        fullscreenBtn,
        scrubberWrap,
        scrubberBar,
    } = options;

    const fmtTime = (s) => {
        if (!s || !Number.isFinite(s)) return "00:00";
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    };

    function updatePlayState() {
        if (!playBtn) return;
        playBtn.textContent = videoEl.paused ? "▶" : "⏸";
        playBtn.title = videoEl.paused ? "Reproducir" : "Pausar";
    }

    function updateTimeline() {
        if (!scrubberBar || !videoEl.duration) return;
        const pct = (videoEl.currentTime / videoEl.duration) * 100;
        scrubberBar.style.width = `${pct}%`;
        if (timecode) {
            timecode.textContent = `${fmtTime(videoEl.currentTime)} / ${fmtTime(videoEl.duration)}`;
        }
    }

    function scrub(e) {
        if (!scrubberWrap || !videoEl.duration) return;
        const rect = scrubberWrap.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const ratio = Math.max(0, Math.min(1, clickX / rect.width));
        videoEl.currentTime = ratio * videoEl.duration;
    }

    // Bindings
    if (playBtn) {
        playBtn.addEventListener("click", () => {
            if (videoEl.paused) videoEl.play().catch(() => {});
            else videoEl.pause();
        });
    }

    if (muteBtn) {
        muteBtn.addEventListener("click", () => {
            videoEl.muted = !videoEl.muted;
            muteBtn.textContent = videoEl.muted ? "🔇" : "🔊";
        });
    }

    if (speedBtn) {
        const speeds = [1, 1.25, 1.5, 2];
        let currentIdx = 0;
        speedBtn.addEventListener("click", () => {
            currentIdx = (currentIdx + 1) % speeds.length;
            videoEl.playbackRate = speeds[currentIdx];
            speedBtn.textContent = `${speeds[currentIdx]}x`;
        });
    }

    if (fullscreenBtn) {
        fullscreenBtn.addEventListener("click", () => {
            if (!document.fullscreenElement) {
                const container = videoEl.closest(".stage-preview-box") || videoEl;
                if (container.requestFullscreen) container.requestFullscreen();
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
            }
        });
    }

    if (scrubberWrap) {
        let isDragging = false;
        scrubberWrap.addEventListener("click", scrub);
        scrubberWrap.addEventListener("mousedown", (e) => {
            isDragging = true;
            scrub(e);
        });
        window.addEventListener("mousemove", (e) => {
            if (isDragging) scrub(e);
        });
        window.addEventListener("mouseup", () => {
            isDragging = false;
        });
    }

    videoEl.addEventListener("play", updatePlayState);
    videoEl.addEventListener("pause", updatePlayState);
    videoEl.addEventListener("timeupdate", updateTimeline);
    videoEl.addEventListener("loadedmetadata", updateTimeline);

    return {
        updatePlayState,
        updateTimeline,
    };
}
