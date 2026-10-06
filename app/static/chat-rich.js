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

  function formatAnswer(value) {
    var lines = String(value || "").split(/\r?\n/);
    var html = [], i = 0;

    while (i < lines.length) {
      var line = lines[i];

      if (
        /^\|.*\|$/.test(line) &&
        i + 1 < lines.length &&
        /^\|?\s*:?-{3,}/.test(lines[i + 1])
      ) {
        var rows = [];
        var header = line.split("|").slice(1, -1);

        rows.push(
          "<thead><tr>" +
          header.map(function (x) {
            return "<th>" + inline(x.trim()) + "</th>";
          }).join("") +
          "</tr></thead>"
        );

        i += 2;

        while (i < lines.length && /^\|.*\|$/.test(lines[i])) {
          var cells = lines[i].split("|").slice(1, -1);

          rows.push(
            "<tr>" +
            cells.map(function (x) {
              return "<td>" + inline(x.trim()) + "</td>";
            }).join("") +
            "</tr>"
          );

          i++;
        }

        html.push(
          "<table>" + rows[0] +
          "<tbody>" + rows.slice(1).join("") +
          "</tbody></table>"
        );

        continue;
      }

      if (/^###\s+/.test(line)) {
        html.push(
          "<h4>" +
          inline(line.replace(/^###\s+/, "")) +
          "</h4>"
        );
      } else if (/^##\s+/.test(line)) {
        html.push(
          "<h3>" +
          inline(line.replace(/^##\s+/, "")) +
          "</h3>"
        );
      } else if (/^#\s+/.test(line)) {
        html.push(
          "<h2>" +
          inline(line.replace(/^#\s+/, "")) +
          "</h2>"
        );
      } else if (/^\s*[-*]\s+/.test(line)) {
        html.push(
          "<li>" +
          inline(line.replace(/^\s*[-*]\s+/, "")) +
          "</li>"
        );
      } else if (line.trim() === "") {
        html.push("<br>");
      } else {
        html.push("<p>" + inline(line) + "</p>");
      }

      i++;
    }

    return html.join("").replace(
      /(<li>[\s\S]*?<\/li>)+/g,
      function (list) {
        return "<ul>" + list + "</ul>";
      }
    );
  }

  function inline(value) {
    return esc(value)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>");
  }

  function status(text, connected, error) {
    var e = $("connectionStatus");
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
    $("messageInput").disabled = !on;
    $("sendButton").disabled = !on;
  }

  function showAgent(a) {
    selected = a;

    if (!a) {
      $("agentDetails").innerHTML =
        "<p>No enabled agents are available.</p>";

      enable(false);
      return;
    }

    $("chatTitle").textContent = a.agent_name;

    $("agentDetails").innerHTML =
      "<h3>" + esc(a.agent_name) + "</h3>" +
      "<p>" + esc(a.description || "Ready for a conversation.") + "</p>" +
      '<span class="agent-tag active">' +
      esc(a.category || "General") + "</span>" +
      '<span class="agent-tag">' +
      (a.allowed_tools || []).length + " tools</span>" +
      '<span class="agent-tag">Backend managed</span>';

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
          o.textContent = a.agent_name;
          s.appendChild(o);
        });

        showAgent(agents[0] || null);
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

    var tools = meta && meta.tools_used
      ? meta.tools_used.length + " tools used · "
      : "";

    item.className = "message " + role;

    item.innerHTML =
      '<div class="avatar">' +
      (role === "user" ? "You" : "AI") +
      '</div><div><div class="bubble">' +
      (role === "assistant" ? formatAnswer(text) : esc(text)) +
      '</div><div class="message-meta">' +
      (role === "assistant" ? tools : "") +
      new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
      }) +
      "</div></div>";

    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
  }

  function thought(text, phase) {
    $("thoughtPanel").hidden = false;

    var row = document.createElement("div");

    var elapsed = executionStartedAt
      ? ((Date.now() - executionStartedAt) / 1000).toFixed(1) + "s"
      : "live";

    row.className = "thought-event";

    row.innerHTML =
      '<span class="pulse"></span><b>' +
      esc(text) +
      "</b><time>" +
      esc((phase || "activity") + " · " + elapsed) +
      "</time>";

    $("thoughtList").appendChild(row);
    $("thoughtList").scrollTop = $("thoughtList").scrollHeight;
  }

  function toggleThoughts() {
    var panel = $("thoughtPanel");
    var button = $("thoughtToggle");
    var minimized = panel.classList.toggle("minimized");

    button.textContent = minimized ? "Show" : "Minimize";

    button.title = minimized
      ? "Show live activity"
      : "Minimize live activity";

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
      "<h3>Ask your agent anything</h3>" +
      "<p>Select an agent on the left, then send a message.</p>" +
      "</div>";
  }

  function send(e) {
    e.preventDefault();

    if (busy || !selected) return;

    var input = $("messageInput");
    var query = input.value.trim();

    if (!query) return;

    addMessage("user", query);

    input.value = "";

    busy = true;
    executionStartedAt = Date.now();

    enable(false);

    $("thoughtList").innerHTML = "";
    $("thoughtPanel").hidden = false;

    var typing = $("typingIndicator");

    if (typing) typing.hidden = false;

    var streamingItem = null;
    var streamingBubble = null;
    var streamingAnswer = "";
    var finalData = null;

    /*
     * Streaming renderer
     *
     * Tokens can arrive much faster than the browser can repaint.
     * requestAnimationFrame batches them so the answer appears
     * progressively instead of rendering the whole answer at once.
     */
    var renderScheduled = false;
    var streamFinished = false;

    function renderStreaming() {
      if (streamFinished || !streamingBubble) return;

      streamingBubble.textContent = streamingAnswer;

      var cursor = document.createElement("span");
      cursor.className = "typing-cursor";

      streamingBubble.appendChild(cursor);

      var list = $("messageList");

      if (list) {
        list.scrollTop = list.scrollHeight;
      }
    }

    function scheduleStreamingRender() {
      if (renderScheduled || streamFinished) return;

      renderScheduled = true;

      var render = function () {
        renderScheduled = false;
        renderStreaming();
      };

      if (window.requestAnimationFrame) {
        window.requestAnimationFrame(render);
      } else {
        setTimeout(render, 16);
      }
    }

    function flushStreamingRender() {
      streamFinished = true;
      renderScheduled = false;

      if (!streamingBubble) return;

      streamingBubble.innerHTML = formatAnswer(streamingAnswer);

      var list = $("messageList");

      if (list) {
        list.scrollTop = list.scrollHeight;
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
          throw Error("Agent request failed: " + r.status);
        }

        var reader = r.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function read() {

          return reader.read().then(function (part) {

            if (part.done) {

              if (typing) {
                typing.hidden = true;
              }

              if (!finalData && !streamingAnswer) {
                throw Error("Stream ended without an answer");
              }

              if (streamingItem) {

                streamingItem.classList.remove("streaming");

                if (streamingBubble) {

                  if (finalData && finalData.answer) {
                    streamingAnswer = finalData.answer;
                  }

                  flushStreamingRender();
                }

                var metaEl =
                  streamingItem.querySelector(".message-meta");

                if (metaEl) {

                  var tools =
                    finalData &&
                    finalData.tools_used &&
                    finalData.tools_used.length
                      ? finalData.tools_used.length +
                        " tools used · "
                      : "";

                  metaEl.textContent =
                    tools +
                    new Date().toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit"
                    });
                }

              } else if (finalData) {

                addMessage(
                  "assistant",
                  finalData.answer,
                  finalData
                );
              }

              var list = $("messageList");

              if (list) {
                list.scrollTop = list.scrollHeight;
              }

              return;
            }

            buffer += decoder.decode(part.value, {
              stream: true
            });

            var blocks = buffer.split(/\r?\n\r?\n/);

            buffer = blocks.pop();

            blocks.forEach(function (block) {

              var line = block
                .split(/\r?\n/)
                .filter(function (x) {
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

                thought(
                  d.message,
                  d.phase
                );

              } else if (d.type === "token") {

                if (typing) {
                  typing.hidden = true;
                }

                if (!streamingBubble) {

                  var list = $("messageList");

                  var welcome =
                    list.querySelector(".welcome-card");

                  if (welcome) {
                    welcome.remove();
                  }

                  streamingItem =
                    document.createElement("article");

                  streamingItem.className =
                    "message assistant streaming";

                  streamingItem.innerHTML =
                    '<div class="avatar">AI</div>' +
                    "<div>" +
                    '<div class="bubble"></div>' +
                    '<div class="message-meta"></div>' +
                    "</div>";

                  list.appendChild(streamingItem);

                  streamingBubble =
                    streamingItem.querySelector(".bubble");
                }

                /*
                 * IMPORTANT:
                 * Do NOT modify innerHTML here.
                 * Just append the incoming token to the buffer.
                 * The browser renders it on the next animation frame.
                 */
                streamingAnswer += d.delta || "";

                scheduleStreamingRender();

              } else if (d.type === "complete") {

                finalData = d;

                if (typing) {
                  typing.hidden = true;
                }

                if (streamingBubble) {

                  streamingAnswer =
                    finalData.answer || streamingAnswer;

                  /*
                   * Final render:
                   * Convert the complete answer into formatted HTML
                   * only once the stream is finished.
                   */
                  flushStreamingRender();

                  streamingItem.classList.remove("streaming");

                  var metaEl =
                    streamingItem.querySelector(".message-meta");

                  if (metaEl) {

                    var tools =
                      finalData &&
                      finalData.tools_used &&
                      finalData.tools_used.length
                        ? finalData.tools_used.length +
                          " tools used · "
                        : "";

                    metaEl.textContent =
                      tools +
                      new Date().toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit"
                      });
                  }

                } else {

                  addMessage(
                    "assistant",
                    finalData.answer,
                    finalData
                  );
                }

                var list = $("messageList");

                if (list) {
                  list.scrollTop = list.scrollHeight;
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

        if (typing) {
          typing.hidden = true;
        }

        if (streamingBubble) {

          streamFinished = true;
          renderScheduled = false;

          streamingBubble.innerHTML =
            formatAnswer(streamingAnswer) +
            '<p style="color:#e25f6a;margin-top:6px">' +
            "<em>" +
            esc(err.message) +
            "</em></p>";

        } else {

          addMessage(
            "assistant",
            "I couldn't complete that request. " +
            err.message
          );
        }
      })

      .then(function () {

        if (typing) {
          typing.hidden = true;
        }

        busy = false;
        enable(true);
      });
  }

  document.addEventListener(
    "DOMContentLoaded",
    function () {

      $("agentSelect").addEventListener(
        "change",
        function () {

          showAgent(
            agents.filter(function (a) {
              return a.agent_id ===
                $("agentSelect").value;
            })[0] || null
          );

          reset();
        }
      );

      $("refreshButton").addEventListener(
        "click",
        load
      );

      $("newChatButton").addEventListener(
        "click",
        reset
      );

      $("thoughtToggle").addEventListener(
        "click",
        toggleThoughts
      );

      $("chatForm").addEventListener(
        "submit",
        send
      );

      $("messageInput").addEventListener(
        "keydown",
        function (e) {

          if (e.key === "Enter" && !e.shiftKey) {

            e.preventDefault();

            send(e);
          }
        }
      );

      load();

      setInterval(
        load,
        30000
      );
    }
  );

}());