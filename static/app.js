// static/app.js
// Клиентский скрипт для Trade-Print AI Assistant

let currentActiveChunk = null; // Хранит загруженный чанк для модального окна
let currentSources = []; // Хранит список источников текущего ответа

// Переменные состояния перевода чанка
let originalChunkText = "";
let translatedChunkText = "";
let isTranslated = false;

function formatResponseText(text) {
    if (!text) return "";
    
    // 1. Экранируем HTML
    let escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
        
    // 2. Превращаем [SOURCE X] и [Источник X] в кликабельные HTML-ссылки
    const isRu = (window.TRANSLATIONS && window.TRANSLATIONS.lang_code === "ru");
    const sourcePrefix = isRu ? "Источник" : "Source";
    const sourceTooltip = isRu ? "Посмотреть первоисточник" : "View source";
    escaped = escaped.replace(/\[(?:SOURCE|Источник)\s*(\d+)\]/gi, (match, p1) => {
        return `<a href="#" onclick="openChunkDetailsBySourceIndex(${p1}); return false;" class="text-brand-400 hover:text-brand-300 font-semibold underline decoration-dotted inline-flex items-center gap-0.5" title="${sourceTooltip}">[${sourcePrefix} ${p1}]</a>`;
    });
    
    // 3. Базовый парсинг Markdown:
    // **жирный** -> <strong>жирный</strong>
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    
    // Переносы строк
    escaped = escaped.replace(/\n/g, "<br>");
    
    return escaped;
}

function openChunkDetailsBySourceIndex(idx) {
    const src = currentSources.find(s => s.idx == idx);
    if (src) {
        const isOfficial = src.metadata && src.metadata.source === "official";
        if (window.DIRECT_FORUM_LINKS && !isOfficial && window.IS_BUILD) {
            window.open(src.url, '_blank');
        } else {
            openChunkDetails(src.id);
        }
    } else {
        console.warn("Источник с индексом не найден: ", idx);
    }
}

// Поддержка отправки вопроса при нажатии Enter (без Shift)
document.getElementById("queryInput").addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitQuery();
    }
});

