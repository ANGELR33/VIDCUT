/**
 * Módulo Agente Copilot Multi-Modelo (Clon ChatGPT con Control Total de la App)
 * Conecta los modelos GLM-5.3, GLM-5.3 Flash, Kimi-k3 y Gemini con las acciones en tiempo real de AetherCut.
 */

export class AgentCopilot {
    constructor() {
        this.activeModel = "gemini";
        this.isOpen = false;
        this.isExpanded = false;
        this.history = [];          // Historial multi-turn de conversación
        this.pendingAttachments = []; // Archivos/multimedia listos para enviar con el próximo mensaje
        this.isThinking = false;
        this.currentAbortController = null;
        this.currentTypewriterInterval = null;
        this.currentReplyTypewriterInterval = null;
        this.activeReplyStream = null;
        this.currentThinkingId = null;

        // Estado del MODO REN (Modificador de la Plataforma)
        this.isRenMode = false;
        this.selectedElementSelector = null;
        this.lastRenSelector = null;   // último elemento seleccionado: permite iterar sin re-seleccionar
        this.isInspectorActive = false;
        this.renStylesMap = {};

        // Persistencia de chats
        this.chatId = null;
        this.ocSessionId = null;

        // Deduplicación de acciones (llegan por SSE en vivo y también al final del turno)
        this.seenActionUids = new Set();
        this.liveEvents = null;

        this.modelsMeta = {
            "gemini":      { name: "Gemini 2.5 Flash",  color: "#f59e0b", badge: "⚡ Recomendado" },
            "glm-5.3":     { name: "GLM-5.3 Senior",    color: "#38bdf8", badge: "Arquitecto" },
            "glm-5.3-flash": { name: "GLM-5.3 Flash",  color: "#a855f7", badge: "Ultra Rápido" },
            "kimi-k3":     { name: "Kimi-k3",           color: "#10b981", badge: "Auditor" },
        };

        this.initElements();
        this.attachEvents();
        this.loadPersistedRenStyles();
        this.loadModelsFromServer();
        this.loadSavedChatsList();
        this.connectLiveEvents();
    }

    /**
     * Suscripción SSE a /api/oc/events: ejecuta en el navegador, en tiempo real,
     * cada acción de UI que publica el agente (opencode en terminal o chat de la app).
     */
    connectLiveEvents() {
        if (this.liveEvents) return;
        try {
            this.liveEvents = new EventSource("/api/oc/events");
            this.liveEvents.onmessage = (msg) => {
                try {
                    const action = JSON.parse(msg.data);
                    if (action && typeof action === "object") {
                        this.executeAppActions([action]);
                    }
                } catch (e) {
                    console.warn("[AgentCopilot] Acción en vivo no válida:", e);
                }
            };
            this.liveEvents.onerror = () => { /* EventSource reintenta solo */ };
        } catch (e) {
            console.warn("[AgentCopilot] SSE en vivo no disponible:", e);
        }
    }

    /**
     * Carga la lista real de modelos desde el servidor y actualiza tarjetas,
     * pills y etiquetas en vivo: la interfaz muestra lo que el motor ofrece.
     */
    async loadModelsFromServer() {
        try {
            const resp = await fetch("/api/agent/models");
            if (!resp.ok) return;
            const data = await resp.json();
            const models = Array.isArray(data.models) ? data.models : [];
            models.forEach(m => {
                if (!m || !m.id) return;
                this.modelsMeta[m.id] = {
                    name: m.name || m.id,
                    color: m.color || "#38bdf8",
                    badge: m.badge || "",
                    desc: m.desc || "",
                    provider: m.provider || "",
                };
                const cards = document.querySelectorAll(`.agent-model-card[data-model="${m.id}"]`);
                cards.forEach(card => {
                    const nameEl = card.querySelector(".agent-model-name");
                    const descEl = card.querySelector(".agent-model-desc");
                    const badgeEl = card.querySelector(".agent-model-badge");
                    const dotEl = card.querySelector(".agent-model-dot");
                    if (nameEl) nameEl.textContent = m.name || m.id;
                    if (descEl && m.desc) descEl.textContent = m.desc;
                    if (badgeEl && m.badge) badgeEl.textContent = m.badge;
                    if (dotEl && m.color) dotEl.style.background = m.color;
                });
            });
            // Refrescar las etiquetas del modelo activo con el nombre real del servidor.
            this.selectModel(this.activeModel);
        } catch (e) {
            console.warn("[AgentCopilot] No se pudo cargar la lista de modelos del servidor:", e);
        }
    }

    initElements() {
        this.deck = document.getElementById("agentChatDeck");
        this.launcher = document.getElementById("agentFabLauncher");
        this.dockBtn = document.getElementById("dockAgentLauncher");
        this.btnClose = document.getElementById("agentBtnClose");
        this.btnMin = document.getElementById("agentBtnMinimize");
        this.btnExpand = document.getElementById("agentBtnExpand");
        this.btnNewChat = document.getElementById("agentBtnNewChat");
        this.modelCards = document.querySelectorAll(".agent-model-card");
        this.modelSelect = document.getElementById("agentModelSelect");
        this.modelDropdown = document.getElementById("agentModelDropdown");
        this.headerModelSelect = document.getElementById("agentHeaderModelSelect");
        this.headerModelDropdown = document.getElementById("agentHeaderModelDropdown");
        this.headerModelPill = document.getElementById("agentHeaderModelPill");
        this.headerPillName = document.getElementById("agentHeaderModelName");
        this.headerDot = document.getElementById("agentHeaderDot");
        this.inputModelTag = document.getElementById("agentInputModelTag");
        this.inputModelNameEl = document.getElementById("agentInputModelName");
        this.fabModelPill = document.getElementById("agentFabModelPill");
        this.messagesContainer = document.getElementById("agentMessagesContainer");
        this.promptForm = document.getElementById("agentPromptForm");
        this.promptInput = document.getElementById("agentPromptInput");
        this.btnSend = document.getElementById("agentBtnSend");

        // Subida de archivos / multimedia (clip junto al nombre del modelo)
        this.btnAttach = document.getElementById("agentBtnAttach");
        this.fileInput = document.getElementById("agentFileInput");
        this.attachmentsBar = document.getElementById("agentAttachments");

        this.quickBtns = document.querySelectorAll(".agent-quick-btn");
        this.suggChips = document.querySelectorAll(".agent-sugg-chip");

        // Elementos del MODO REN
        this.btnToggleRen = document.getElementById("agentBtnToggleRen");
        this.renToolbar = document.getElementById("agentRenToolbar");
        this.renToggleDot = document.getElementById("agentRenToggleDot");
        this.btnPickElement = document.getElementById("agentBtnPickElement");
        this.renTargetPill = document.getElementById("agentRenTargetPill");
        this.renTargetSelText = document.getElementById("agentRenTargetSelText");
        this.btnClearTarget = document.getElementById("agentBtnClearTarget");
        this.btnResetRen = document.getElementById("agentBtnResetRen");
        this.renChips = document.querySelectorAll(".agent-ren-chip");
        this.inspectorOverlay = document.getElementById("agentRenInspectorOverlay");
        this.inspectorBadge = document.getElementById("agentRenInspectorBadge");
        this.inspectorTag = document.getElementById("agentRenHoverTag");
        this.inspectorSel = document.getElementById("agentRenHoverSel");

        // Persistencia de chats
        this.savedChatsList = document.getElementById("agentSavedChatsList");
    }

    attachEvents() {
        // Toggle abrir / cerrar
        if (this.launcher) {
            this.launcher.addEventListener("click", () => this.toggle());
        }
        if (this.dockBtn) {
            this.dockBtn.addEventListener("click", () => this.open());
        }
        if (this.btnClose) {
            this.btnClose.addEventListener("click", () => this.close());
        }
        if (this.btnMin) {
            this.btnMin.addEventListener("click", () => this.close());
        }
        if (this.btnExpand) {
            this.btnExpand.addEventListener("click", () => this.toggleExpand());
        }
        if (this.btnNewChat) {
            this.btnNewChat.addEventListener("click", () => this.resetChat());
        }

        // Modo REN Toggle y Botones
        if (this.btnToggleRen) {
            this.btnToggleRen.addEventListener("click", () => this.toggleRenMode());
        }
        if (this.btnPickElement) {
            this.btnPickElement.addEventListener("click", () => this.toggleElementPicker());
        }
        if (this.btnClearTarget) {
            this.btnClearTarget.addEventListener("click", () => this.clearRenTarget());
        }
        if (this.btnResetRen) {
            this.btnResetRen.addEventListener("click", () => this.resetRenModifications());
        }
        this.renChips.forEach(chip => {
            chip.addEventListener("click", () => {
                const act = chip.getAttribute("data-ren-action");
                if (act) this.handleRenActionClick(act);
            });
        });

        // Selección de modelos: tarjetas dentro de AMBOS dropdowns (header y prompt)
        const allModelCards = document.querySelectorAll(".agent-model-card");
        allModelCards.forEach(card => {
            card.addEventListener("click", () => {
                const modelId = card.getAttribute("data-model");
                this.selectModel(modelId);
                this.toggleModelDropdown(false);
                this.toggleHeaderModelDropdown(false);
            });
        });

        // Dropdown del selector de modelo en el HEADER (arriba)
        if (this.headerModelPill) {
            this.headerModelPill.addEventListener("click", (e) => {
                e.stopPropagation();
                this.toggleHeaderModelDropdown();
                this.toggleModelDropdown(false);
            });
        }

        // Dropdown del selector de modelo en el INPUT (abajo)
        if (this.inputModelTag) {
            this.inputModelTag.addEventListener("click", (e) => {
                e.stopPropagation();
                this.toggleModelDropdown();
                this.toggleHeaderModelDropdown(false);
            });
        }

        document.addEventListener("click", (e) => {
            if (this.modelSelect && !this.modelSelect.contains(e.target)) {
                this.toggleModelDropdown(false);
            }
            if (this.headerModelSelect && !this.headerModelSelect.contains(e.target)) {
                this.toggleHeaderModelDropdown(false);
            }
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                this.toggleModelDropdown(false);
                this.toggleHeaderModelDropdown(false);
            }
        });

