/**
 * AetherCut Studio - Navigation & Sidebar System
 */
export function initNavigation(switchModeCallback) {
    const $ = (id) => document.getElementById(id);

    // Sidebar items & top pills
    $("dockStreamer")?.addEventListener("click", () => switchModeCallback("streamer"));
    $("dockCopilot")?.addEventListener("click", () => switchModeCallback("copilot"));
    $("dockStudio")?.addEventListener("click", () => switchModeCallback("studio"));
    $("dockProjects")?.addEventListener("click", () => switchModeCallback("projects"));

    $("tabModeStreamer")?.addEventListener("click", () => switchModeCallback("streamer"));
    $("tabModeCopilot")?.addEventListener("click", () => switchModeCallback("copilot"));
    $("tabModeStudio")?.addEventListener("click", () => switchModeCallback("studio"));
    $("tabModeProjects")?.addEventListener("click", () => switchModeCallback("projects"));
}