// Отправка запроса к RAG-серверу
async function submitQuery() {
    const queryInput = document.getElementById("queryInput");
    const query = queryInput.value.trim();
    if (!query) return;

    // Блокируем интерфейс
    queryInput.value = "";
    queryInput.disabled = true;
    document.getElementById("askBtn").disabled = true;

    // Сбрасываем старый ответ и подготавливаем блоки
    document.getElementById("welcomeView").classList.add("hidden");
    document.getElementById("answerBlock").classList.remove("hidden");
    document.getElementById("queryText").textContent = query;
    document.getElementById("answerText").textContent = "";
    document.getElementById("thoughtBlock").classList.add("hidden");
    document.getElementById("thoughtText").textContent = "";
    document.getElementById("sourcesBlock").classList.add("hidden");
    document.getElementById("sourcesList").innerHTML = "";
    document.getElementById("debugBlock").classList.add("hidden");
    
    // Сбрасываем отладочные списки
    document.getElementById("ftsDebugList").innerHTML = "";
    document.getElementById("vectorDebugList").innerHTML = "";
    document.getElementById("rerankDebugList").innerHTML = "";
    document.getElementById("ftsCount").textContent = "0";
    document.getElementById("vectorCount").textContent = "0";
    document.getElementById("rerankCount").textContent = "0";

    // Показываем индикатор печати
    document.getElementById("streamIndicator").classList.remove("hidden");

    let fullResponseText = "";

    try {
        const model = document.getElementById("modelSelect").value;
        const searchMode = document.getElementById("searchModeSelect").value;
        const strictMode = document.getElementById("strictModeCheckModal").checked;
        const showReasoning = document.getElementById("showReasoningCheckModal").checked;
        const sourceFilter = document.getElementById("sourceFilterSelect").value;
        const enableContextOptimizer = document.getElementById("contextOptimizerCheckModal").checked;

        const response = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query: query,
                model: model,
                search_mode: searchMode,
                strict_mode: strictMode,
                show_reasoning: showReasoning,
                source_filter: sourceFilter,
                enable_context_optimizer: enableContextOptimizer
            })
        });

        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // Разделяем по двум переносам строки (формат SSE)
            const parts = buffer.split("\n\n");
            buffer = parts.pop(); // Остаток буфера сохраняем

            for (const part of parts) {
                if (!part.trim()) continue;
                
                // Обрабатываем события SSE
                const lines = part.split("\n");
                let event = "message";
                let dataStr = "";
                
                for (const line of lines) {
                    if (line.startsWith("event: ")) {
                        event = line.substring(7).trim();
                    } else if (line.startsWith("data: ")) {
                        dataStr = line.substring(6).trim();
                    }
                }

                if (!dataStr) continue;

                try {
                    const data = JSON.parse(dataStr);
                    
                    if (event === "debug") {
                        // Отрисовка диагностики (показываем, если чекбокс включен)
                        renderDebugInfo(data);
                    } else if (event === "sources") {
                        // Отрисовка источников
                        renderSources(data);
                    } else if (event === "message" || !event) {
                        // Отрисовка текста генерации с фильтрацией мыслей
                        if (data.text) {
                            fullResponseText += data.text;
                            
                            // Парсим теги <thought>
                            const thoughtStartIdx = fullResponseText.indexOf("<thought>");
                            const thoughtEndIdx = fullResponseText.indexOf("</thought>");
                            
                            if (thoughtStartIdx !== -1) {
                                if (thoughtEndIdx !== -1) {
                                    // Мысли завершились
                                    const thought = fullResponseText.substring(thoughtStartIdx + 9, thoughtEndIdx).trim();
                                    const answer = fullResponseText.substring(thoughtEndIdx + 10);
                                    
                                    if (showReasoning && thought) {
                                        document.getElementById("thoughtBlock").classList.remove("hidden");
                                        document.getElementById("thoughtText").textContent = thought;
                                    } else {
                                        document.getElementById("thoughtBlock").classList.add("hidden");
                                    }
                                    document.getElementById("answerText").innerHTML = formatResponseText(answer);
                                } else {
                                    // Мысли в процессе генерации
                                    const thought = fullResponseText.substring(thoughtStartIdx + 9);
                                    if (showReasoning) {
                                        document.getElementById("thoughtBlock").classList.remove("hidden");
                                        document.getElementById("thoughtText").textContent = thought;
                                    }
                                    document.getElementById("answerText").innerHTML = ""; // скрываем ответ, пока думаем
                                }
                            } else {
                                // Обычный ответ без тегов мыслей
                                document.getElementById("thoughtBlock").classList.add("hidden");
                                document.getElementById("answerText").innerHTML = formatResponseText(fullResponseText);
                            }
                        }
                    }
                } catch (e) {
                    console.error("Ошибка парсинга SSE пакета:", e);
                }
            }
        }
    } catch (error) {
        document.getElementById("answerText").innerHTML = `<span class="text-red-400 font-semibold">[!] ${window.TRANSLATIONS.llm_error_prefix || 'Error'}: ${error.message}</span>`;
    } finally {
        // Разблокируем интерфейс
        queryInput.disabled = false;
        document.getElementById("askBtn").disabled = false;
        document.getElementById("streamIndicator").classList.add("hidden");
        queryInput.focus();
        
        // Обновляем список истории в левом сайдбаре
        refreshSidebar();
    }
}

