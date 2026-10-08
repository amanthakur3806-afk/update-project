(function () {
  "use strict";

  var agents = [], selected = null;
  var conversation = "chat_" + Date.now();
  var busy = false, executionStartedAt = 0;
  var currentUser = null;
  var authToken = localStorage.getItem("luna_auth_token") || null;

  var $ = function (name) {
    return document.getElementById(name);
  };

  function authHeaders(extraHeaders) {
    var headers = Object.assign({}, extraHeaders || {});
    if (authToken) {
      headers["Authorization"] = "Bearer " + authToken;
    }
    return headers;
  }

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

  function unwrapJsonIfPresent(text) {
    if (!text) return "";
    var trimmed = String(text).trim();

    var blockMatch = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
    var candidate = blockMatch ? blockMatch[1].trim() : trimmed;

    if ((candidate.startsWith("{") && candidate.endsWith("}")) || (candidate.startsWith("[") && candidate.endsWith("]"))) {
      try {
        var parsed = JSON.parse(candidate);
        if (typeof parsed === "object" && parsed !== null) {
          var commonKeys = ["answer", "response", "message", "content", "summary", "result", "output", "text"];
          for (var i = 0; i < commonKeys.length; i++) {
            var k = commonKeys[i];
            if (typeof parsed[k] === "string" && parsed[k].trim()) {
              return unwrapJsonIfPresent(parsed[k]);
            }
          }
          if (!Array.isArray(parsed)) {
            var lines = [];
            for (var key in parsed) {
              if (Object.prototype.hasOwnProperty.call(parsed, key)) {
                var val = parsed[key];
                var cleanKey = key.replace(/_/g, " ").replace(/\b\w/g, function (l) { return l.toUpperCase(); });
                if (typeof val === "object" && val !== null) {
                  val = JSON.stringify(val);
                }
                lines.push("- **" + cleanKey + "**: " + val);
              }
            }
            return lines.join("\n");
          } else {
            var arrLines = [];
            parsed.forEach(function (item) {
              if (typeof item === "object" && item !== null) {
                var parts = [];
                for (var k in item) {
                  if (Object.prototype.hasOwnProperty.call(item, k)) {
                    var ck = k.replace(/_/g, " ").replace(/\b\w/g, function (l) { return l.toUpperCase(); });
                    parts.push("**" + ck + "**: " + item[k]);
                  }
                }
                arrLines.push("- " + parts.join(", "));
              } else {
                arrLines.push("- " + String(item));
              }
            });
            return arrLines.join("\n");
          }
        }
      } catch (e) {
        // Not JSON
      }
    }
    return text;
  }

  function formatAnswer(value) {
    if (!value) return "";
    value = unwrapJsonIfPresent(value);
    var lines = String(value).split(/\r?\n/);
    var html = [];
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

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

      if (/^\|.*\|$/.test(line) && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1])) {
        var headerCells = line.split("|").slice(1, -1);
        var tableHtml = '<div class="table-wrapper"><table><thead><tr>';
        headerCells.forEach(function (h) {
          tableHtml += '<th>' + inline(h.trim()) + '</th>';
        });
        tableHtml += '</tr></thead><tbody>';

        i += 2;
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

      if (/^####\s+/.test(line)) {
        html.push('<h5>' + inline(line.replace(/^####\s+/, "")) + '</h5>');
      } else if (/^###\s+/.test(line)) {
        html.push('<h4>' + inline(line.replace(/^###\s+/, "")) + '</h4>');
      } else if (/^##\s+/.test(line)) {
        html.push('<h3>' + inline(line.replace(/^##\s+/, "")) + '</h3>');
      } else if (/^#\s+/.test(line)) {
        html.push('<h2>' + inline(line.replace(/^#\s+/, "")) + '</h2>');
      } else if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
        html.push('<hr class="content-divider">');
      } else if (/^\s*[-*]\s+/.test(line)) {
        var listItems = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          listItems.push('<li>' + inline(lines[i].replace(/^\s*[-*]\s+/, "")) + '</li>');
          i++;
        }
        html.push('<ul class="rich-list">' + listItems.join("") + '</ul>');
        continue;
      } else if (/^\s*\d+\.\s+/.test(line)) {
        var numItems = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          numItems.push('<li>' + inline(lines[i].replace(/^\s*\d+\.\s+/, "")) + '</li>');
          i++;
        }
        html.push('<ol class="rich-list">' + numItems.join("") + '</ol>');
        continue;
      } else if (line.trim() === "") {
        html.push('<div class="spacer"></div>');
      } else {
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
    "luna": [
      "Give me a full dossier for ABC including ARR, SLA, and open tasks.",
      "Analyze churn risk for XYZ and verify war-room SLA escalation policy.",
      "Show operations health and open tasks for NOVA.",
      "List all customers and their current statuses.",
      "What are the multi-year volume discount guidelines for a 3-year contract?"
    ],
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

    var suggestions = SUGGESTIONS_MAP[a.agent_id] || SUGGESTIONS_MAP["luna"] || [
      "Hello! What can you help me with?",
      "List available tools and capabilities."
    ];

    html += '<div class="quick-prompts-label">Quick Prompts:</div><div class="quick-prompts">';
    suggestions.forEach(function (prompt) {
      html += '<button type="button" class="prompt-chip" title="' + esc(prompt) + '">' + esc(prompt) + '</button>';
    });
    html += '</div>';

    $("agentDetails").innerHTML = html;

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

  // --- Auth & User State Management ---

  function showNotice(msg, isError) {
    var notice = $("authNotice");
    if (!notice) return;
    if (!msg) {
      notice.hidden = true;
      notice.textContent = "";
      return;
    }
    notice.hidden = false;
    notice.className = "auth-notice " + (isError ? "error" : "success");
    notice.innerHTML = (isError ? "<strong>[Error]</strong> " : "<strong>[OK]</strong> ") + esc(msg);
  }

  function renderUserMenu() {
    var container = $("userMenuContainer");
    if (!container) return;

    if (currentUser) {
      var initials = (currentUser.full_name || currentUser.username || "U")
        .split(" ")
        .map(function (n) { return n[0]; })
        .join("")
        .substring(0, 2)
        .toUpperCase();

      container.innerHTML =
        '<div class="user-badge" id="userProfileBtn" title="' + esc(currentUser.full_name) + ' (' + esc(currentUser.role || 'Member') + ')">' +
          '<div class="user-avatar">' + esc(initials) + '</div>' +
          '<div class="user-info">' +
            '<span class="user-name">' + esc(currentUser.full_name || currentUser.username) + '</span>' +
            '<span class="user-role">' + esc(currentUser.role || 'Enterprise User') + '</span>' +
          '</div>' +
          '<button class="user-action-btn" id="switchUserBtn" type="button" title="Switch Account">Switch</button>' +
          '<button class="user-action-btn" id="logoutBtn" type="button" title="Sign Out">Sign Out</button>' +
        '</div>';

      var logoutBtn = $("logoutBtn");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          logout();
        });
      }

      var switchBtn = $("switchUserBtn");
      if (switchBtn) {
        switchBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          openAuthScreen("demo");
        });
      }

      var profileBtn = $("userProfileBtn");
      if (profileBtn) {
        profileBtn.addEventListener("click", function () {
          openAuthScreen("demo");
        });
      }
    } else {
      container.innerHTML = '<button id="authTriggerBtn" class="auth-cta-btn" type="button">Sign In / Switch Persona</button>';
      var btn = $("authTriggerBtn");
      if (btn) {
        btn.addEventListener("click", function () {
          openAuthScreen("login");
        });
      }
    }

    updateWelcomeBanner();
  }

  function updateWelcomeBanner() {
    var head = $("welcomeHeadline");
    var subhead = $("welcomeSubhead");
    if (!head || !subhead) return;

    if (currentUser) {
      head.textContent = "Welcome back, " + (currentUser.full_name || currentUser.username);
      subhead.textContent = (currentUser.role ? currentUser.role + " (" + (currentUser.department || "Enterprise") + ")" : "Enterprise Account") +
        " · Luna is context-aware of your role and ready to orchestrate tools.";
    } else {
      head.textContent = "Ask Luna anything";
      subhead.textContent = "Type your prompt below. Luna automatically classifies intent, selects the right MCP tools across Operations, CRM, and Analytics, and streams verified responses.";
    }
  }

  function openAuthScreen(defaultTab) {
    var screen = $("authScreen");
    if (!screen) return;
    screen.hidden = false;

    var closeBtn = $("closeAuthScreenBtn");
    if (closeBtn) {
      closeBtn.hidden = !currentUser; // only show return button if already logged in
    }

    showNotice("", false);
    switchAuthTab(defaultTab || "login");
    loadDemoAccounts();
  }

  function closeAuthScreen() {
    var screen = $("authScreen");
    if (screen) screen.hidden = true;
  }

  function switchAuthTab(tabName) {
    var tabs = document.querySelectorAll(".auth-tab-btn");
    tabs.forEach(function (t) {
      if (t.getAttribute("data-tab") === tabName) {
        t.classList.add("active");
      } else {
        t.classList.remove("active");
      }
    });

    var loginForm = $("loginForm");
    var regForm = $("registerForm");
    var demoContent = $("demoTabContent");

    var title = $("authCardTitle");
    var subtitle = $("authCardSubtitle");

    if (tabName === "login") {
      if (loginForm) loginForm.hidden = false;
      if (regForm) regForm.hidden = true;
      if (demoContent) demoContent.hidden = true;
      if (title) title.textContent = "Sign In to Workspace";
      if (subtitle) subtitle.textContent = "Enter your enterprise credentials to access your isolated sessions.";
    } else if (tabName === "register") {
      if (loginForm) loginForm.hidden = true;
      if (regForm) regForm.hidden = false;
      if (demoContent) demoContent.hidden = true;
      if (title) title.textContent = "Create New Account";
      if (subtitle) subtitle.textContent = "Set up your profile and responsibilities for personalized agent context.";
    } else if (tabName === "demo") {
      if (loginForm) loginForm.hidden = true;
      if (regForm) regForm.hidden = true;
      if (demoContent) demoContent.hidden = false;
      if (title) title.textContent = "1-Click Demo Personas";
      if (subtitle) subtitle.textContent = "Instantly explore Luna with pre-seeded enterprise roles and context.";
    }

    showNotice("", false);
  }

  function setButtonLoading(btn, isLoading, defaultText) {
    if (!btn) return;
    var txt = btn.querySelector(".btn-text");
    var spnr = btn.querySelector(".btn-spinner");
    btn.disabled = isLoading;
    if (isLoading) {
      if (txt) txt.textContent = "Please wait...";
      if (spnr) spnr.hidden = false;
    } else {
      if (txt) txt.textContent = defaultText;
      if (spnr) spnr.hidden = true;
    }
  }

  function fetchCurrentUser() {
    if (!authToken) {
      currentUser = null;
      renderUserMenu();
      loadSessions();
      openAuthScreen("login");
      return Promise.resolve(null);
    }

    return fetch("/auth/me", {
      headers: authHeaders()
    })
      .then(function (r) {
        if (!r.ok) throw Error("Session expired or invalid");
        return r.json();
      })
      .then(function (user) {
        currentUser = user;
        renderUserMenu();
        closeAuthScreen();
        loadSessions();
        return user;
      })
      .catch(function () {
        authToken = null;
        currentUser = null;
        localStorage.removeItem("luna_auth_token");
        renderUserMenu();
        loadSessions();
        openAuthScreen("login");
        return null;
      });
  }

  function login(usernameOrEmail, password) {
    var submitBtn = $("loginSubmitBtn");
    setButtonLoading(submitBtn, true, "Sign In to Workspace");
    showNotice("", false);

    return fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username_or_email: usernameOrEmail,
        password: password
      })
    })
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) {
            throw Error(data.detail || "Invalid username or password.");
          }
          return data;
        });
      })
      .then(function (res) {
        setButtonLoading(submitBtn, false, "Sign In to Workspace");
        authToken = res.access_token;
        localStorage.setItem("luna_auth_token", authToken);
        currentUser = res.user;
        renderUserMenu();
        closeAuthScreen();
        reset();
        loadSessions();
      })
      .catch(function (err) {
        setButtonLoading(submitBtn, false, "Sign In to Workspace");
        showNotice(err.message, true);
      });
  }

  function register(formData) {
    var submitBtn = $("regSubmitBtn");
    setButtonLoading(submitBtn, true, "Create Account & Start Chatting");
    showNotice("", false);

    return fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData)
    })
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) {
            throw Error(data.detail || "Registration failed. Please verify fields.");
          }
          return data;
        });
      })
      .then(function (res) {
        setButtonLoading(submitBtn, false, "Create Account & Start Chatting");
        authToken = res.access_token;
        localStorage.setItem("luna_auth_token", authToken);
        currentUser = res.user;
        renderUserMenu();
        closeAuthScreen();
        reset();
        loadSessions();
      })
      .catch(function (err) {
        setButtonLoading(submitBtn, false, "Create Account & Start Chatting");
        showNotice(err.message, true);
      });
  }

  function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem("luna_auth_token");
    renderUserMenu();
    reset();
    loadSessions();
    openAuthScreen("login");
  }

  function loadDemoAccounts() {
    var grid = $("demoAccountsGrid");
    if (!grid) return;

    grid.innerHTML = '<div style="font-size:12px;color:#94a3b8;padding:8px 0;">Loading enterprise personas...</div>';

    fetch("/auth/demo-accounts")
      .then(function (r) { return r.json(); })
      .then(function (accounts) {
        grid.innerHTML = "";
        accounts.forEach(function (acc) {
          var card = document.createElement("div");
          card.className = "demo-persona-card";
          if (currentUser && currentUser.username === acc.username) {
            card.classList.add("active");
          }

          var initials = (acc.full_name || acc.username)
            .split(" ")
            .map(function (n) { return n[0]; })
            .join("")
            .substring(0, 2)
            .toUpperCase();

          card.innerHTML =
            '<div class="demo-persona-head">' +
              '<div class="demo-persona-user">' +
                '<div class="demo-persona-avatar">' + esc(initials) + '</div>' +
                '<div>' +
                  '<div class="demo-persona-name">' + esc(acc.full_name) + '</div>' +
                  '<div class="demo-persona-email-hint">@' + esc(acc.username) + ' &middot; ' + esc(acc.email) + '</div>' +
                '</div>' +
              '</div>' +
              '<span class="demo-persona-role-badge">' + esc(acc.role) + '</span>' +
            '</div>' +
            '<div class="demo-persona-desc">' + esc(acc.description || acc.responsibilities || '') + '</div>' +
            '<div class="demo-persona-action">' +
              (currentUser && currentUser.username === acc.username ? '\u2713 Active Persona' : 'Sign in as this persona \u2192') +
            '</div>';

          card.addEventListener("click", function () {
            login(acc.username, "LunaDemo2026!");
          });

          grid.appendChild(card);
        });
      })
      .catch(function (err) {
        grid.innerHTML = '<div style="font-size:12px;color:#ef4444;">Failed to load demo accounts.</div>';
      });
  }

  // --- Multi-Chat Sessions Management ---

  function loadSessions() {
    var list = $("sessionsList");
    if (!list) return;

    fetch("/memory/conversations", {
      headers: authHeaders()
    })
      .then(function (r) {
        if (!r.ok) return [];
        return r.json();
      })
      .then(function (convs) {
        renderSessionsList(convs);
      })
      .catch(function (e) {
        console.warn("Could not load conversations:", e);
      });
  }

  function renderSessionsList(convs) {
    var list = $("sessionsList");
    if (!list) return;

    list.innerHTML = "";

    if (!convs || convs.length === 0) {
      list.innerHTML = '<div class="sessions-empty">No conversations yet.<br>Start messaging below!</div>';
      return;
    }

    convs.forEach(function (c) {
      var item = document.createElement("div");
      item.className = "session-item" + (c.conversation_id === conversation ? " active" : "");
      item.dataset.cid = c.conversation_id;

      var turnsBadge = c.turns_count ? '<span class="session-badge">' + c.turns_count + '</span>' : '';

      item.innerHTML =
        '<div class="session-title-wrap">' +
          '<span class="session-icon">#</span>' +
          '<span class="session-title" title="' + esc(c.title || c.conversation_id) + '">' + esc(c.title || "Chat Session") + '</span>' +
        '</div>' +
        '<div class="session-actions">' +
          turnsBadge +
          '<button type="button" class="session-del-btn" title="Delete conversation">&times;</button>' +
        '</div>';

      item.addEventListener("click", function (e) {
        if (e.target.closest(".session-del-btn")) return;
        switchSession(c.conversation_id);
      });

      var delBtn = item.querySelector(".session-del-btn");
      if (delBtn) {
        delBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          deleteSession(c.conversation_id);
        });
      }

      list.appendChild(item);
    });
  }

  function switchSession(newConversationId) {
    conversation = newConversationId;
    resetThoughts();

    var labelEl = $("conversationLabel");
    if (labelEl) labelEl.textContent = "Loading session...";

    var items = document.querySelectorAll(".session-item");
    items.forEach(function (it) {
      if (it.dataset.cid === newConversationId) {
        it.classList.add("active");
      } else {
        it.classList.remove("active");
      }
    });

    fetch("/memory/conversations/" + encodeURIComponent(newConversationId), {
      headers: authHeaders()
    })
      .then(function (r) {
        if (!r.ok) throw Error("Could not load history (" + r.status + ")");
        return r.json();
      })
      .then(function (data) {
        var msgList = $("messageList");
        msgList.innerHTML = "";

        if (data.title) {
          $("conversationLabel").textContent = data.title;
        } else {
          $("conversationLabel").textContent = "Session: " + newConversationId;
        }

        if (data.agent_id && agents && agents.length) {
          var matchedAgent = agents.filter(function (a) { return a.agent_id === data.agent_id; })[0];
          if (matchedAgent && (!selected || selected.agent_id !== data.agent_id)) {
            var s = $("agentSelect");
            if (s) s.value = matchedAgent.agent_id;
            selected = matchedAgent;
            $("chatTitle").textContent = matchedAgent.agent_name;
          }
        }

        if (!data.messages || data.messages.length === 0) {
          msgList.innerHTML =
            '<div class="welcome-card">' +
            '<div class="welcome-icon">L</div>' +
            '<h3 id="welcomeHeadline">Ask Luna anything</h3>' +
            '<p id="welcomeSubhead">This conversation is fresh and ready for your prompts.</p>' +
            '</div>';
          updateWelcomeBanner();
        } else {
          data.messages.forEach(function (m) {
            addMessage(m.role, m.content);
          });
        }
        msgList.scrollTop = msgList.scrollHeight;
      })
      .catch(function (err) {
        console.error("switchSession error:", err);
        var msgList = $("messageList");
        if (msgList) {
          msgList.innerHTML = '<div style="padding:20px;color:#dc2626;text-align:center;">Failed to load conversation: ' + esc(err.message) + '</div>';
        }
      });
  }

  function deleteSession(targetCid) {
    if (!confirm("Are you sure you want to delete this conversation session?")) return;

    fetch("/memory/conversations/" + encodeURIComponent(targetCid), {
      method: "DELETE",
      headers: authHeaders()
    })
      .then(function (r) {
        if (!r.ok) throw Error("Failed to delete session");
        return r.json();
      })
      .then(function () {
        if (conversation === targetCid) {
          reset();
        }
        loadSessions();
      })
      .catch(function (err) {
        alert("Error deleting conversation: " + err.message);
      });
  }

  function load() {
    status("Connecting", false, false);

    fetch("/agents?ts=" + Date.now(), {
      headers: authHeaders()
    })
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

        var lunaAgent = agents.filter(function (a) { return a.agent_id === "luna"; })[0];
        var currentSelectedId = selected ? selected.agent_id : (lunaAgent ? "luna" : (agents[0] ? agents[0].agent_id : null));
        var targetAgent = agents.filter(function (a) { return a.agent_id === currentSelectedId; })[0] || lunaAgent || agents[0] || null;
        
        if (s && targetAgent) {
          s.value = targetAgent.agent_id;
        }

        showAgent(targetAgent);
        status("Connected", true, false);

        return Promise.all([
          fetch("/mcp/servers", { headers: authHeaders() }),
          fetch("/mcp/tools", { headers: authHeaders() })
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

    var authorLabel = role === "user"
      ? (currentUser ? (currentUser.full_name || currentUser.username) : "You")
      : "Luna";

    item.className = "message " + role;
    item.innerHTML =
      '<div class="avatar">' + esc(authorLabel.substring(0, 4)) + '</div>' +
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

    $("conversationLabel").textContent = "New session";

    $("messageList").innerHTML =
      '<div class="welcome-card">' +
      '<div class="welcome-icon">L</div>' +
      '<h3 id="welcomeHeadline">Ask Luna anything</h3>' +
      '<p id="welcomeSubhead">Type your request below. Luna dynamically plans and executes operations, CRM lookups, and analytics with live streaming responses.</p>' +
      '</div>';
    
    updateWelcomeBanner();

    var inp = $("messageInput");
    if (inp) {
      inp.value = "";
      inp.style.height = "auto";
    }

    var items = document.querySelectorAll(".session-item");
    items.forEach(function (it) { it.classList.remove("active"); });
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
        '<div class="avatar">Luna</div>' +
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
      loadSessions();
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
        headers: authHeaders({
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        }),
        body: JSON.stringify({
          query: query,
          conversation_id: conversation,
          user_id: currentUser ? currentUser.user_id : null
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

                if (targetText.length === 0 && finalData.answer) {
                  enqueueDelta(finalData.answer);
                } else if (finalData.answer && finalData.answer.length > targetText.length) {
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
    
    var sideNewBtn = $("sidebarNewChatBtn");
    if (sideNewBtn) {
      sideNewBtn.addEventListener("click", reset);
    }

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

      textarea.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
      });
    }

    // Modal Close Button
    var closeBtn = $("closeAuthScreenBtn");
    if (closeBtn) {
      closeBtn.addEventListener("click", closeAuthScreen);
    }

    // Tab buttons
    var tabs = document.querySelectorAll(".auth-tab-btn");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        switchAuthTab(this.getAttribute("data-tab"));
      });
    });

    // Sub links
    var linkReg = $("linkToRegister");
    if (linkReg) {
      linkReg.addEventListener("click", function (e) {
        e.preventDefault();
        switchAuthTab("register");
      });
    }
    var linkDemo = $("linkToDemo");
    if (linkDemo) {
      linkDemo.addEventListener("click", function (e) {
        e.preventDefault();
        switchAuthTab("demo");
      });
    }
    var linkLog = $("linkToLogin");
    if (linkLog) {
      linkLog.addEventListener("click", function (e) {
        e.preventDefault();
        switchAuthTab("login");
      });
    }

    // Guest Continue Button
    var guestBtn = $("guestContinueBtn");
    if (guestBtn) {
      guestBtn.addEventListener("click", function () {
        closeAuthScreen();
      });
    }

    // Login Form Submit
    var loginForm = $("loginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var id = $("loginId").value.trim();
        var pwd = $("loginPassword").value;
        if (!id || !pwd) {
          showNotice("Please enter your username/email and password.", true);
          return;
        }
        login(id, pwd);
      });
    }

    // Register Form Submit
    var regForm = $("registerForm");
    if (regForm) {
      regForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var fullName = $("regFullName").value.trim();
        var username = $("regUsername").value.trim();
        var email = $("regEmail").value.trim();
        var password = $("regPassword").value;
        var role = $("regRole").value.trim() || null;
        var department = $("regDepartment").value.trim() || null;
        var responsibilities = $("regResponsibilities").value.trim() || null;

        if (!fullName || !username || !email || !password) {
          showNotice("Please fill in all required fields marked with *.", true);
          return;
        }

        if (password.length < 6) {
          showNotice("Password must be at least 6 characters long.", true);
          return;
        }

        var formData = {
          full_name: fullName,
          username: username,
          email: email,
          password: password,
          role: role,
          department: department,
          responsibilities: responsibilities
        };

        register(formData);
      });
    }

    // Initialize state
    fetchCurrentUser().then(function () {
      load();
    });

    setInterval(load, 30000);
  });
}());