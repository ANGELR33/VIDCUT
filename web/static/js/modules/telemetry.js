/**
 * AetherCut / Prism Studio - Real-time SSE Telemetry & State Monitor
 */
import { $, fmtDuration, esc } from "./utils.js";

export function createTelemetryMonitor({ onStateChange, onComplete }) {
    let activeStream = null;
    let observedTaskId = "";

    function setConnection(kind, label) {
        const badge = $("connectionStatus");
        const sidebarStatus = $("connectionStatusSidebar");
        if (badge) {
            badge.className = `profile-role status-${kind}`;
            badge.textContent = `● ${label}`;
        }
        if (sidebarStatus) {
            sidebarStatus.textContent = `● ${label}`;
            sidebarStatus.style.color = kind === "active" ? "#38bdf8" : kind === "warning" ? "#fbbf24" : "#22c55e";
        }
    }

    function listen(taskId) {
        if (!taskId) return;
        if (activeStream) activeStream.close();
        observedTaskId = taskId;
        setConnection("active", "Conectando");

        activeStream = new EventSource(`/api/stream-progress/${encodeURIComponent(taskId)}`);
        
        activeStream.onopen = () => {
            setConnection("active", "En vivo");
        };

        activeStream.onmessage = (event) => {
            let state;
            try { 
                state = JSON.parse(event.data); 
            } catch { 
                return; 
            }

            if (onStateChange) onStateChange(state, taskId);

            if (state.completed || state.error || state.cancelled) {
                activeStream.close();
                activeStream = null;
                setConnection("ready", state.completed ? "Completado" : "Listo");
                if (state.completed && onComplete) onComplete(state, taskId);
            }
        };

        activeStream.onerror = () => {
            setConnection("warning", "Reconectando");
        };
    }

    function stop() {
        if (activeStream) {
            activeStream.close();
            activeStream = null;
        }
    }

    return {
        listen,
        stop,
        setConnection,
        getTaskId: () => observedTaskId,
    };
}