// Отрисовка блоков диагностики
function renderDebugInfo(debugInfo) {
    const showDebug = document.getElementById("debugToggleModal").checked;
    if (showDebug) {
        document.getElementById("debugBlock").classList.remove("hidden");
    }

    const ftsList = document.getElementById("ftsDebugList");
    const vectorList = document.getElementById("vectorDebugList");
    const rerankList = document.getElementById("rerankDebugList");

    document.getElementById("ftsCount").textContent = debugInfo.fts_found.length;
    document.getElementById("vectorCount").textContent = debugInfo.vector_found.length;
    document.getElementById("rerankCount").textContent = debugInfo.reranked.length;

    // Отрисовка статистики оптимизатора контекста
    const optStatsBlock = document.getElementById("optimizerStatsBlock");
    if (optStatsBlock) {
        if (debugInfo.context_optimization) {
            optStatsBlock.classList.remove("hidden");
            document.getElementById("optDocsBefore").textContent = debugInfo.context_optimization.docs_before;
            document.getElementById("optDocsAfter").textContent = debugInfo.context_optimization.docs_after;
            document.getElementById("optWordsBefore").textContent = debugInfo.context_optimization.words_before;
            document.getElementById("optWordsAfter").textContent = debugInfo.context_optimization.words_after;
            document.getElementById("optSavedPct").textContent = debugInfo.context_optimization.saved_pct;
        } else {
            optStatsBlock.classList.add("hidden");
        }
    }

    // FTS
    debugInfo.fts_found.forEach(item => {
        const modelLabel = item.model ? `[${item.model}] ` : "";
        ftsList.innerHTML += `
            <div class="p-2 rounded bg-[#162238] border border-gray-800 hover:border-gray-700 transition-colors cursor-pointer" onclick="openChunkDetails('${item.id}')">
                <div class="font-medium truncate text-gray-300">${modelLabel}${item.title}</div>
                <div class="text-[10px] text-gray-500 flex justify-between mt-1">
                    <span>ID: ${item.id}</span>
                    <span class="text-blue-400 font-semibold">score: ${item.score}</span>
                </div>
            </div>
        `;
    });

    // Vector
    debugInfo.vector_found.forEach(item => {
        const modelLabel = item.model ? `[${item.model}] ` : "";
        vectorList.innerHTML += `
            <div class="p-2 rounded bg-[#162238] border border-gray-800 hover:border-gray-700 transition-colors cursor-pointer" onclick="openChunkDetails('${item.id}')">
                <div class="font-medium truncate text-gray-300">${modelLabel}${item.title}</div>
                <div class="text-[10px] text-gray-500 flex justify-between mt-1">
                    <span>ID: ${item.id}</span>
                    <span class="text-purple-400 font-semibold">score: ${item.score}</span>
                </div>
            </div>
        `;
    });

    // Reranked
    debugInfo.reranked.forEach((item, index) => {
        const modelLabel = item.model ? `[${item.model}] ` : "";
        rerankList.innerHTML += `
            <div class="p-2 rounded bg-[#162238] border border-gray-800 hover:border-gray-700 transition-colors cursor-pointer" onclick="openChunkDetails('${item.id}')">
                <div class="font-medium truncate text-gray-300">${index + 1}. ${modelLabel}${item.title}</div>
                <div class="text-[10px] text-gray-500 flex justify-between mt-1">
                    <span>ID: ${item.id}</span>
                    <span class="text-green-400 font-semibold">score: ${item.score}</span>
                </div>
            </div>
        `;
    });
}

// Отрисовка источников под ответом
function renderSources(sources) {
    if (!sources || sources.length === 0) return;
    currentSources = sources;
    
    document.getElementById("sourcesBlock").classList.remove("hidden");
    const container = document.getElementById("sourcesList");
    
    sources.forEach(src => {
        const isOfficial = src.source === "official";
        const authors = src.authors.length > 0 ? src.authors.join(", ") : "forum";
        const posts = src.posts.length > 0 ? `${window.TRANSLATIONS.posts_label || 'Posts'}: ${src.posts.join(", ")}` : "";
        
        const badge = isOfficial 
            ? '<span class="text-[9px] text-blue-400 font-bold bg-blue-500/10 px-1.5 py-0.5 rounded uppercase tracking-wider">Official</span>' 
            : '<span class="text-[9px] text-yellow-500 font-bold bg-yellow-500/10 px-1.5 py-0.5 rounded uppercase tracking-wider">Forum</span>';
            
        const detailText = isOfficial 
            ? `<span class="truncate text-blue-300">PDF: ${src.document || src.title}</span>`
            : `<span class="truncate">${window.TRANSLATIONS.author_prefix || 'Author'}: ${authors}</span>`;
            
        const extraText = isOfficial 
            ? `<span class="text-blue-300 font-semibold">${window.TRANSLATIONS.page_prefix || 'Page'} ${src.page || 1}</span>`
            : `<span>${posts}</span>`;
            
        const modelLabel = src.model ? `[${src.model}] ` : "";
        const useDirect = (window.DIRECT_FORUM_LINKS && !isOfficial && window.IS_BUILD);
        const clickHandler = useDirect ? `window.open('${src.url}', '_blank')` : `openChunkDetails('${src.id}')`;
        container.innerHTML += `
            <div onclick="${clickHandler}" class="p-3 rounded-xl bg-[#142036] border border-[#1e293b] hover:border-brand-500/50 hover:bg-[#1b2b47] transition-all cursor-pointer flex flex-col gap-1.5 shadow-md">
                <div class="flex items-start justify-between gap-2">
                    <span class="text-sm font-semibold text-white line-clamp-1 group-hover:text-brand-400 flex items-center gap-1.5">
                        ${badge} [${src.idx}] ${modelLabel}${src.title}
                    </span>
                    <span class="text-[10px] text-green-400 font-bold bg-green-500/10 px-1.5 py-0.5 rounded">
                        ${src.score}
                    </span>
                </div>
                <div class="text-[10px] text-gray-300 flex items-center justify-between">
                    ${detailText}
                    ${extraText}
                </div>
            </div>
        `;
    });
}

