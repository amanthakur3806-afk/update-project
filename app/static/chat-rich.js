(function () {
  "use strict";

  var agents = [], selected = null;
  var conversation = "chat_" + Date.now();
  var busy = false, executionStartedAt = 0;

  var $ = function (name) {
    return document.getElementById(name);
  };

  function esc(value) {
    return String(value == null ? "" : value).replace(
      /[&<>"']/g,
      function (c) {
        return {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }[c];
      }
    );
  }

  function inline(value) {
    return esc(value)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+?)`/g, '<code class="inline-code">$1</code>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }

  function formatAnswer(value) {
    if (!value) return "";
    var lines = String(value).split(/\r?\n/);
    var html = [];
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      // Code Block
      if (/^```/.test(line)) {
        var lang = line.replace(/^```/, "").trim() || "code";
        var codeLines = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) {
          codeLines.push(lines[i]);
          i++;
        }
        var codeText = codeLines.join("\n");
        html.push(
          '<div class="code-card">' +
            '<div class="code-header"><span>' + esc(lang) + '</span><button type="button" class="copy-code-btn" onclick="navigator.clipboard.writeText(this.closest(\'.code-card\').querySelector(\'code\').innerText)">Copy</button></div>' +
            '<pre><code>' + esc(codeText) + '</code></pre>' +
          '</div>'
        );
        i++;
        continue;
      }

      // Markdown Table
      if (/^\|.*\|$/.test(line) && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1])) {
        var headerCells = line.split("|").slice(1, -1);
        var tableHtml = '<div class="table-wrapper"><table><thead><tr>';
        headerCells.forEach(function (h) {
          tableHtml += '<th>' + inline(h.trim()) + '</th>';
        });
        tableHtml += '</tr></thead><tbody>';

        i += 2; // skip header and separator
        while (i < lines.length && /^\|.*\|$/.test(lines[i])) {
          var rowCells = lines[i].split("|").slice(1, -1);
          tableHtml += '<tr>';
          rowCells.forEach(function (c) {
            tableHtml += '<td>' + inline(c.trim()) + '</td>';
          });
          tableHtml += '</tr>';
          i++;
        }
        tableHtml += '</tbody></table></div>';
        html.push(tableHtml);
        continue;
      }

      // Blockquote
      if (/^>\s+/.test(line)) {
        var quoteLines = [line.replace(/^>\s+/, "")];
        i++;
        while (i < lines.length && /^>\s+/.test(lines[i])) {
          quoteLines.push(lines[i].replace(/^>\s+/, ""));
          i++;
        }
        html.push('<blockquote class="callout">' + quoteLines.map(inline).join("<br>") + '</blockquote>');
        continue;
      }

      // Headers
      if (/^####\s+/.test(line)) {
        html.push('<h5>' + inline(line.replace(/^####\s+/, "")) + '</h5>');
      } else if (/^###\s+/.test(line)) {
        html.push('<h4>' + inline(line.replace(/^###\s+/, "")) + '</h4>');
      } else if (/^##\s+/.test(line)) {
        html.push('<h3>' + inline(line.replace(/^##\s+/, "")) + '</h3>');
      } else if (/^#\s+/.test(line)) {
        html.push('<h2>' + inline(line.replace(/^#\s+/, "")) + '</h2>');
      }
      // Horizontal Rule
      else if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
        html.push('<hr class="content-divider">');
      }
      // Unordered Lists
      else if (/^\s*[-*]\s+/.test(line)) {
        var listItems = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          listItems.push('<li>' + inline(lines[i].replace(/^\s*[-*]\s+/, "")) + '</li>');
          i++;
        }
        html.push('<ul class="rich-list">' + listItems.join("") + '</ul>');
        continue;
      }
      // Ordered Lists
      else if (/^\s*\d+\.\s+/.test(line)) {
        var numItems = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          numItems.push('<li>' + inline(lines[i].replace(/^\s*\d+\.\s+/, "")) + '</li>');
          i++;
        }
        html.push('<ol class="rich-list">' + numItems.join("") + '</ol>');
        continue;
      }
      // Empty Line
      else if (line.trim() === "") {
        html.push('<div class="spacer"></div>');
      }
      // Regular Paragraph
      else {
        html.push('<p>' + inline(line) + '</p>');
      }

      i++;
    }

    return html.join("");
  }

  function status(text, connected, error) {
    var e = $("connectionStatus");
    if (!e) return;
    e.textContent = "";

    var d = document.createElement("i");
    e.appendChild(d);
    e.appendChild(document.createTextNode(" " + text));

    e.className =
      "status-pill" +
      (connected ? " connected" : "") +
      (error ? " error" : "");
  }

  function enable(on) {
    var inp = $("messageInput");
    var btn = $("sendButton");
    if (inp) inp.disabled = !on;
    if (btn) btn.disabled = !on;
    if (on && inp) inp.focus();
  }

  var SUGGESTIONS_MAP = {
    "customer_operations_agent": [
      "List all customers.",
      "Get operations details and tasks for NOVA.",
      "Add note 'Completed annual HIPAA audit review' to NOVA.",
      "Create follow-up task 'Deploy eBPF latency patch' for customer XYZ.",
      "Change QUANTUM status to active.",
      "Show audit history for ABC."
    ],
    "customer_research_agent": [
      "Generate comprehensive dossier for customer ABC including architecture and SLA.",
      "Compare customer ABC and XYZ in terms of architecture, ARR, and SLA.",
      "What is the clinical data compliance setup and TAM contact for NOVA?",
      "Summarize Acme Industrial Automation (ACME) IoT plant telemetry infrastructure.",
      "What are the upcoming renewal risks and Black Friday requirements for QUANTUM?"
    ],
    "financial_analyst_agent": [
      "Analyze ARR, MRR, and churn risk across XYZ and QUANTUM.",
      "Audit health metrics, NPS scores, and monthly API telemetry for all accounts.",
      "What are the multi-year volume discount guidelines for a 3-year contract?",
      "Compare financial metrics between NOVA ($620k ARR) and ABC ($480k ARR)."
    ],
    "support_compliance_agent": [
      "Verify SLA response compliance and war-room protocol for Tier 1 customer XYZ.",
      "What are the Sev-1 escalation guidelines and response windows across Platinum vs Gold tiers?",
      "Review HIPAA compliance, BAA status, and data retention policies for NOVA.",
      "What is our disaster recovery RPO/RTO target for Tier 1 Platinum accounts?"
    ]
  };

  function showAgent(a) {
    selected = a;

    if (!a) {
      $("agentDetails").innerHTML = "<p>No enabled agents are available.</p>";
      enable(false);
      return;
    }

    $("chatTitle").textContent = a.agent_name;

    var categoryClass = (a.category || "General").toLowerCase();
    var toolCount = (a.allowed_tools || []).length;

    var html =
      '<h3>' + esc(a.agent_name) + '</h3>' +
      '<p>' + esc(a.description || "Ready for conversation.") + '</p>' +
      '<div class="agent-badges">' +
      '<span class="agent-tag active cat-' + esc(categoryClass) + '">' + esc(a.category || "General") + '</span>' +
      '<span class="agent-tag">' + toolCount + ' tools</span>' +
      '<span class="agent-tag model-tag">' + esc(a.model || "gpt-4o-mini") + '</span>' +
      '</div>';

    // Suggestion Chips
    var suggestions = SUGGESTIONS_MAP[a.agent_id] || [
      "Hello! What can you help me with?",
      "List available tools and capabilities."
    ];

    html += '<div class="quick-prompts-label">Quick Prompts:</div><div class="quick-prompts">';
    suggestions.forEach(function (prompt) {
      html += '<button type="button" class="prompt-chip" title="' + esc(prompt) + '">' + esc(prompt) + '</button>';
    });
    html += '</div>';

    $("agentDetails").innerHTML = html;

    // Attach click handlers to prompt chips
    var chips = $("agentDetails").querySelectorAll(".prompt-chip");
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var inp = $("messageInput");
        if (inp && !busy) {
          inp.value = this.getAttribute("title") || this.textContent;
          $("chatForm").dispatchEvent(new Event("submit", { cancelable: true }));
        }
      });
    });

    enable(true);
  }

  function load() {
    status("Connecting", false, false);

    fetch("/agents?ts=" + Date.now())
      .then(function (r) {
        if (!r.ok) throw Error("Agent API returned " + r.status);
        return r.json();
      })
      .then(function (data) {
        agents = data.filter(function (a) {
          return a.enabled !== false;
        });

        $("agentCount").textContent = agents.length;

        var s = $("agentSelect");
        s.innerHTML = "";

        agents.forEach(function (a) {
          var o = document.createElement("option");
          o.value = a.agent_id;
          o.textContent = a.agent_name + " (" + (a.category || "General") + ")";
          s.appendChild(o);
        });

        var currentSelectedId = selected ? selected.agent_id : (agents[0] ? agents[0].agent_id : null);
        var targetAgent = agents.filter(function (a) { return a.agent_id === currentSelectedId; })[0] || agents[0] || null;
        
        if (s && targetAgent) {
          s.value = targetAgent.agent_id;
        }

        showAgent(targetAgent);
        status("Connected", true, false);

        return Promise.all([
          fetch("/mcp/servers"),
          fetch("/mcp/tools")
        ]);
      })
      .then(function (rs) {
        return Promise.all(
          rs.map(function (r) {
            return r.ok ? r.json() : [];
          })
        );
      })
      .then(function (data) {
        $("mcpCount").textContent = data[0].length;
        $("toolCount").textContent = data[1].length;
      })
      .catch(function (e) {
        console.error(e);
        status("Backend unavailable", false, true);
        enable(false);
      });
  }

  function addMessage(role, text, meta) {
    var list = $("messageList");
    var welcome = list.querySelector(".welcome-card");
    if (welcome) welcome.remove();

    var item = document.createElement("article");
    var tools = meta && meta.tools_used && meta.tools_used.length
      ? '<span class="tool-pill">' + meta.tools_used.length + ' tool(s) used</span> '
      : "";

    var duration = meta && meta.duration_ms
      ? '<span class="duration-pill">' + (meta.duration_ms / 1000).toFixed(2) + 's</span> '
      : "";

    item.className = "message " + role;
    item.innerHTML =
      '<div class="avatar">' + (role === "user" ? "You" : "AI") + '</div>' +
      '<div class="bubble-wrap">' +
        '<div class="bubble">' + (role === "assistant" ? formatAnswer(text) : esc(text)) + '</div>' +
        '<div class="message-meta">' +
          (role === "assistant" ? tools + duration : "") +
          '<time>' + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + '</time>' +
        '</div>' +
      '</div>';

    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
  }

  function thought(text, phase) {
    $("thoughtPanel").hidden = false;
    var row = document.createElement("div");
    var elapsed = executionStartedAt
      ? ((Date.now() - executionStartedAt) / 1000).toFixed(1) + "s"
      : "0.0s";

    row.className = "thought-event";
    row.innerHTML =
      '<span class="pulse"></span>' +
      '<span class="phase-tag phase-' + esc(phase || "activity") + '">' + esc(phase || "activity") + '</span>' +
      '<b>' + esc(text) + '</b>' +
      '<time>' + esc(elapsed) + '</time>';

    var tList = $("thoughtList");
    tList.appendChild(row);
    tList.scrollTop = tList.scrollHeight;
  }

  function toggleThoughts() {
    var panel = $("thoughtPanel");
    var button = $("thoughtToggle");
    var minimized = panel.classList.toggle("minimized");

    button.textContent = minimized ? "Expand" : "Minimize";
    button.setAttribute("aria-expanded", String(!minimized));
  }

  function resetThoughts() {
    $("thoughtList").innerHTML = "";
    $("thoughtPanel").hidden = true;
    executionStartedAt = 0;
  }

  function reset() {
    conversation = "chat_" + Date.now();
    resetThoughts();

    $("messageList").innerHTML =
      '<div class="welcome-card">' +
      '<div class="welcome-icon">✦</div>' +
      '<h3>Ask your agent anything</h3>' +
      '<p>Select an agent on the left, then send a message. The agent will plan and execute tools with live streaming responses.</p>' +
      '</div>';
    
    var inp = $("messageInput");
    if (inp) {
      inp.value = "";
      inp.style.height = "auto";
    }
  }

  function send(e) {
    if (e) e.preventDefault();
    if (busy || !selected) return;

    var input = $("messageInput");
    var query = input.value.trim();
    if (!query) return;

    addMessage("user", query);
    input.value = "";
    input.style.height = "auto";

    busy = true;
    executionStartedAt = Date.now();
    enable(false);

    $("thoughtList").innerHTML = "";
    $("thoughtPanel").hidden = false;

    var typing = $("typingIndicator");
    if (typing) typing.hidden = false;

    var streamingItem = null;
    var streamingBubble = null;
    var targetText = "";
    var displayedLength = 0;
    var typewriterTimer = null;
    var networkComplete = false;
    var finalData = null;
    var streamError = null;

    function ensureStreamingBubble() {
      if (streamingBubble) return;
      var list = $("messageList");
      var welcome = list.querySelector(".welcome-card");
      if (welcome) welcome.remove();

      streamingItem = document.createElement("article");
      streamingItem.className = "message assistant streaming";
      streamingItem.innerHTML =
        '<div class="avatar">AI</div>' +
        '<div class="bubble-wrap">' +
          '<div class="bubble"><span class="typing-cursor"></span></div>' +
          '<div class="message-meta"><time>' + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + '</time></div>' +
        '</div>';

      list.appendChild(streamingItem);
      streamingBubble = streamingItem.querySelector(".bubble");
      list.scrollTop = list.scrollHeight;
    }

    function finalizeStreaming() {
      if (typewriterTimer) {
        clearTimeout(typewriterTimer);
        typewriterTimer = null;
      }
      if (typing) typing.hidden = true;

      var finalAnswer = (finalData && finalData.answer) ? finalData.answer : targetText;
      if (streamingBubble) {
        streamingBubble.innerHTML = formatAnswer(finalAnswer);
        if (streamError) {
          streamingBubble.innerHTML += '<p class="stream-error"><em>' + esc(streamError) + '</em></p>';
        }
        if (streamingItem) {
          streamingItem.classList.remove("streaming");
          var metaEl = streamingItem.querySelector(".message-meta");
          if (metaEl && finalData) {
            var toolsStr = finalData.tools_used && finalData.tools_used.length
              ? '<span class="tool-pill">' + finalData.tools_used.length + ' tool(s) used</span> '
              : "";
            var durationStr = finalData.duration_ms
              ? '<span class="duration-pill">' + (finalData.duration_ms / 1000).toFixed(2) + 's</span> '
              : "";
            metaEl.innerHTML = toolsStr + durationStr + '<time>' + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + '</time>';
          }
        }
      } else if (finalData && finalData.answer) {
        addMessage("assistant", finalData.answer, finalData);
      }

      var list = $("messageList");
      if (list) list.scrollTop = list.scrollHeight;

      busy = false;
      enable(true);
    }

    function tickTypewriter() {
      if (!streamingBubble) {
        if (networkComplete) {
          finalizeStreaming();
        }
        return;
      }

      var diff = targetText.length - displayedLength;
      if (diff <= 0) {
        if (networkComplete) {
          finalizeStreaming();
          return;
        }
        typewriterTimer = setTimeout(tickTypewriter, 30);
        return;
      }

      // Smooth adaptive speed curve:
      // Small buffer (1-20 chars): 1 char every 18ms (natural human/AI typing cadence)
      // Medium buffer (20-60 chars): 2-3 chars every 15ms (smooth brisk flow)
      // Large buffer (60-150 chars): 4-8 chars every 12ms (fast catch-up)
      // Massive buffer (150+ chars): 12-20 chars every 8ms (instantaneous catch-up)
      var charsToAdvance = 1;
      var delay = 18;

      if (diff > 150) {
        charsToAdvance = Math.min(diff, 16);
        delay = 8;
      } else if (diff > 80) {
        charsToAdvance = Math.min(diff, 6);
        delay = 12;
      } else if (diff > 30) {
        charsToAdvance = Math.min(diff, 3);
        delay = 15;
      } else {
        charsToAdvance = 1;
        delay = 18;
      }

      displayedLength += charsToAdvance;
      var currentSlice = targetText.substring(0, displayedLength);

      streamingBubble.innerHTML = formatAnswer(currentSlice) + '<span class="typing-cursor"></span>';
      
      var list = $("messageList");
      if (list) list.scrollTop = list.scrollHeight;

      typewriterTimer = setTimeout(tickTypewriter, delay);
    }

    function enqueueDelta(delta) {
      if (!delta) return;
      ensureStreamingBubble();
      targetText += delta;
      if (!typewriterTimer) {
        tickTypewriter();
      }
    }

    fetch(
      "/agents/" + encodeURIComponent(selected.agent_id) + "/stream",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        },
        body: JSON.stringify({
          query: query,
          conversation_id: conversation
        })
      }
    )
      .then(function (r) {
        if (!r.ok) {
          throw Error("Agent request failed: HTTP " + r.status);
        }

        var reader = r.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function read() {
          return reader.read().then(function (part) {
            if (part.done) {
              if (typing) typing.hidden = true;
              networkComplete = true;
              if (!typewriterTimer) {
                finalizeStreaming();
              }
              return;
            }

            buffer += decoder.decode(part.value, { stream: true });
            var blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop();

            blocks.forEach(function (block) {
              var line = block.split(/\r?\n/).filter(function (x) {
                return x.indexOf("data: ") === 0;
              })[0];

              if (!line) return;
              var d;
              try {
                d = JSON.parse(line.substring(6));
              } catch (err) {
                return;
              }

              if (d.type === "progress") {
                thought(d.message, d.phase);
              } else if (d.type === "token") {
                if (typing) typing.hidden = true;
                enqueueDelta(d.delta || "");
              } else if (d.type === "complete") {
                finalData = d;
                if (typing) typing.hidden = true;
                networkComplete = true;

                // If no tokens were streamed at all (or if targetText is empty), enqueue full answer
                if (targetText.length === 0 && finalData.answer) {
                  enqueueDelta(finalData.answer);
                } else if (finalData.answer && finalData.answer.length > targetText.length) {
                  // Catch up with any tail difference
                  targetText = finalData.answer;
                }

                if (!typewriterTimer) {
                  tickTypewriter();
                }
              } else if (d.type === "error") {
                throw Error(d.message);
              }
            });

            return read();
          });
        }

        return read();
      })
      .catch(function (err) {
        if (typing) typing.hidden = true;
        streamError = err.message;
        networkComplete = true;
        if (!streamingBubble) {
          addMessage("assistant", "I could not complete that request: " + err.message);
          busy = false;
          enable(true);
        } else {
          finalizeStreaming();
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("agentSelect").addEventListener("change", function () {
      var agentId = this.value;
      var found = agents.filter(function (a) { return a.agent_id === agentId; })[0] || null;
      showAgent(found);
      reset();
    });

    $("refreshButton").addEventListener("click", load);
    $("newChatButton").addEventListener("click", reset);
    $("thoughtToggle").addEventListener("click", toggleThoughts);
    $("chatForm").addEventListener("submit", send);

    var textarea = $("messageInput");
    if (textarea) {
      textarea.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          send(e);
        }
      });

      // Auto-growing textarea
      textarea.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
      });
    }

    load();
    setInterval(load, 30000);
  });
}());