        // Desvanecido animado de los chats recientes al scrollear
        if (this.savedChatsList) {
            this.savedChatsList.addEventListener("scroll", () => this.updateChatsScrollFade());
        }

        // Acciones rápidas & sugerencias
        const handlePromptClick = (btn) => {
            const promptText = btn.getAttribute("data-prompt");
            if (promptText) {
                if (this.promptInput) {
                    this.promptInput.value = promptText;
                    this.autoGrowInput();
                }
                this.submitCurrentPrompt();
            }
        };

        this.quickBtns.forEach(btn => btn.addEventListener("click", () => handlePromptClick(btn)));
        this.suggChips.forEach(btn => btn.addEventListener("click", () => handlePromptClick(btn)));

        // Subida de archivos o multimedia: clip + arrastrar y soltar sobre el prompt
        if (this.btnAttach && this.fileInput) {
            this.btnAttach.addEventListener("click", () => this.fileInput.click());
            this.fileInput.addEventListener("change", () => {
                this.addAttachmentFiles(Array.from(this.fileInput.files || []));
                this.fileInput.value = "";
            });
        }
        if (this.promptForm) {
            this.promptForm.addEventListener("dragover", (e) => {
                e.preventDefault();
                this.promptForm.classList.add("agent-dragover");
            });
            this.promptForm.addEventListener("dragleave", () => this.promptForm.classList.remove("agent-dragover"));
            this.promptForm.addEventListener("drop", (e) => {
                e.preventDefault();
                this.promptForm.classList.remove("agent-dragover");
                this.addAttachmentFiles(Array.from(e.dataTransfer?.files || []));
            });
        }

        // Envío de formulario o botón de parada si está pensando
        if (this.promptForm) {
            this.promptForm.addEventListener("submit", (e) => {
                e.preventDefault();
                if (this.isThinking) {
                    this.stopCurrent();
                } else {
                    this.submitCurrentPrompt();
                }
            });
        }