// Открытие модального окна просмотра чанка
async function openChunkDetails(chunkId) {
    try {
        const response = await fetch(`/chunk/${chunkId}`);
        if (!response.ok) throw new Error(window.TRANSLATIONS.chunk_load_error || "Failed to load chunk data");
        
        const chunk = await response.json();
        currentActiveChunk = chunk;
        
        // Заполняем поля шапки
        document.getElementById("chunkModalTitle").textContent = chunk.thread_title;
        document.getElementById("chunkModalSubtitle").textContent = `ID: ${chunk.id} | Индекс чанка: ${chunk.chunk_index}`;
        
        // Заполняем вкладку Текст
        originalChunkText = chunk.text;
        translatedChunkText = "";
        isTranslated = false;
        document.getElementById("content-text").textContent = originalChunkText;
        updateTranslateButtonState();
        
        // Заполняем вкладку JSON
        document.getElementById("content-json").textContent = JSON.stringify(chunk, null, 4);
        
        // Заполняем вкладку HTML (локальная копия во фрейме)
        const iframe = document.getElementById("chunkIframe");
        if (chunk.metadata && chunk.metadata.source === "official") {
            iframe.src = `/archive/official/${chunk.metadata.document}#page=${chunk.metadata.page}`;
        } else {
            const sourcePath = (chunk.metadata && chunk.metadata.source) ? chunk.metadata.source + "/" : "";
            iframe.src = `/archive/${sourcePath}thread_${chunk.thread_id}/page001.html`;
        }
        
        // Ссылка на оригинал
        document.getElementById("chunkOriginalLink").href = chunk.url;
        
        // Показываем модалку
        toggleChunkModal(true);
        // Сбрасываем активную вкладку на "Текст"
        switchChunkTab("text");
        
        // Синхронизируем панель навигации
        updateNavControlsState();
        
    } catch (e) {
        alert(e.message);
    }
}

// Переключение вкладок в модальном окне чанка
function switchChunkTab(tabName) {
    const tabs = ["text", "html", "json"];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-${t}`);
        const cnt = document.getElementById(`content-${t}`);
        
        if (btn) {
            if (t === tabName) {
                btn.classList.add("border-brand-500", "text-brand-400");
                btn.classList.remove("border-transparent", "text-gray-400");
            } else {
                btn.classList.remove("border-brand-500", "text-brand-400");
                btn.classList.add("border-transparent", "text-gray-400");
            }
        }
        
        if (cnt) {
            if (t === tabName) {
                cnt.classList.remove("hidden");
            } else {
                cnt.classList.add("hidden");
            }
        }
    });

    // Управляем видимостью кнопки перевода (показываем только на вкладке Текст)
    const translateBtn = document.getElementById("translateChunkBtn");
    if (translateBtn) {
        if (tabName === "text") {
            translateBtn.classList.remove("hidden");
        } else {
            translateBtn.classList.add("hidden");
        }
    }
}

// Обновление состояния надписи на кнопке перевода
function updateTranslateButtonState() {
    const textSpan = document.getElementById("translateBtnText");
    if (!textSpan) return;
    
    const isRu = (window.TRANSLATIONS && window.TRANSLATIONS.lang_code === "ru");
    
    if (isTranslated) {
        textSpan.textContent = isRu ? "Оригинал" : "Original";
    } else {
        const langName = (window.TRANSLATIONS && window.TRANSLATIONS.lang_name) ? window.TRANSLATIONS.lang_name : "Your Language";
        textSpan.textContent = isRu ? "Перевести" : `Translate to ${langName}`;
    }
}

// Вызов LLM для перевода текста чанка на текущий язык
async function translateActiveChunk() {
    const textDiv = document.getElementById("content-text");
    const textSpan = document.getElementById("translateBtnText");
    const isRu = (window.TRANSLATIONS && window.TRANSLATIONS.lang_code === "ru");

    if (!textDiv || !textSpan) return;

    if (isTranslated) {
        // Возвращаем оригинал
        textDiv.textContent = originalChunkText;
        isTranslated = false;
        updateTranslateButtonState();
        return;
    }

    if (translatedChunkText) {
        // Показываем уже готовый перевод
        textDiv.textContent = translatedChunkText;
        isTranslated = true;
        updateTranslateButtonState();
        return;
    }

    // Запускаем процесс перевода
    textSpan.textContent = isRu ? "Перевод..." : "Translating...";
    const targetLang = (window.TRANSLATIONS && window.TRANSLATIONS.lang_code) ? window.TRANSLATIONS.lang_code : "en";

    try {
        const response = await fetch("/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: originalChunkText,
                target_lang: targetLang
            })
        });

        if (!response.ok) throw new Error("Translation failed");
        
        const data = await response.json();
        translatedChunkText = data.translated;
        textDiv.textContent = translatedChunkText;
        isTranslated = true;
        updateTranslateButtonState();
    } catch (e) {
        alert(e.message);
        updateTranslateButtonState();
    }
}

// Показать/скрыть модалку чанка
function toggleChunkModal(show) {
    const modal = document.getElementById("chunkModal");
    if (show) {
        modal.classList.remove("hidden");
    } else {
        modal.classList.add("hidden");
        document.getElementById("chunkIframe").src = "about:blank"; // Сброс фрейма
    }
}

// Загрузка диалога из бокового сайдбара (История)
function loadHistoryItem(chat) {
    document.getElementById("welcomeView").classList.add("hidden");
    document.getElementById("answerBlock").classList.remove("hidden");
    
    document.getElementById("queryText").textContent = chat.query;
    document.getElementById("answerText").textContent = chat.answer;
    
    // Очищаем и скрываем дебаг (история не хранит логи отладки)
    document.getElementById("debugBlock").classList.add("hidden");
    
    // Рендерим источники
    const sourcesList = document.getElementById("sourcesList");
    sourcesList.innerHTML = "";
    document.getElementById("sourcesBlock").classList.add("hidden");
    
    if (chat.sources && chat.sources.length > 0) {
        renderSources(chat.sources);
    }
}

// Показать/скрыть модалку настроек
function toggleSettingsModal(show) {
    const modal = document.getElementById("settingsModal");
    if (show) {
        modal.classList.remove("hidden");
        if (typeof updateProviderInputs === "function") {
            updateProviderInputs();
        }
        if (typeof updateContextSizeAutoLogic === "function") {
            updateContextSizeAutoLogic();
        }
        if (typeof refreshModelList === "function") {
            refreshModelList();
        }
        // Fetch DB Stats
        fetch("/api/db/stats")
            .then(res => res.json())
            .then(data => {
                const totalEl = document.getElementById("dbStatsTotal");
                const sumEl = document.getElementById("dbStatsSummarized");
                if (totalEl) totalEl.textContent = data.total_chunks;
                if (sumEl) sumEl.textContent = data.summarized_chunks;
            })
            .catch(err => console.error("Error loading DB stats:", err));
    } else {
        modal.classList.add("hidden");
    }
}

// Запрос списка доступных моделей с сервера
async function refreshModelList() {
    const providerSelect = document.getElementById("llmProviderSelect");
    const lmstudioUrl = document.getElementById("lmstudioUrlInput").value.trim();
    const ollamaUrl = document.getElementById("ollamaUrlInput").value.trim();
    const selectEl = document.getElementById("llmModelSelect");
    if (!selectEl) return;
    
    const currentValue = selectEl.value;
    selectEl.innerHTML = "";
    
    // Опция автоопределения
    const autoOption = document.createElement("option");
    autoOption.value = "";
    autoOption.textContent = "Auto Detect / Автоопределение";
    selectEl.appendChild(autoOption);
    
    const provider = providerSelect.value;
    const apiBase = provider === "ollama" ? ollamaUrl : lmstudioUrl;
    
    try {
        const response = await fetch(`/api/models?provider=${provider}&api_base=${encodeURIComponent(apiBase)}`);
        if (response.ok) {
            const data = await response.json();
            if (data.models && data.models.length > 0) {
                data.models.forEach(model => {
                    const option = document.createElement("option");
                    option.value = model;
                    option.textContent = model;
                    if (model === currentValue) {
                        option.selected = true;
                    }
                    selectEl.appendChild(option);
                });
            }
        }
    } catch (err) {
        console.error("Error fetching model list:", err);
    }
}

// Сохранение настроек в API
async function saveSettings(e) {
    e.preventDefault();
    const form = document.getElementById("settingsForm");
    const formData = new FormData(form);
    
    const settings = {};
    formData.forEach((value, key) => {
        settings[key] = value;
    });
    
    // Явно собираем настройки провайдеров (включая readonly поля)
    const provider = document.getElementById("llmProviderSelect").value;
    const lmstudioUrl = document.getElementById("lmstudioUrlInput").value.trim();
    const ollamaUrl = document.getElementById("ollamaUrlInput").value.trim();
    const llmModel = document.getElementById("llmModelSelect").value;
    
    settings["LLM_PROVIDER"] = provider;
    settings["provider"] = provider;
    settings["LM_STUDIO_API_BASE"] = lmstudioUrl;
    settings["OLLAMA_API_BASE"] = ollamaUrl;
    settings["LLM_MODEL"] = llmModel;
    settings["LLM_PROVIDERS"] = {
        "lmstudio": { "url": lmstudioUrl },
        "ollama": { "url": ollamaUrl }
    };
    settings["providers"] = {
        "lmstudio": { "url": lmstudioUrl },
        "ollama": { "url": ollamaUrl }
    };
    
    settings["LAST_DEBUG_MODE"] = document.getElementById("debugToggleModal").checked;
    settings["LAST_SHOW_REASONING"] = document.getElementById("showReasoningCheckModal").checked;
    settings["LAST_STRICT_MODE"] = document.getElementById("strictModeCheckModal").checked;
    settings["LAST_ENABLE_CONTEXT_OPTIMIZER"] = document.getElementById("contextOptimizerCheckModal").checked;
    settings["LAST_DIRECT_FORUM_LINKS"] = document.getElementById("directForumLinksCheckModal").checked;
    settings["LAST_AUTO_CONTEXT_SIZE"] = document.getElementById("autoContextSizeCheck").checked;
    
    const contextModeSelect = form.querySelector("[name='LLM_CONTEXT_MODE']");
    if (contextModeSelect) {
        settings["LAST_CONTEXT_MODE"] = contextModeSelect.value;
        settings["LLM_CONTEXT_MODE"] = contextModeSelect.value;
    }

    try {
        const response = await fetch("/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            toggleSettingsModal(false);
            // Перезагружаем страницу, чтобы применить новые настройки
            window.location.reload();
        } else {
            const data = await response.json();
            alert(`${window.TRANSLATIONS.save_error || 'Save error'}: ${data.detail}`);
        }
    } catch (err) {
        alert(`${window.TRANSLATIONS.network_error || 'Network error'}: ${err.message}`);
    }
}

// Удалить отдельный диалог из истории
async function deleteHistoryItem(event, chatId) {
    event.stopPropagation(); // Предотвращаем клик по самому элементу истории
    if (!confirm(window.TRANSLATIONS.confirm_delete || "Delete this dialog?")) return;
    
    try {
        const response = await fetch(`/history/delete/${chatId}`, { method: "POST" });
        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            alert((window.TRANSLATIONS.delete_error || "Delete error") + ": " + (data.detail || response.statusText));
        }
    } catch (e) {
        alert((window.TRANSLATIONS.delete_error || "Delete error") + ": " + e.message);
    }
}

// Полная очистка истории
async function clearAllHistory(event) {
    if (event) event.stopPropagation();
    if (!confirm(window.TRANSLATIONS.confirm_clear || "Clear all history?")) return;
    
    try {
        const response = await fetch("/history/clear", { method: "POST" });
        if (response.ok) {
            window.location.reload();
        } else {
            const data = await response.json();
            alert((window.TRANSLATIONS.clear_error || "Clear error") + ": " + (data.detail || response.statusText));
        }
    } catch (e) {
        alert((window.TRANSLATIONS.clear_error || "Clear error") + ": " + e.message);
    }
}

// Вспомогательное обновление сайдбара
async function refreshSidebar() {
    // В данном случае мы просто перезагружаем список, чтобы не писать сложный UI-рендер,
    // но для плавного UX мы можем запросить историю через API.
    // Для простоты и надежности, мы перезагрузим страницу ТОЛЬКО если чат успешно завершился.
    // Но так как у нас SPA чат, мы можем динамически дозагрузить историю.
    // Давайте обновим список истории, просто сделав fetch на текущую страницу и вырезав элемент сайдбара.
    try {
        const response = await fetch("/");
        const text = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, "text/html");
        
        const newHistoryList = doc.getElementById("historyList").innerHTML;
        const oldHistoryList = document.getElementById("historyList");
        oldHistoryList.innerHTML = newHistoryList;
        
        // Также обновим видимость кнопки очистки истории в шапке сайдбара
        const clearBtn = document.getElementById("clearHistoryBtn");
        const newClearBtn = doc.getElementById("clearHistoryBtn");
        if (clearBtn && newClearBtn) {
            if (newClearBtn.classList.contains("hidden")) {
                clearBtn.classList.add("hidden");
            } else {
                clearBtn.classList.remove("hidden");
            }
        }
    } catch (e) {
        console.error("Не удалось обновить сайдбар: ", e);
    }
}

// Поддержка автоматического изменения высоты поля ввода при наборе текста
const tx = document.getElementById("queryInput");
if (tx) {
    tx.addEventListener("input", OnInput, false);
}

function OnInput() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
}

// Автоматическое сохранение настроек модели, режима поиска и строгого режима при изменении
async function saveLastSelection(settingsObj) {
    try {
        await fetch("/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settingsObj)
        });
    } catch (e) {
        console.error("Не удалось сохранить выбор настроек: ", e);
    }
}

const modelSelect = document.getElementById("modelSelect");
if (modelSelect) {
    modelSelect.addEventListener("change", function() {
        saveLastSelection({ LAST_MODEL: this.value });
    });
}

const searchModeSelect = document.getElementById("searchModeSelect");
if (searchModeSelect) {
    searchModeSelect.addEventListener("change", function() {
        saveLastSelection({ LAST_SEARCH_MODE: this.value });
    });
}

const sourceFilterSelect = document.getElementById("sourceFilterSelect");
if (sourceFilterSelect) {
    sourceFilterSelect.addEventListener("change", function() {
        saveLastSelection({ LAST_SOURCE_FILTER: this.value });
    });
}



// Единое делегирование кликов для всей истории диалогов
document.addEventListener("click", function(event) {
    // 1. Кнопка удаления конкретного диалога (корзинка)
    const deleteBtn = event.target.closest(".delete-history-btn");
    if (deleteBtn) {
        event.preventDefault();
        event.stopPropagation();
        const chatId = deleteBtn.getAttribute("data-id");
        deleteHistoryItem(event, chatId);
        return;
    }

    // 2. Кнопка "Очистить все" в шапке истории
    const clearBtn = event.target.closest("#clearHistoryBtn");
    if (clearBtn) {
        event.preventDefault();
        event.stopPropagation();
        clearAllHistory(event);
        return;
    }

    // 3. Сама карточка диалога (загрузить диалог)
    const card = event.target.closest(".history-card");
    if (card) {
        event.preventDefault();
        try {
            const chatData = JSON.parse(card.getAttribute("data-chat"));
            loadHistoryItem(chatData);
        } catch (e) {
            console.error("Ошибка парсинга истории:", e);
        }
        return;
    }
});

// Language switcher logic
const langSelectBtn = document.getElementById("langSelectBtn");
const langDropdown = document.getElementById("langDropdown");

if (langSelectBtn && langDropdown) {
    langSelectBtn.addEventListener("click", function(event) {
        event.stopPropagation();
        langDropdown.classList.toggle("hidden");
    });
    
    document.addEventListener("click", function(event) {
        if (!event.target.closest("#langSelectorContainer")) {
            langDropdown.classList.add("hidden");
        }
    });
}

async function changeLanguage(lang) {
    await saveLastSelection({ LAST_LANG: lang });
    window.location.reload();
}

async function toggleContextMode(currentMode, isAuto) {
    let newMode;
    if (currentMode === "quality") {
        newMode = "fast";
    } else if (currentMode === "fast") {
        newMode = "off";
    } else {
        newMode = "quality";
    }
    
    const settingsUpdate = { 
        LLM_CONTEXT_MODE: newMode,
        LAST_CONTEXT_MODE: newMode 
    };
    
    if (isAuto) {
        // Automatically set size: Quality gets 3000, Speed/OFF gets 1000
        const autoVal = (newMode === "quality") ? 3000 : 1000;
        settingsUpdate["MAX_CONTEXT_SIZE_WORDS"] = autoVal;
    }
    
    await saveLastSelection(settingsUpdate);
    window.location.reload();
}

// Навигация и перелистывание чанков в модальном окне
async function navigateChunk(direction) {
    if (!currentActiveChunk) return;
    const chunkId = currentActiveChunk.id;
    try {
        const response = await fetch(`/chunk/navigate/${chunkId}?direction=${direction}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const msg = errorData.detail || "Нет больше страниц или постов в этом документе";
            alert(msg);
            return;
        }
        const newChunk = await response.json();
        updateChunkModalWithNewData(newChunk);
    } catch (e) {
        alert(e.message);
    }
}