        if (this.promptInput) {
            this.promptInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    this.submitCurrentPrompt();
                }
            });
            this.promptInput.addEventListener("input", () => this.autoGrowInput());
        }
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        if (!this.deck) return;
        this.isOpen = true;
        this.deck.classList.remove("agent-hidden");
        this.deck.setAttribute("aria-hidden", "false");
        setTimeout(() => {
            if (this.promptInput) this.promptInput.focus();
        }, 150);
    }

    close() {
        if (!this.deck) return;
        this.isOpen = false;
        this.deck.classList.add("agent-hidden");
        this.deck.setAttribute("aria-hidden", "true");
    }

    toggleExpand() {
        if (!this.deck) return;
        this.isExpanded = !this.isExpanded;
        this.deck.classList.toggle("agent-expanded", this.isExpanded);
    }

    selectModel(modelId) {
        if (!modelId || !this.modelsMeta[modelId]) return;
        this.activeModel = modelId;
        const meta = this.modelsMeta[modelId];

        // Sincronizar estado activo de las tarjetas en ambos dropdowns
        document.querySelectorAll(".agent-model-card").forEach(c => {
            c.classList.toggle("active", c.getAttribute("data-model") === modelId);
        });

        // Sincronizar HEADER
        if (this.headerPillName) this.headerPillName.textContent = meta.name;
        if (this.headerDot) this.headerDot.style.background = meta.color || "#f59e0b";

        // Sincronizar INPUT TOOLBAR
        if (this.inputModelNameEl) this.inputModelNameEl.textContent = meta.name;
        const inputDot = this.inputModelTag ? this.inputModelTag.querySelector(".agent-model-select-dot") : null;
        if (inputDot) inputDot.style.background = meta.color || "#f59e0b";

        // Sincronizar botón flotante
        if (this.fabModelPill) this.fabModelPill.textContent = meta.name;

        // Si el chat es nuevo y aún no hay mensajes del usuario, actualizar el mensaje de bienvenida
        if (this.history.length === 0 && this.messagesContainer) {
            const botAuthorSpan = this.messagesContainer.querySelector(".agent-msg-bot .agent-msg-author span");
            if (botAuthorSpan) botAuthorSpan.textContent = meta.name;
            const contentP = this.messagesContainer.querySelector(".agent-msg-bot .agent-msg-content p");
            if (contentP && contentP.innerHTML.includes("Nuevo chat iniciado")) {
                contentP.innerHTML = `Nuevo chat iniciado con <strong>${meta.name}</strong>. ¿En qué te ayudo ahora?`;
            }
        }
    }

    /** Abre/cierra el dropdown de modelos anclado en el header superior. */
    toggleHeaderModelDropdown(force) {
        if (!this.headerModelSelect) return;
        const open = typeof force === "boolean"
            ? force
            : !this.headerModelSelect.classList.contains("open");
        this.headerModelSelect.classList.toggle("open", open);
        if (this.headerModelPill) {
            this.headerModelPill.setAttribute("aria-expanded", open ? "true" : "false");
        }
    }

    /** Abre/cierra el dropdown de modelos anclado a la etiqueta del prompt. */
    toggleModelDropdown(force) {
        if (!this.modelSelect) return;
        const open = typeof force === "boolean"
            ? force
            : !this.modelSelect.classList.contains("open");
        this.modelSelect.classList.toggle("open", open);
        if (this.inputModelTag) {
            this.inputModelTag.setAttribute("aria-expanded", open ? "true" : "false");
        }
    }

    /** Activa el desvanecido superior/inferior de la lista de chats solo cuando hay scroll. */
    updateChatsScrollFade() {
        const el = this.savedChatsList;
        if (!el) return;
        const scrollable = el.scrollHeight > el.clientHeight + 4;
        el.classList.toggle("is-scrollable", scrollable);
        const atTop = el.scrollTop <= 2;
        const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
        el.classList.toggle("fade-top", scrollable && !atTop);
        el.classList.toggle("fade-bottom", scrollable && !atBottom);
    }

    autoGrowInput() {
        if (!this.promptInput) return;
        this.promptInput.style.height = "auto";
        this.promptInput.style.height = Math.min(this.promptInput.scrollHeight, 130) + "px";
    }

    /* =========================================================================
       SUBIDA DE ARCHIVOS Y MULTIMEDIA (clip junto al modelo + drag & drop)
       ========================================================================= */

    addAttachmentFiles(files) {
        const incoming = (files || []).filter(f => f && f.size > 0).slice(0, 6);
        if (!incoming.length) return;
        incoming.forEach(f => {
            const dup = this.pendingAttachments.some(a => a.name === f.name && a.size === f.size);
            if (!dup) this.pendingAttachments.push(f);
        });
        if (this.pendingAttachments.length > 6) {
            this.pendingAttachments = this.pendingAttachments.slice(-6);
            this.showToast("Máximo 6 adjuntos por mensaje (se conservan los últimos).", "warning");
        }
        this.renderAttachments();
    }

    removeAttachment(index) {
        this.pendingAttachments.splice(index, 1);
        this.renderAttachments();
    }

    renderAttachments() {
        if (!this.attachmentsBar) return;
        this.attachmentsBar.replaceChildren();
        if (!this.pendingAttachments.length) {
            this.attachmentsBar.style.display = "none";
            return;
        }
        this.attachmentsBar.style.display = "flex";
        this.pendingAttachments.forEach((file, i) => {
            const chip = document.createElement("div");
            chip.className = "agent-attach-chip";
            chip.title = file.name;
            const icon = document.createElement("span");
            icon.className = "agent-attach-icon";
            icon.textContent = this.fileIconFor(file);
            const name = document.createElement("span");
            name.className = "agent-attach-name";
            name.textContent = file.name;
            const size = document.createElement("span");
            size.className = "agent-attach-size";
            size.textContent = this.formatFileSize(file.size);
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "agent-attach-remove";
            remove.title = "Quitar adjunto";
            remove.textContent = "×";
            remove.addEventListener("click", () => this.removeAttachment(i));
            chip.append(icon, name, size, remove);
            this.attachmentsBar.appendChild(chip);
        });
    }

    fileIconFor(file) {
        const t = (file.type || "").toLowerCase();
        if (t.startsWith("image/")) return "🖼️";
        if (t.startsWith("video/")) return "🎬";
        if (t.startsWith("audio/")) return "🎵";
        if (t.includes("pdf")) return "📕";
        if (t.includes("json") || /\.(js|ts|py|css|html?|md|txt|xml|ya?ml|csv|ini|toml|sh|bat|ps1|sql)$/i.test(file.name)) return "📄";
        return "📎";
    }

    formatFileSize(bytes) {
        if (!bytes) return "0 B";
        const units = ["B", "KB", "MB", "GB"];
        let i = 0;
        let n = bytes;
        while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
        return `${n.toFixed(n >= 10 ? 0 : 1)} ${units[i]}`;
    }

    /**
     * Convierte los adjuntos en un bloque de contexto para el modelo:
     * los archivos de texto/código se incrustan (hasta 200 KB) y el resto
     * (imágenes, video, audio…) se lista con tipo y tamaño.
     */
    async buildAttachmentsBlock(files) {
        const TEXT_EXTS = /\.(txt|md|json|js|mjs|ts|jsx|tsx|py|css|scss|html?|xml|ya?ml|csv|ini|toml|cfg|conf|sh|bat|ps1|sql|log)$/i;
        const parts = [`📎 El usuario adjuntó ${files.length} archivo(s) en este mensaje:`];
        for (const f of files) {
            const isText = TEXT_EXTS.test(f.name) && f.size <= 200 * 1024;
            if (isText) {
                try {
                    const content = (await f.text()).slice(0, 12000);
                    const lang = (f.name.split(".").pop() || "").toLowerCase();
                    parts.push(`\n### ${f.name} (${this.formatFileSize(f.size)})\n\`\`\`${lang}\n${content}\n\`\`\``);
                } catch (e) {
                    parts.push(`- ${f.name} · ${f.type || "?"} · ${this.formatFileSize(f.size)} (no se pudo leer el contenido)`);
                }
            } else {
                parts.push(`- ${f.name} · tipo: ${f.type || "desconocido"} · tamaño: ${this.formatFileSize(f.size)}${(f.type || "").startsWith("image/") ? " (imagen adjunta)" : ""}`);
            }
        }
        parts.push("Ten en cuenta estos archivos para responder al usuario.");
        return parts.join("\n");
    }

    resetChat() {
        if (!this.messagesContainer) return;
        this.history = [];
        this.pendingAttachments = [];
        this.renderAttachments();
        this.chatId = null;
        this.ocSessionId = null;  // el siguiente guardado crea un chat nuevo
        this.loadSavedChatsList();
        this.messagesContainer.innerHTML = `
            <div class="agent-message agent-msg-bot">
                <div class="agent-msg-avatar">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/>
                        <path d="M4 11a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v7a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-7z"/>
                        <circle cx="9" cy="15" r="1"/>
                        <circle cx="15" cy="15" r="1"/>
                    </svg>
                </div>
                <div class="agent-msg-body">
                    <div class="agent-msg-author">AetherCopilot <span>${this.modelsMeta[this.activeModel].name}</span></div>
                    <div class="agent-msg-content">
                        <p>Nuevo chat iniciado con <strong>${this.modelsMeta[this.activeModel].name}</strong>. ¿En qué te ayudo ahora?</p>
                    </div>
                </div>
            </div>
        `;
    }

    appendUserMessage(text) {
        if (!this.messagesContainer) return;
        const msgDiv = document.createElement("div");
        msgDiv.className = "agent-message agent-msg-user";
        msgDiv.innerHTML = `
            <div class="agent-msg-body">
                <div style="white-space:pre-wrap;">${this.escapeHtml(text)}</div>
            </div>
        `;
        this.messagesContainer.appendChild(msgDiv);
        this.scrollToBottom();
    }

    appendBotThinking() {
        if (!this.messagesContainer) return;
        const id = "botThinking_" + Date.now();
        const msgDiv = document.createElement("div");
        msgDiv.className = "agent-message agent-msg-bot";
        msgDiv.id = id;
        msgDiv.innerHTML = `
            <div class="agent-msg-avatar">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/>
                    <path d="M4 11a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v7a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-7z"/>
                </svg>
            </div>
            <div class="agent-msg-body">
                <div class="agent-msg-author">AetherCopilot <span>${this.modelsMeta[this.activeModel].name}</span></div>
                <div class="agent-msg-content">
                    <p style="color:#94a3b8; display:flex; align-items:center; gap:8px; margin:0 0 6px;">
                        <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:#c084fc; animation:pulse 1s infinite;"></span>
                        <span id="thinkStatus_${id}">Pensando…</span>
                    </p>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(msgDiv);
        this.scrollToBottom();

        // Temporizador en vivo: muestra cuánto lleva trabajando el motor y
        // conserva el último estado informado por el streaming.
        const statusEl = document.getElementById(`thinkStatus_${id}`);
        const startedAt = Date.now();
        const timer = setInterval(() => {
            if (!statusEl || !statusEl.isConnected) {
                clearInterval(timer);
                return;
            }
            const secs = Math.round((Date.now() - startedAt) / 1000);
            const current = statusEl.dataset.status || "Pensando…";
            statusEl.textContent = `${current} · ${secs}s`;
        }, 1000);

        return id;
    }

    appendBotResponse(reply, actions = [], extra = {}, modelName = "GLM-5.3 Flash", reasoning = "", opts = {}) {
        if (!this.messagesContainer) return;
        const msgDiv = document.createElement("div");
        msgDiv.className = "agent-message agent-msg-bot";

        const uniqueThinkId = "think_" + Math.random().toString(36).substring(2, 9);
        const badgeId = "badge_" + uniqueThinkId;
        const textId = "text_" + uniqueThinkId;
        const cursorId = "cursor_" + uniqueThinkId;

        // Bloque desplegable de razonamiento / pensamiento (Estilo Antigravity / DeepSeek con Typewriter)
        let reasoningHtml = "";
        if (reasoning && reasoning.trim().length > 0) {
            reasoningHtml = `
                <details class="agent-thinking-dropdown" open>
                    <summary>
                        <span class="agent-thinking-icon">🧠</span>
                        <span>Pensamiento del modelo (${modelName})</span>
                        <span class="agent-thinking-badge" id="${badgeId}">Escribiendo...</span>
                    </summary>
                    <div class="agent-thinking-body">
                        <span class="agent-typewriter-text" id="${textId}"></span><span class="agent-typewriter-cursor" id="${cursorId}">|</span>
                    </div>
                </details>
            `;
        }

        // Badges visuales de acciones y archivos de contexto estilo Antigravity
        let actionsHtml = "";
        let contextPillsHtml = "";

        if (extra && extra.context_files && Array.isArray(extra.context_files) && extra.context_files.length > 0) {
            contextPillsHtml = `
                <div style="margin-bottom:8px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
                    <span style="font-size:11px; color:#94a3b8; font-weight:700; display:flex; align-items:center; gap:4px;">
                        📁 Contexto de código activo:
                    </span>
                    ${extra.context_files.map(f => `
                        <span style="font-size:11px; background:rgba(56,189,248,0.12); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); padding:2px 8px; border-radius:12px; font-family:'Geist Mono', monospace; font-weight:600;">
                            ${this.escapeHtml(f)}
                        </span>
                    `).join("")}
                </div>
            `;
        }

        if (actions && actions.length > 0) {
            actionsHtml = `<div style="margin-bottom:8px; display:flex; flex-wrap:wrap; gap:6px;">`;
            actions.forEach(a => {
                const type = a.type || "action";
                let icon = "⚡";
                let label = "Acción ejecutada";
                if (type === "navigate") { icon = "🚀"; label = `Navegando a: ${a.view || "Mesa"}`; }
                else if (type === "create_project") { icon = "🎬"; label = `Lanzando emisión: ${a.topic?.slice(0, 24)}...`; }
                else if (type === "create_thumbnail") { icon = "🖼️"; label = "Miniatura YouTube Creada"; }
                else if (type === "customize_ui") { icon = "🎨"; label = "Estilo de UI Actualizado"; }
                else if (type === "ren_mutate") { icon = "🛠️"; label = `Modo REN: ${a.selector || "UI"}`; }
                else if (type === "ren_reset") { icon = "🔄"; label = "Modo REN: UI Restablecida"; }
                else if (type === "modify_popups") { icon = "📐"; label = "Pop-ups Ajustados"; }
                else if (type === "edit_file") {
                    icon = "✏️";
                    const p = a.path || a.file_written || "archivo";
                    const fName = p.split("/").pop();
                    label = a.error
                        ? `edit_file: ${fName} [⚠️ ${a.error}]`
                        : `edit_file: ${fName} [✓ Modificado en disco]`;
                }
                else if (type === "read_file") {
                    icon = "📖";
                    const fName = (a.path || "archivo").split("/").pop();
                    label = a.error
                        ? `read_file: ${fName} [⚠️ ${a.error}]`
                        : `read_file: ${fName} [✓ Leído]`;
                }
                else if (type === "list_files") {
                    icon = "📁";
                    label = a.error
                        ? `list_files: ${a.dir || "web"} [⚠️ ${a.error}]`
                        : `list_files: ${a.dir || "web"} [✓ Listado]`;
                }
                else if (type === "search_code") {
                    icon = "🔍";
                    const count = a.count ?? (Array.isArray(a.matches) ? a.matches.length : 0);
                    label = a.error
                        ? `search_code: ${a.pattern || ""} [⚠️ ${a.error}]`
                        : `search_code: "${a.pattern || ""}" [✓ ${count} coincidencias · ${a.scanned_files ?? "?"} archivos]`;
                }
                else if (type === "modify_timeline_card" || type === "modify_card") {
                    icon = "📊";
                    label = a.card_url
                        ? `modify_timeline_card: ${a.headline || a.card_id || ""} [✓ Tarjeta re-renderizada]`
                        : `modify_timeline_card: ${a.headline || a.card_id || ""} [⚠️ Ver detalles]`;
                }

                actionsHtml += `<span class="agent-action-badge success">${icon} ${label}</span>`;
            });
            actionsHtml += `</div>`;
        }

        // Miniatura YouTube incrustada si existe
        let thumbHtml = "";
        if (extra && extra.thumbnail && extra.thumbnail.url) {
            thumbHtml = `
                <div class="agent-thumb-preview-card">
                    <img src="${extra.thumbnail.url}" alt="Portada YouTube">
                    <div class="agent-thumb-preview-footer">
                        <span style="font-size:11px; font-weight:700; color:#cbd5e1;">Miniatura 1280x720 (Alta Retención)</span>
                        <a href="${extra.thumbnail.url}" download="${extra.thumbnail.filename}" style="font-size:11px; font-weight:700; background:#a855f7; color:#fff; padding:4px 10px; border-radius:6px; text-decoration:none;">Descargar HD</a>
                    </div>
                </div>
            `;
        }

        let cleanReply = reply || "";
        if (typeof cleanReply === "string") {
            cleanReply = cleanReply.trim();
            if (cleanReply.startsWith("{") && cleanReply.includes('"reply"')) {
                try {
                    const parsed = JSON.parse(cleanReply);
                    if (parsed.reply) cleanReply = parsed.reply;
                } catch (e) {
                    const m = cleanReply.match(/"reply"\s*:\s*"((?:\\.|[^"\\])*)"/s);
                    if (m) cleanReply = m[1];
                }
            }
            cleanReply = cleanReply.replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\\/g, '\\');
        }

        // Respuesta con efecto typewriter: el mensaje ya no aparece de golpe.
        // Si había una respuesta anterior todavía escribiéndose, se completa al instante.
        this.finalizeActiveReplyStream();

        const replyStreamId = `replyStream_${uniqueThinkId}`;
        const replyCursorId = `replyCursor_${uniqueThinkId}`;

        msgDiv.innerHTML = `
            <div class="agent-msg-avatar">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/>
                    <path d="M4 11a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v7a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-7z"/>
                    <circle cx="9" cy="15" r="1"/>
                    <circle cx="15" cy="15" r="1"/>
                </svg>
            </div>
            <div class="agent-msg-body">
                <div class="agent-msg-author">AetherCopilot <span>${modelName}</span></div>
                <div class="agent-msg-content">
                    ${reasoningHtml}
                    ${contextPillsHtml}
                    ${actionsHtml}
                    <div class="agent-reply-stream" id="${replyStreamId}"></div><span class="agent-typewriter-cursor" id="${replyCursorId}">|</span>
                    ${thumbHtml}
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(msgDiv);
        this.scrollToBottom();

        // Respuesta al instante (historial cargado) o escrita palabra a palabra
        if (opts.instant) {
            this.activeReplyStream = null;
            const container = document.getElementById(replyStreamId);
            if (container) container.innerHTML = this.formatMarkdown(cleanReply);
            const cursorEl = document.getElementById(replyCursorId);
            if (cursorEl) cursorEl.remove();
            this.attachCodeBlockActions(msgDiv);
        } else {
            // Escribir la respuesta palabra a palabra con render Markdown progresivo
            this.streamReplyTypewriter(
                document.getElementById(replyStreamId),
                document.getElementById(replyCursorId),
                cleanReply,
                msgDiv,
            );
        }

        // Pensamiento: al instante si ya se transmitió en vivo; typewriter natural si no.
        if (reasoning && reasoning.trim().length > 0) {
            const textEl = document.getElementById(textId);
            const cursorEl = document.getElementById(cursorId);
            const badgeEl = document.getElementById(badgeId);
            if (textEl) {
                if (opts.instantReasoning || opts.instant) {
                    textEl.textContent = reasoning.trim();
                    if (badgeEl) {
                        badgeEl.textContent = "Completado";
                        badgeEl.style.borderColor = "rgba(16, 185, 129, 0.4)";
                        badgeEl.style.color = "#34d399";
                    }
                    if (cursorEl) cursorEl.remove();
                } else {
                    this.streamTypewriter(textEl, cursorEl, badgeEl, reasoning.trim());
                }
            }
        }
    }

    /**
     * Escribe la respuesta del modelo con efecto typewriter, re-renderizando el
     * Markdown de forma progresiva. Al terminar, conecta los botones de los
     * bloques de código (Copiar / Aplicar en vivo).
     */
    streamReplyTypewriter(containerEl, cursorEl, fullText, msgDiv) {
        if (!containerEl) return;
        const total = (fullText || "").length;
        if (!total) {
            if (cursorEl) cursorEl.remove();
            this.attachCodeBlockActions(msgDiv);
            return;
        }
        // Adaptativo: mensajes largos escriben más rápido para no eternizar la
        // espera, pero a un ritmo natural y legible (no de golpe).
        const chunk = total > 1500 ? 10 : total > 600 ? 6 : total > 250 ? 3 : 2;
        let index = 0;
        this.activeReplyStream = { containerEl, cursorEl, fullText, msgDiv };
        this.currentReplyTypewriterInterval = setInterval(() => {
            index = Math.min(index + chunk, total);
            containerEl.innerHTML = this.formatMarkdown(fullText.substring(0, index));
            this.scrollToBottom();
            if (index >= total) {
                this.finalizeActiveReplyStream();
            }
        }, 32);
    }

    /**
     * Completa al instante la respuesta que estaba escribiéndose (por ejemplo,
     * al llegar un mensaje nuevo o al pulsar Detener).
     */
    finalizeActiveReplyStream() {
        if (this.currentReplyTypewriterInterval) {
            clearInterval(this.currentReplyTypewriterInterval);
            this.currentReplyTypewriterInterval = null;
        }
        const stream = this.activeReplyStream;
        this.activeReplyStream = null;
        if (stream && stream.containerEl && stream.containerEl.isConnected) {
            stream.containerEl.innerHTML = this.formatMarkdown(stream.fullText || "");
            if (stream.cursorEl) stream.cursorEl.remove();
            this.attachCodeBlockActions(stream.msgDiv);
            this.scrollToBottom();
        }
    }

    /**
     * Conecta los botones interactivos de los bloques de código.
     */
    attachCodeBlockActions(msgDiv) {
        if (!msgDiv) return;
        msgDiv.querySelectorAll(".agent-code-copy-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const code = decodeURIComponent(btn.getAttribute("data-code") || "");
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(code).then(() => {
                        const original = btn.textContent;
                        btn.textContent = "✓ Copiado";
                        setTimeout(() => { btn.textContent = original; }, 2000);
                    });
                }
            });
        });

        msgDiv.querySelectorAll(".agent-code-apply-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const code = decodeURIComponent(btn.getAttribute("data-code") || "");
                btn.textContent = "⏳ Aplicando...";
                btn.disabled = true;

                // 1. Inyectar en vivo en el DOM
                let styleEl = document.getElementById("agentLiveAppliedStyles");
                if (!styleEl) {
                    styleEl = document.createElement("style");
                    styleEl.id = "agentLiveAppliedStyles";
                    document.head.appendChild(styleEl);
                }
                styleEl.textContent += "\n" + code;

                // 2. Cache-bust stylesheets
                document.querySelectorAll('link[rel="stylesheet"]').forEach(l => {
                    const base = l.href.split('?')[0];
                    l.href = `${base}?v=${Date.now()}`;
                });

                // 3. Persistir en disco via API edit-files
                try {
                    const resp = await fetch("/api/agent/edit-files", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            ops: [{
                                op: "append",
                                path: "web/static/css/theme/matte-dark.css",
                                content: `\n/* AetherCopilot Live UI Apply */\n${code}\n`
                            }]
                        })
                    });
                    const d = await resp.json();
                    if (d.ok) {
                        btn.textContent = "✓ Aplicado en disco";
                        btn.style.background = "#059669";
                        this.showToast("⚡ Estilos aplicados en pantalla y guardados en matte-dark.css", "success");
                    } else {
                        btn.textContent = "✓ Aplicado en vivo";
                    }
                } catch (e) {
                    btn.textContent = "✓ Aplicado en vivo";
                }
            });
        });
    }

    /**
     * Animación fluida de escritura palabra/carácter por carácter (Estilo Antigravity)
     */
    streamTypewriter(textEl, cursorEl, badgeEl, fullText, speed = 26) {
        if (!textEl) return;
        if (this.currentTypewriterInterval) {
            clearInterval(this.currentTypewriterInterval);
            this.currentTypewriterInterval = null;
        }

        let index = 0;
        const total = fullText.length;
        const chunk = total > 400 ? 5 : (total > 160 ? 3 : 1);

        this.currentTypewriterInterval = setInterval(() => {
            if (index < total) {
                index = Math.min(index + chunk, total);
                textEl.textContent = fullText.substring(0, index);
                this.scrollToBottom();
            } else {
                clearInterval(this.currentTypewriterInterval);
                this.currentTypewriterInterval = null;
                if (badgeEl) {
                    badgeEl.textContent = "Completado";
                    badgeEl.style.borderColor = "rgba(16, 185, 129, 0.4)";
                    badgeEl.style.color = "#34d399";
                }
                if (cursorEl) {
                    cursorEl.style.transition = "opacity 0.4s ease";
                    cursorEl.style.opacity = "0";
                    setTimeout(() => { if (cursorEl) cursorEl.remove(); }, 400);
                }
            }
        }, speed);
    }

    scrollToBottom() {
        if (!this.messagesContainer) return;
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    collectAppContext() {
        const urlParams = new URLSearchParams(window.location.search);
        const curProjId = urlParams.get("project") || urlParams.get("task") || window.currentProjectId || null;
        const curTitle = document.getElementById("topbarProjectTitle")?.textContent || "";
        const activeView = window.activeMode || "studio";
        const aspect = document.querySelector('input[name="kaiAspectRatio"]:checked')?.value || "16:9";

        const curSelItem = (typeof window.getSelectedItem === "function") ? window.getSelectedItem() : null;
        const selItemData = curSelItem ? {
            type: window.selectedEditorItem?.type,
            id: window.selectedEditorItem?.id,
            headline: curSelItem.headline || curSelItem.title || curSelItem.concept || curSelItem.name,
            stat_value: curSelItem.stat_value,
            body: curSelItem.body,
            scene_id: curSelItem.scene_id,
            start: curSelItem.start,
            duration: curSelItem.duration || (curSelItem.end ? curSelItem.end - curSelItem.start : 7)
        } : null;

        return {
            current_project_id: curProjId,
            current_project_name: curTitle,
            active_view: activeView,
            aspect_ratio: aspect,
            is_ren_mode: this.isRenMode,
            // El agente recuerda el último elemento seleccionado aunque el Modo
            // REN se apague: permite iterar ("ahora en rojo") sin re-seleccionar.
            target_selector: this.selectedElementSelector || this.lastRenSelector,
            selected_timeline_item: selItemData,
        };
    }

    stopCurrent() {
        if (this.currentTypewriterInterval) {
            clearInterval(this.currentTypewriterInterval);
            this.currentTypewriterInterval = null;
        }
        // Completar al instante cualquier respuesta que siga escribiéndose.
        this.finalizeActiveReplyStream();
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
        }
        this.isThinking = false;
        if (this.currentThinkingId) {
            const thinkEl = document.getElementById(this.currentThinkingId);
            if (thinkEl) thinkEl.remove();
            this.currentThinkingId = null;
        }
        this.resetSendButton();
        this.appendBotResponse("⏹️ **Generación detenida a petición del usuario.** ¿Deseas hacer otra consulta o pedir otra acción?", [], {}, "AetherCopilot");
    }

    resetSendButton() {
        if (!this.btnSend) return;
        this.btnSend.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
        `;
        this.btnSend.style.background = "";
        this.btnSend.title = "Enviar mensaje";
        this.btnSend.disabled = false;
    }

    setStopButton() {
        if (!this.btnSend) return;
        this.btnSend.innerHTML = `<span style="font-size:13px; font-weight:800; display:flex; align-items:center; justify-content:center;">■</span>`;
        this.btnSend.style.background = "#ef4444";
        this.btnSend.title = "Detener generación en curso";
        this.btnSend.disabled = false;
    }

    async submitCurrentPrompt() {
        if (!this.promptInput) return;
        const text = this.promptInput.value.trim();
        const files = this.pendingAttachments.slice();
        if (!text && !files.length) return;

        // Los adjuntos viajan dentro del mensaje: texto/código se incrusta y
        // la multimedia se lista para que el modelo sepa con qué trabaja.
        let messageToSend = text;
        let displayText = text;
        if (files.length) {
            const block = await this.buildAttachmentsBlock(files);
            messageToSend = (text ? text + "\n\n" : "") + block;
            displayText = (text ? text + "\n" : "") + `📎 ${files.length} archivo(s) adjunto(s)`;
        }

        // Si ya había una tarea pensando, se aborta limpiamente
        if (this.isThinking && this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
            if (this.currentThinkingId) {
                const prevEl = document.getElementById(this.currentThinkingId);
                if (prevEl) prevEl.remove();
            }
        }

        this.promptInput.value = "";
        this.autoGrowInput();
        this.pendingAttachments = [];
        this.renderAttachments();
        this.appendUserMessage(displayText);
        this.isThinking = true;
        this.setStopButton();

        this.currentThinkingId = this.appendBotThinking();
        const appContext = this.collectAppContext();
        this.currentAbortController = new AbortController();

        // Preparar historial (solo texto plano para ahorrar tokens)
        const historyToSend = this.history.slice(-10).map(h => ({
            role: h.role,
            content: typeof h.content === "string" ? h.content.slice(0, 300) : String(h.content).slice(0, 300)
        }));

        // ── STREAMING EN TIEMPO REAL: el pensamiento del modelo se muestra EN VIVO ──
        let liveReasoning = "";
        let sawAnyEvent = false;
        try {
            const resp = await fetch("/api/agent/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                signal: this.currentAbortController.signal,
                body: JSON.stringify({
                    message: messageToSend,
                    model_id: this.activeModel,
                    app_context: appContext,
                    history: historyToSend,
                    oc_session_id: this.ocSessionId || null,
                }),
            });
            if (!resp.ok || !resp.body) {
                throw new Error("stream_no_disponible");
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let finalPayload = null;

            const handleEvent = (ev) => {
                if (!ev || !ev.type) return;
                sawAnyEvent = true;
                if (ev.type === "status") {
                    this.updateThinkingStatus(this.currentThinkingId, ev.message);
                } else if (ev.type === "reasoning") {
                    liveReasoning = ev.text || liveReasoning;
                    this.updateThinkingReasoning(this.currentThinkingId, liveReasoning);
                } else if (ev.type === "tool") {
                    const toolName = ev.title || ev.tool || "Herramienta";
                    const isDone = (ev.status === "completed" || ev.status === "done" || ev.status === "success");
                    this.updateThinkingStatus(this.currentThinkingId, isDone ? `✓ ${toolName}` : `⚙️ ${toolName}…`);
                } else if (ev.type === "final") {
                    finalPayload = ev.payload || {};
                } else if (ev.type === "error") {
                    throw new Error(ev.message || "Error del motor del agente.");
                }
            };

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                let sep;
                while ((sep = buffer.indexOf("\n\n")) !== -1) {
                    const chunk = buffer.slice(0, sep);
                    buffer = buffer.slice(sep + 2);
                    for (const line of chunk.split("\n")) {
                        if (!line.startsWith("data:")) continue;
                        try { handleEvent(JSON.parse(line.slice(5).trim())); }
                        catch (parseErr) { if (parseErr.message && !parseErr.message.includes("JSON")) throw parseErr; }
                    }
                }
                if (finalPayload) break;
            }

            if (!finalPayload) throw new Error("stream_sin_final");
            this.handleAgentResponse(finalPayload, displayText, liveReasoning, true);
        } catch (streamErr) {
            if (streamErr.name === "AbortError") {
                console.log("[AgentCopilot] Petición abortada.");
                return;
            }
            // Fallback al endpoint clásico si el stream falló antes de entregar algo.
            if (!sawAnyEvent) {
                try {
                    const resp2 = await fetch("/api/agent/chat", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        signal: this.currentAbortController.signal,
                        body: JSON.stringify({
                            message: messageToSend,
                            model_id: this.activeModel,
                            app_context: appContext,
                            history: historyToSend,
                            oc_session_id: this.ocSessionId || null,
                        }),
                    });
                    const data = await resp2.json();
                    if (!resp2.ok) throw new Error(data.detail || "Error al procesar mensaje");
                    this.handleAgentResponse(data, displayText, data.reasoning || "", false);
                } catch (err2) {
                    if (err2.name === "AbortError") return;
                    const thinkEl = document.getElementById(this.currentThinkingId);
                    if (thinkEl) thinkEl.remove();
                    this.currentThinkingId = null;
                    this.appendBotResponse(`⚠️ No se pudo completar la solicitud: ${err2.message}`, [], {}, "Error");
                }
            } else {
                const thinkEl = document.getElementById(this.currentThinkingId);
                if (thinkEl) thinkEl.remove();
                this.currentThinkingId = null;
                this.appendBotResponse(`⚠️ La transmisión se interrumpió: ${streamErr.message || "error desconocido"}`, [], {}, "Error");
            }
        } finally {
            this.isThinking = false;
            this.currentAbortController = null;
            this.resetSendButton();
        }
    }

    /**
     * Procesa la respuesta final del agente: renderiza, guarda historial,
     * ejecuta acciones y persiste el chat en disco.
     */
    handleAgentResponse(data, userText, reasoning, reasoningWasStreamed) {
        const thinkEl = document.getElementById(this.currentThinkingId);
        if (thinkEl) thinkEl.remove();
        this.currentThinkingId = null;

        if (data.extra && data.extra.oc_session_id) {
            this.ocSessionId = data.extra.oc_session_id;
        }
        const modelLabel = this.modelsMeta[data.model_used]?.name || this.modelsMeta[this.activeModel]?.name || data.model_used;
        // Si el pensamiento ya se mostró en vivo, no se re-escribe con typewriter.
        this.appendBotResponse(data.reply, data.actions, data.extra, modelLabel, reasoning || "", {
            instantReasoning: Boolean(reasoningWasStreamed),
        });

        this.history.push({ role: "user", content: userText });
        this.history.push({ role: "assistant", content: data.reply || "" });
        if (this.history.length > 20) this.history = this.history.slice(-20);

        if (data.actions && Array.isArray(data.actions)) {
            this.executeAppActions(data.actions, data.extra);
        }

        // Persistencia: cada intercambio se guarda; el almacén conserva 20 chats.
        this.saveCurrentChat();
    }

    /**
     * Actualiza el texto de estado dentro del mensaje "Pensando...".
     */
    updateThinkingStatus(thinkId, status) {
        if (!thinkId) return;
        const el = document.getElementById(`thinkStatus_${thinkId}`);
        if (!el) return;
        el.dataset.status = status || "Pensando…";
        el.textContent = el.dataset.status;
    }

    /**
     * Muestra el razonamiento del modelo EN TIEMPO REAL dentro del mensaje
     * "Pensando..." mientras el modelo piensa.
     */
    updateThinkingReasoning(thinkId, text) {
        if (!thinkId || !text) return;
        const bubble = document.getElementById(thinkId);
        if (!bubble) return;
        let area = document.getElementById(`thinkReasoning_${thinkId}`);
        if (!area) {
            const content = bubble.querySelector(".agent-msg-content");
            if (!content) return;
            area = document.createElement("details");
            area.id = `thinkReasoning_${thinkId}`;
            area.className = "agent-thinking-dropdown";
            area.open = true;
            area.innerHTML = `<summary>
                    <span class="agent-thinking-icon">🧠</span>
                    <span>Pensamiento en tiempo real</span>
                    <span class="agent-thinking-badge">Escribiendo…</span>
                </summary>
                <div class="agent-thinking-body"><span class="agent-typewriter-text"></span></div>`;
            content.appendChild(area);
        }
        const textEl = area.querySelector(".agent-typewriter-text");
        if (textEl) textEl.textContent = text;
        this.scrollToBottom();
    }

    /* =========================================================================
       PERSISTENCIA DE CHATS (hasta 20 conversaciones guardadas en disco)
       ========================================================================= */

    async saveCurrentChat() {
        if (!this.history.length) return;
        try {
            const resp = await fetch("/api/agent/chats", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat_id: this.chatId, messages: this.history }),
            });
            const data = await resp.json();
            if (resp.ok && data.chat) this.chatId = data.chat.id;
            this.loadSavedChatsList();
        } catch (e) {
            console.warn("[AgentCopilot] No se pudo guardar el chat:", e);
        }
    }

    async loadSavedChatsList() {
        if (!this.savedChatsList) return;
        try {
            const resp = await fetch("/api/agent/chats");
            const data = await resp.json();
            const chats = Array.isArray(data.chats) ? data.chats : [];
            this.savedChatsList.replaceChildren();
            if (!chats.length) {
                const empty = document.createElement("span");
                empty.className = "agent-chats-empty";
                empty.textContent = "Sin chats guardados todavía";
                this.savedChatsList.appendChild(empty);
                this.updateChatsScrollFade();
                return;
            }
            chats.forEach(chat => {
                const item = document.createElement("div");
                item.className = `agent-chat-item${chat.id === this.chatId ? " is-active" : ""}`;
                const button = document.createElement("button");
                button.type = "button";
                button.className = "agent-chat-item-open";
                const title = document.createElement("span");
                title.className = "agent-chat-item-title";
                title.textContent = chat.title || "Chat sin título";
                const meta = document.createElement("span");
                meta.className = "agent-chat-item-time";
                meta.textContent = this.formatChatTime(chat.updated_at);
                button.append(title, meta);
                button.addEventListener("click", () => this.openSavedChat(chat.id));
                const del = document.createElement("button");
                del.type = "button";
                del.className = "agent-chat-item-delete";
                del.title = "Eliminar chat";
                del.textContent = "×";
                del.addEventListener("click", (event) => {
                    event.stopPropagation();
                    this.deleteSavedChat(chat.id);
                });
                item.append(button, del);
                this.savedChatsList.appendChild(item);
            });
        } catch (e) {
            console.warn("[AgentCopilot] No se pudo listar los chats:", e);
        }
    }

    formatChatTime(iso) {
        const date = iso ? new Date(iso) : null;
        if (!date || Number.isNaN(date.valueOf())) return "";
        const diffMin = Math.floor((Date.now() - date.valueOf()) / 60000);
        if (diffMin < 1) return "ahora";
        if (diffMin < 60) return `hace ${diffMin} min`;
        if (diffMin < 1440) return `hace ${Math.floor(diffMin / 60)} h`;
        return date.toLocaleDateString([], { day: "2-digit", month: "short" });
    }

    async openSavedChat(chatId) {
        try {
            const resp = await fetch(`/api/agent/chats/${encodeURIComponent(chatId)}`);
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || "No se pudo abrir el chat.");
            const chat = data.chat || {};
            this.chatId = chat.id || chatId;
            this.history = Array.isArray(chat.messages) ? chat.messages.slice() : [];
            this.renderHistoryMessages();
            this.loadSavedChatsList();
        } catch (e) {
            this.showToast(`No se pudo abrir el chat: ${e.message}`, "error");
        }
    }

    async deleteSavedChat(chatId) {
        try {
            const resp = await fetch(`/api/agent/chats/${encodeURIComponent(chatId)}`, { method: "DELETE" });
            if (!resp.ok) throw new Error("El servidor no pudo eliminarlo.");
            if (chatId === this.chatId) this.chatId = null;  // la conversación en pantalla sigue; el próximo guardado crea uno nuevo
            this.loadSavedChatsList();
        } catch (e) {
            this.showToast(`No se pudo eliminar el chat: ${e.message}`, "error");
        }
    }

    renderHistoryMessages() {
        if (!this.messagesContainer) return;
        this.finalizeActiveReplyStream();
        this.messagesContainer.replaceChildren();
        const welcome = document.createElement("div");
        welcome.className = "agent-message agent-msg-bot";
        welcome.innerHTML = `
            <div class="agent-msg-avatar">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/>
                    <path d="M4 11a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v7a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-7z"/>
                    <circle cx="9" cy="15" r="1"/>
                    <circle cx="15" cy="15" r="1"/>
                </svg>
            </div>
            <div class="agent-msg-body">
                <div class="agent-msg-author">AetherCopilot <span>chat recuperado</span></div>
                <div class="agent-msg-content"><p>Conversación restaurada. Puedes continuar donde la dejaste.</p></div>
            </div>
        `;
        this.messagesContainer.appendChild(welcome);
        (this.history || []).forEach(msg => {
            if (!msg || !msg.content) return;
            if (msg.role === "user") this.appendUserMessage(msg.content);
            else this.appendBotResponse(msg.content, [], {}, "AetherCopilot", "", { instant: true });
        });
        this.scrollToBottom();
    }

    /**
     * Ejecuta las acciones devueltas por el agente directamente sobre la UI y plataforma.
     */
    executeAppActions(actions, extra) {
        if (!Array.isArray(actions)) return;
        // ¿Alguna acción escribió archivos reales? → necesitamos recargar
        let needsReload = false;
        const filesEdited = [];

        actions.forEach(rawAction => {
            if (!rawAction) return;
            let action = Object.assign({}, rawAction);
            // Normalizar formato polimórfico
            if (!action.type) {
                const VALID = ["ren_mutate","ren_reset","navigate","create_project","create_thumbnail",
                    "open_project","show_notification","customize_ui","modify_popups",
                    "highlight_element","set_playback","switch_model","edit_file"];
                for (const key of Object.keys(action)) {
                    if (VALID.includes(key)) {
                        const val = action[key];
                        if (typeof val === "object" && val !== null) {
                            action = Object.assign({ type: key }, val);
                        } else if (typeof val === "string" && key === "navigate") {
                            action = { type: "navigate", view: val };
                        } else {
                            action = { type: key, value: val };
                        }
                        break;
                    }
                }
            }
            const type = action.type;

            // Deduplicar: la misma acción puede llegar por SSE y drenada del turno.
            if (action.uid) {
                if (this.seenActionUids.has(action.uid)) return;
                this.seenActionUids.add(action.uid);
                if (this.seenActionUids.size > 500) {
                    this.seenActionUids.delete(this.seenActionUids.values().next().value);
                }
            }

            // ── ACCIÓN REAL: Archivo modificado en disco ──
            if (type === "edit_file") {
                const targetPath = action.path || action.file_written || "";
                const isCss = targetPath.endsWith(".css");
                if (isCss) {
                    // Inyección y hot-reload visual instantáneo (sin recargar ni perder el chat)
                    let liveStyle = document.getElementById("agentLiveAppliedStyles");
                    if (!liveStyle) {
                        liveStyle = document.createElement("style");
                        liveStyle.id = "agentLiveAppliedStyles";
                        document.head.appendChild(liveStyle);
                    }
                    if (action.css_code || action.content) {
                        liveStyle.textContent += "\n" + (action.css_code || action.content);
                    }
                    // Refrescar links de stylesheet
                    document.querySelectorAll('link[rel="stylesheet"]').forEach(l => {
                        const base = l.href.split("?")[0];
                        l.href = `${base}?v=${Date.now()}`;
                    });
                    this.showToast(`🎨 Estilos en ${targetPath.split('/').pop()} aplicados en pantalla y guardados en disco.`, "success");
                } else if (action.reload) {
                    needsReload = true;
                    filesEdited.push(targetPath);
                }
            }

            // Modificación de tarjeta de línea de tiempo por IA
            if (type === "modify_timeline_card" || type === "modify_card") {
                if (typeof window.updateCardFromCopilot === "function") {
                    const ok = window.updateCardFromCopilot(action);
                    if (ok) {
                        this.showToast(`📊 Tarjeta "${action.headline || action.card_id}" actualizada con éxito en la línea de tiempo.`, "success");
                    }
                }
            }


            // 0. Cambio de modelo
            if (type === "switch_model" && action.model_id) {
                this.selectModel(action.model_id);
            }

            // 1. Navegación
            if (type === "navigate") {
                const targetView = (action.view || "studio").toLowerCase();
                if (typeof window.switchMode === "function") {
                    if (targetView === "mesa" || targetView === "studio") {
                        window.switchMode("studio");
                    } else if (targetView === "projects") {
                        window.switchMode("projects");
                    } else if (targetView === "streamer") {
                        window.switchMode("streamer");
                    } else if (targetView === "copilot") {
                        window.switchMode("copilot");
                    } else if (targetView === "multiagent" || targetView === "multi-agent" || targetView === "dev") {
                        window.switchMode("multiagent");
                    }
                }
                if (action.project_id && typeof window.openProject === "function") {
                    window.openProject(action.project_id);
                }
            }

            // 2. Abrir proyecto específico
            if (type === "open_project" && action.project_id) {
                if (typeof window.openProject === "function") {
                    window.openProject(action.project_id);
                    if (typeof window.switchMode === "function") window.switchMode("studio");
                }
            }

            // 3. Creación de proyecto
            if (type === "create_project") {
                // IDs reales verificados: streamerTopic, streamerDuration, streamerFormat, startStreamerBtn
                const topicInput = document.getElementById("streamerTopic") || document.getElementById("kaiTopicInput");
                const durSelect  = document.getElementById("streamerDuration") || document.getElementById("kaiDurationSelect");
                const fmtSelect  = document.getElementById("streamerFormat");
                const startBtn   = document.getElementById("startStreamerBtn");
                // Navegar al streamer primero para asegurar que los controles estén visibles
                if (typeof window.switchMode === "function") window.switchMode("streamer");
                if (topicInput && action.topic) topicInput.value = action.topic;
                if (durSelect && action.duration_sec) durSelect.value = String(action.duration_sec);
                if (fmtSelect && action.aspect_ratio) {
                    // streamerFormat usa valores como "16:9", "9:16", "1:1"
                    fmtSelect.value = action.aspect_ratio;
                }
                if (startBtn) {
                    // Pequeño delay para que el DOM procese los valores antes del submit
                    setTimeout(() => startBtn.click(), 150);
                }
            }

            // 4. Miniatura generada
            if (type === "create_thumbnail" || (extra && extra.thumbnail)) {
                const thumb = (extra && extra.thumbnail) || action;
                const thumbImg  = document.getElementById("resThumbnailImg");
                const thumbCard = document.getElementById("resThumbnailCard");
                const thumbBtn  = document.getElementById("btnDownloadThumbnail");
                if (thumbImg && thumb.url) {
                    thumbImg.src = thumb.url;
                    if (thumbCard) thumbCard.style.display = "flex";
                    if (thumbBtn) thumbBtn.href = thumb.url;
                }
            }

            // 5. Personalización de colores y acentos
            if (type === "customize_ui") {
                if (action.accent_color) {
                    document.documentElement.style.setProperty("--prism-accent", action.accent_color);
                    document.documentElement.style.setProperty("--neon-cyan", action.accent_color);
                    const styleTag = document.getElementById("agentCustomUiStyles") || document.createElement("style");
                    styleTag.id = "agentCustomUiStyles";
                    styleTag.textContent = `
                        .streamer-btn-primary, .prism-sb-tab.active, .agent-fab-launcher {
                            border-color: ${action.accent_color} !important;
                            box-shadow: 0 0 16px ${action.accent_color}44 !important;
                        }
                    `;
                    document.head.appendChild(styleTag);
                }
                if (action.bg_color) {
                    document.documentElement.style.setProperty("--surface-1", action.bg_color);
                }
            }

            // 6. MODO REN: Mutaciones en vivo
            if (type === "ren_mutate") {
                this.applyRenMutation(action);
            }

            // 7. MODO REN: Reseteo
            if (type === "ren_reset") {
                this.resetRenModifications();
            }

            // 8. Modificar popups
            if (type === "modify_popups") {
                const scale = action.scale || "medium";
                const style = action.style || "broadcast_amber";
                const styleTag = document.getElementById("agentPopupStyles") || document.createElement("style");
                styleTag.id = "agentPopupStyles";
                const scaleMap = { large: "1.15", medium: "1", small: "0.85" };
                const sc = scaleMap[scale] || "1";
                styleTag.textContent = `.popup-overlay { transform: scale(${sc}); } .popup-card { --popup-style: '${style}'; }`;
                document.head.appendChild(styleTag);
            }

            // 9. Resaltar elemento con pulso
            if (type === "highlight_element" && action.selector) {
                const target = document.querySelector(action.selector);
                if (target) {
                    target.scrollIntoView({ behavior: "smooth", block: "center" });
                    const color = action.color || "#38bdf8";
                    target.style.transition = "box-shadow 0.3s ease";
                    target.style.boxShadow = `0 0 28px ${color}, 0 0 8px ${color}88`;
                    setTimeout(() => { target.style.boxShadow = ""; }, 2800);
                }
            }

            // 10. Notificación toast
            if (type === "show_notification") {
                this.showToast(action.message || "Acción completada.", action.level || "info");
            }

            // 11. Control de reproducción
            if (type === "set_playback") {
                const video = document.getElementById("masterVideoPlayer") || document.getElementById("videoPlayer") || document.querySelector("video");
                if (video) {
                    if (action.action === "play") video.play();
                    else if (action.action === "pause") video.pause();
                    else if (action.action === "seek" && action.time != null) {
                        video.currentTime = Number(action.time);
                    }
                }
            }
        });

        // ── Si se editaron archivos que requieren recarga (HTML / JS estructurales) ──
        if (needsReload && filesEdited.length > 0) {
            const fileList = filesEdited.map(f => f.split("/").pop()).join(", ");
            this.showToast(`✏️ Archivos estructurales modificados: ${fileList} — Recargando...`, "info");
            setTimeout(() => {
                window.location.reload();
            }, 1800);
        }
    }

    /**
     * Muestra una notificación toast flotante en la app.
     */
    showToast(message, level = "info") {
        const colors = {
            success: { bg: "#10b981", icon: "✅" },
            error:   { bg: "#ef4444", icon: "❌" },
            warning: { bg: "#f59e0b", icon: "⚠️" },
            info:    { bg: "#38bdf8", icon: "ℹ️" },
        };
        const c = colors[level] || colors.info;
        const toast = document.createElement("div");
        toast.style.cssText = `
            position: fixed; bottom: 88px; right: 24px; z-index: 99999;
            background: #1e293b; border: 1px solid ${c.bg}55;
            border-left: 3px solid ${c.bg}; color: #e2e8f0;
            padding: 12px 18px; border-radius: 10px;
            font-size: 13px; font-weight: 500; max-width: 320px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            display: flex; align-items: center; gap: 10px;
            animation: slideInRight 0.3s ease;
            pointer-events: none;
        `;
        toast.innerHTML = `<span>${c.icon}</span><span>${this.escapeHtml(message)}</span>`;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.transition = "opacity 0.4s ease, transform 0.4s ease";
            toast.style.opacity = "0";
            toast.style.transform = "translateX(20px)";
            setTimeout(() => toast.remove(), 400);
        }, 3500);
    }

    /* =========================================================================
       MÉTODOS DEL MODO REN (RENDER / EDIT NETWORK) & SELECTOR DE ELEMENTOS
       ========================================================================= */

    toggleRenMode(force) {
        this.isRenMode = force !== undefined ? force : !this.isRenMode;
        if (this.deck) {
            this.deck.classList.toggle("ren-mode-active", this.isRenMode);
        }
        if (this.btnToggleRen) {
            this.btnToggleRen.classList.toggle("active", this.isRenMode);
        }
        if (this.renToolbar) {
            this.renToolbar.style.display = this.isRenMode ? "flex" : "none";
        }
        if (this.promptInput) {
            if (this.isRenMode) {
                this.promptInput.placeholder = "Modo REN activo: selecciona elementos o escribe 'cambia el botón a cian', 'oculta la barra'...";
            } else {
                this.promptInput.placeholder = "Pídele al agente lo que quieras en la app... (Enter para enviar)";
                this.stopElementPicker();
            }
        }
    }

    toggleElementPicker() {
        if (this.isInspectorActive) {
            this.stopElementPicker();
        } else {
            this.startElementPicker();
        }
    }

    startElementPicker() {
        if (!this.isRenMode) {
            this.toggleRenMode(true);
        }
        this.isInspectorActive = true;
        document.body.classList.add("ren-inspector-active");

        if (this.btnPickElement) {
            this.btnPickElement.classList.add("picking");
            this.btnPickElement.innerHTML = `<span>✕ Cancelar Selección</span>`;
        }
        if (this.deck) {
            this.deck.style.opacity = "0.35";
            this.deck.style.pointerEvents = "none";
        }
        if (this.inspectorOverlay) {
            this.inspectorOverlay.style.display = "block";
        }

        this._onInspectorMove = (e) => {
            const el = document.elementFromPoint(e.clientX, e.clientY);
            if (!el || el.closest("#agentChatDeck") || el.closest("#agentRenInspectorOverlay")) {
                if (this.inspectorOverlay) this.inspectorOverlay.style.display = "none";
                return;
            }

            const rect = el.getBoundingClientRect();
            if (this.inspectorOverlay) {
                this.inspectorOverlay.style.display = "block";
                this.inspectorOverlay.style.top = `${rect.top}px`;
                this.inspectorOverlay.style.left = `${rect.left}px`;
                this.inspectorOverlay.style.width = `${rect.width}px`;
                this.inspectorOverlay.style.height = `${rect.height}px`;
            }

            const tagName = el.tagName.toLowerCase();
            const idPart = el.id ? `#${el.id}` : "";
            const classPart = !el.id && el.classList.length ? `.${el.classList[0]}` : "";
            if (this.inspectorTag) this.inspectorTag.textContent = tagName;
            if (this.inspectorSel) this.inspectorSel.textContent = idPart || classPart || "";
        };

        this._onInspectorClick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            const el = document.elementFromPoint(e.clientX, e.clientY);
            if (!el || el.closest("#agentChatDeck") || el.closest("#agentRenInspectorOverlay")) {
                return;
            }

            // Deducir mejor selector CSS
            let selector = "";
            if (el.id) {
                selector = `#${el.id}`;
            } else if (el.classList.length) {
                selector = `${el.tagName.toLowerCase()}.${Array.from(el.classList).slice(0, 2).join(".")}`;
            } else {
                selector = el.tagName.toLowerCase();
            }

            this.setRenTarget(selector);
            this.stopElementPicker();
        };

        this._onInspectorKey = (e) => {
            if (e.key === "Escape") {
                this.stopElementPicker();
            }
        };

        window.addEventListener("mousemove", this._onInspectorMove, { passive: true });
        window.addEventListener("click", this._onInspectorClick, { capture: true, once: true });
        window.addEventListener("keydown", this._onInspectorKey);
    }

    stopElementPicker() {
        this.isInspectorActive = false;
        document.body.classList.remove("ren-inspector-active");

        if (this.btnPickElement) {
            this.btnPickElement.classList.remove("picking");
            this.btnPickElement.innerHTML = `
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="22" y1="12" x2="18" y2="12"/>
                    <line x1="6" y1="12" x2="2" y2="12"/>
                    <line x1="12" y1="6" x2="12" y2="2"/>
                    <line x1="12" y1="22" x2="12" y2="18"/>
                </svg>
                <span>🎯 Seleccionar Elemento</span>
            `;
        }
        if (this.deck) {
            this.deck.style.opacity = "1";
            this.deck.style.pointerEvents = "auto";
        }
        if (this.inspectorOverlay) {
            this.inspectorOverlay.style.display = "none";
        }

        if (this._onInspectorMove) window.removeEventListener("mousemove", this._onInspectorMove);
        if (this._onInspectorClick) window.removeEventListener("click", this._onInspectorClick, { capture: true });
        if (this._onInspectorKey) window.removeEventListener("keydown", this._onInspectorKey);
    }

    setRenTarget(selector) {
        this.selectedElementSelector = selector;
        this.lastRenSelector = selector;  // memoria de iteración: sigue vigente al apagar REN
        if (this.renTargetPill && this.renTargetSelText) {
            this.renTargetSelText.textContent = selector;
            this.renTargetPill.style.display = "inline-flex";
        }
        // Resaltar momentáneamente el elemento seleccionado
        const target = document.querySelector(selector);
        if (target) {
            target.style.transition = "box-shadow 0.3s ease";
            target.style.boxShadow = "0 0 25px #06b6d4";
            setTimeout(() => { target.style.boxShadow = ""; }, 1800);
        }
        if (this.promptInput) {
            this.promptInput.focus();
            if (!this.promptInput.value) {
                this.promptInput.value = `Modifica ${selector}: `;
                this.autoGrowInput();
            }
        }
    }

    clearRenTarget() {
        this.selectedElementSelector = null;
        if (this.renTargetPill) {
            this.renTargetPill.style.display = "none";
        }
    }

    handleRenActionClick(actionType) {
        const sel = this.selectedElementSelector || "button, .streamer-btn-primary";
        let styles = {};
        let op = "style";

        if (actionType === "color_cyan") {
            styles = { borderColor: "#06b6d4", boxShadow: "0 0 20px rgba(6, 182, 212, 0.4)", color: "#06b6d4" };
        } else if (actionType === "color_emerald") {
            styles = { borderColor: "#10b981", boxShadow: "0 0 20px rgba(16, 185, 129, 0.4)", color: "#10b981" };
        } else if (actionType === "color_purple") {
            styles = { borderColor: "#a855f7", boxShadow: "0 0 20px rgba(168, 85, 247, 0.4)", color: "#a855f7" };
        } else if (actionType === "color_amber") {
            styles = { borderColor: "#f59e0b", boxShadow: "0 0 20px rgba(245, 158, 11, 0.4)", color: "#f59e0b" };
        } else if (actionType === "glow") {
            styles = { boxShadow: "0 0 28px rgba(6, 182, 212, 0.6)", borderColor: "#38bdf8" };
        } else if (actionType === "scale_up") {
            styles = { transform: "scale(1.1)", transformOrigin: "center" };
        } else if (actionType === "hide") {
            op = "hide";
        } else if (actionType === "remove") {
            op = "remove";
        }

        this.applyRenMutation({
            selector: sel,
            operation: op,
            styles: styles,
        });

        this.appendBotResponse(`✨ **[Modo REN]** Acción ejecutada sobre \`${sel}\` (operación: \`${op}\`).`, [{
            type: "ren_mutate",
            selector: sel,
            operation: op
        }], {}, "Modo REN");
    }

    /**
     * Normaliza los estilos de una acción ren_mutate a un objeto {propiedad: valor}.
     * Los modelos a veces envían "styles" como string CSS ("background: #06b6d4")
     * en lugar de objeto; sin normalizar, Object.entries() itera letra por letra
     * y genera CSS roto (el cambio nunca aparece en pantalla).
     */
    normalizeStyles(styles) {
        if (!styles) return {};
        if (typeof styles === "string") {
            const obj = {};
            styles.split(";").forEach(pair => {
                const idx = pair.indexOf(":");
                if (idx === -1) return;
                const prop = pair.slice(0, idx).trim();
                const value = pair.slice(idx + 1).trim();
                if (prop && value) obj[prop] = value;
            });
            return obj;
        }
        if (typeof styles === "object") {
            const obj = {};
            Object.entries(styles).forEach(([k, v]) => {
                if (k && v !== null && v !== undefined) obj[k] = String(v);
            });
            return obj;
        }
        return {};
    }

    applyRenMutation(action) {
        const sel = action.selector || "body";
        const op = action.operation || "style";
        const styles = this.normalizeStyles(action.styles);

        if (op === "remove") {
            const targets = document.querySelectorAll(sel);
            targets.forEach(t => {
                t.style.setProperty("display", "none", "important");
                t.style.setProperty("height", "0", "important");
                t.style.setProperty("overflow", "hidden", "important");
                t.style.setProperty("pointer-events", "none", "important");
                t.setAttribute("data-ren-removed", "true");
            });
            this.renStylesMap[sel] = {
                display: "none",
                height: "0",
                overflow: "hidden",
                pointerEvents: "none"
            };
        } else if (op === "hide") {
            const targets = document.querySelectorAll(sel);
            targets.forEach(t => t.style.setProperty("display", "none", "important"));
            this.renStylesMap[sel] = Object.assign(this.renStylesMap[sel] || {}, { display: "none" });
        } else if (op === "show") {
            // "show" estaba documentada en el prompt pero nunca implementada:
            // restaurar el elemento (limpia estilos REN en vivo y persistidos).
            delete this.renStylesMap[sel];
            document.querySelectorAll(sel).forEach(t => {
                t.style.removeProperty("display");
                t.style.removeProperty("height");
                t.style.removeProperty("overflow");
                t.style.removeProperty("pointer-events");
                t.removeAttribute("data-ren-removed");
            });
        } else {
            if (Object.keys(styles).length > 0) {
                // Aplicación inmediata en el DOM + persistencia en el mapa REN.
                document.querySelectorAll(sel).forEach(t => {
                    Object.entries(styles).forEach(([prop, val]) => {
                        const kebabProp = prop.replace(/([A-Z])/g, "-$1").toLowerCase();
                        t.style.setProperty(kebabProp, val, "important");
                    });
                });
            }
            this.renStylesMap[sel] = Object.assign(this.renStylesMap[sel] || {}, styles);
        }

        this.savePersistedRenStyles();
    }

    savePersistedRenStyles() {
        let styleTag = document.getElementById("aethercutRenCustomStyles");
        if (!styleTag) {
            styleTag = document.createElement("style");
            styleTag.id = "aethercutRenCustomStyles";
            document.head.appendChild(styleTag);
        }

        let cssContent = "";
        for (const [selector, rules] of Object.entries(this.renStylesMap)) {
            cssContent += `${selector} {\n`;
            for (const [prop, val] of Object.entries(rules)) {
                const kebabProp = prop.replace(/([A-Z])/g, "-$1").toLowerCase();
                cssContent += `  ${kebabProp}: ${val} !important;\n`;
            }
            cssContent += `}\n`;
        }

        styleTag.textContent = cssContent;
        try {
            localStorage.setItem("aethercut_ren_styles", JSON.stringify(this.renStylesMap));
        } catch (e) {
            console.warn("[Modo REN] No se pudo guardar en localStorage:", e);
        }
    }

    loadPersistedRenStyles() {
        try {
            const saved = localStorage.getItem("aethercut_ren_styles");
            if (saved) {
                this.renStylesMap = JSON.parse(saved);
                this.savePersistedRenStyles();
            }
        } catch (e) {
            console.warn("[Modo REN] Error al cargar estilos persistidos:", e);
        }
    }

    resetRenModifications() {
        this.renStylesMap = {};
        const styleTag = document.getElementById("aethercutRenCustomStyles");
        if (styleTag) styleTag.remove();
        try {
            localStorage.removeItem("aethercut_ren_styles");
        } catch (e) {}
        this.clearRenTarget();
        this.appendBotResponse("🔄 **[Modo REN]** Todos los estilos y elementos personalizados se han restablecido a la versión original de la app.", [], {}, "Modo REN");
    }

    escapeHtml(str) {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    formatMarkdown(text) {
        if (!text) return "";

        // 1. Extraer y estructurar bloques de código estilo Antigravity ```lang ... ```
        const codeBlocks = [];
        let processed = text.replace(/```([a-zA-Z0-9_\-\.]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
            const blockId = "cb_" + Math.random().toString(36).substring(2, 9);
            codeBlocks.push({ id: blockId, lang: (lang || "code").toLowerCase(), code: code.trim() });
            return `__CODEBLOCK_PLACEHOLDER_${blockId}__`;
        });

        // 2. Formato Markdown estándar
        processed = processed
            // Negrita
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            // Cursiva
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            // Enlaces [texto](url)
            .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:#38bdf8; text-decoration:underline;">$1</a>')
            // Código inline
            .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-family:\'Geist Mono\', monospace; font-size:12px; color:#38bdf8;">$1</code>');

        // 3. Reemplazar placeholders de bloques de código por componentes interactivos
        codeBlocks.forEach(b => {
            const lowCode = b.code.toLowerCase();
            const hasBadPlanningWords = lowCode.includes("plan:") || lowCode.includes("edit_file") || lowCode.includes("replace 1:") || lowCode.includes("voy a hacer");
            const isCss = !hasBadPlanningWords && (b.lang === "css" || ((b.code.includes(";") || b.code.includes("background:") || b.code.includes("border:")) && b.code.includes("{")));
            const applyBtnHtml = isCss ? `
                <button type="button" class="agent-code-apply-btn" data-code="${encodeURIComponent(b.code)}" title="Inyectar en pantalla y guardar en matte-dark.css" style="background:linear-gradient(135deg, #10b981, #059669); color:#fff; border:none; padding:3px 10px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; display:inline-flex; align-items:center; gap:4px; box-shadow:0 2px 8px rgba(16,185,129,0.3);">
                    <span>⚡ Aplicar en vivo</span>
                </button>
            ` : "";

            const blockHtml = `
                <div class="agent-code-block-wrap" style="margin:12px 0; border:1px solid rgba(255,255,255,0.12); border-radius:9px; background:#070a12; overflow:hidden; box-shadow:0 6px 20px rgba(0,0,0,0.6);">
                    <div class="agent-code-block-header" style="display:flex; justify-content:space-between; align-items:center; padding:6px 12px; background:rgba(255,255,255,0.04); border-bottom:1px solid rgba(255,255,255,0.08);">
                        <span style="font-size:10px; font-weight:700; text-transform:uppercase; color:#94a3b8; letter-spacing:0.06em; font-family:'Geist Mono', monospace;">${this.escapeHtml(b.lang || 'código')}</span>
                        <div style="display:flex; gap:6px;">
                            ${applyBtnHtml}
                            <button type="button" class="agent-code-copy-btn" data-code="${encodeURIComponent(b.code)}" title="Copiar código al portapapeles" style="background:rgba(255,255,255,0.08); color:#cbd5e1; border:1px solid rgba(255,255,255,0.12); padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600; cursor:pointer;">
                                📋 Copiar
                            </button>
                        </div>
                    </div>
                    <pre style="margin:0; padding:12px; font-family:'Geist Mono', monospace; font-size:12px; line-height:1.55; color:#e2e8f0; overflow-x:auto; background:transparent;"><code>${this.escapeHtml(b.code)}</code></pre>
                </div>
            `;
            processed = processed.replace(`__CODEBLOCK_PLACEHOLDER_${b.id}__`, blockHtml);
        });

        // 4. Párrafos y listas
        const lines = processed.split("\n");
        let result = [];
        let inList = false;

        lines.forEach(line => {
            const trimmed = line.trim();
            if (trimmed.includes("agent-code-block-wrap")) {
                if (inList) { result.push("</ul>"); inList = false; }
                result.push(trimmed);
            } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
                if (!inList) {
                    result.push("<ul style=\"margin:6px 0; padding-left:18px;\">");
                    inList = true;
                }
                result.push(`<li>${trimmed.substring(2)}</li>`);
            } else {
                if (inList) {
                    result.push("</ul>");
                    inList = false;
                }
                if (trimmed) {
                    result.push(`<p style=\"margin:6px 0;\">${trimmed}</p>`);
                }
            }
        });
        if (inList) result.push("</ul>");

        return result.join("");
    }
}