async function navigateChunkToPage() {
    if (!currentActiveChunk) return;
    const chunkId = currentActiveChunk.id;
    const pageVal = parseInt(document.getElementById("navPageInput").value);
    if (isNaN(pageVal) || pageVal < 1) {
        alert("Пожалуйста, введите корректный номер");
        return;
    }
    try {
        const response = await fetch(`/chunk/navigate/${chunkId}?direction=page&page=${pageVal}`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const msg = errorData.detail || "Страница или пост не найдены";
            alert(msg);
            return;
        }
        const newChunk = await response.json();
        updateChunkModalWithNewData(newChunk);
    } catch (e) {
        alert(e.message);
    }
}

function updateChunkModalWithNewData(chunk) {
    currentActiveChunk = chunk;
    
    // Обновляем шапку
    document.getElementById("chunkModalTitle").textContent = chunk.thread_title;
    document.getElementById("chunkModalSubtitle").textContent = `ID: ${chunk.id} | Индекс чанка: ${chunk.chunk_index}`;
    
    // Обновляем текст
    originalChunkText = chunk.text;
    translatedChunkText = "";
    isTranslated = false;
    document.getElementById("content-text").textContent = originalChunkText;
    updateTranslateButtonState();
    
    // Обновляем вкладку JSON
    document.getElementById("content-json").textContent = JSON.stringify(chunk, null, 4);
    
    // Обновляем вкладку HTML (локальная копия во фрейме)
    const iframe = document.getElementById("chunkIframe");
    if (chunk.metadata && chunk.metadata.source === "official") {
        iframe.src = `/archive/official/${chunk.metadata.document}#page=${chunk.metadata.page}`;
    } else {
        const sourcePath = (chunk.metadata && chunk.metadata.source) ? chunk.metadata.source + "/" : "";
        iframe.src = `/archive/${sourcePath}thread_${chunk.thread_id}/page001.html`;
    }
    
    // Ссылка на оригинал
    document.getElementById("chunkOriginalLink").href = chunk.url;
    
    // Сбрасываем на вкладку "Текст" при переходе
    switchChunkTab("text");
    
    // Синхронизируем ввод
    updateNavControlsState();
}

function updateNavControlsState() {
    if (!currentActiveChunk) return;
    const isOfficial = currentActiveChunk.metadata && currentActiveChunk.metadata.source === "official";
    const labelSpan = document.getElementById("navLabelPage");
    const pageInput = document.getElementById("navPageInput");
    const totalSpan = document.getElementById("navTotalCount");
    
    const totalCount = currentActiveChunk.total_count || 1;
    const isRu = (window.TRANSLATIONS && window.TRANSLATIONS.lang_code === "ru");
    
    if (totalSpan) {
        totalSpan.innerHTML = `/ <span class="text-white font-semibold">${totalCount}</span>`;
    }
    
    if (isOfficial) {
        labelSpan.textContent = isRu ? "Стр" : "Page";
        pageInput.value = currentActiveChunk.metadata.page || 1;
    } else {
        labelSpan.textContent = isRu ? "Пост" : "Post";
        pageInput.value = currentActiveChunk.chunk_index || 1;
    }
}

// Слушатель нажатия Enter на поле ввода страницы
const navPageInputEl = document.getElementById("navPageInput");
if (navPageInputEl) {
    navPageInputEl.addEventListener("keydown", function(e) {
        if (e.key === "Enter") {
            e.preventDefault();
            navigateChunkToPage();
        }
    });
}
