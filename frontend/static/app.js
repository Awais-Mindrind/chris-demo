// Minimal JavaScript for Quote Agent UI

let currentSessionId = null;

// Send chat message with SSE streaming
async function sendChat() {
  const msgInput = document.getElementById("msg");
  const message = msgInput.value.trim();

  if (!message) return;

  const transcript = document.getElementById("transcript");
  const status = document.getElementById("status");

  // Clear input and add user message
  msgInput.value = "";
  transcript.textContent += `User: ${message}\n\n`;
  status.textContent = "Streaming...";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
        session_id: currentSessionId,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentResponse = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process SSE lines
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("event:")) {
          const eventType = line.slice(6).trim();

          if (eventType === "token") {
            // Get next line for data
            const dataLine = lines[lines.indexOf(line) + 1];
            if (dataLine && dataLine.startsWith("data:")) {
              try {
                const data = JSON.parse(dataLine.slice(5));
                currentResponse += data.chunk || data.text || "";
                transcript.textContent =
                  transcript.textContent.replace(/Assistant:.*$/, "") +
                  `Assistant: ${currentResponse}`;
              } catch (e) {
                // Fallback to raw data
                currentResponse += dataLine.slice(5);
                transcript.textContent =
                  transcript.textContent.replace(/Assistant:.*$/, "") +
                  `Assistant: ${currentResponse}`;
              }
            }
          } else if (eventType === "done") {
            const dataLine = lines[lines.indexOf(line) + 1];
            if (dataLine && dataLine.startsWith("data:")) {
              try {
                const data = JSON.parse(dataLine.slice(5));
                if (data.pdf_url) {
                  transcript.textContent += `\n\n📄 <a href="${data.pdf_url}" target="_blank" class="pdf-link">View Quote PDF</a>\n`;
                }
                if (data.session_id) {
                  currentSessionId = data.session_id;
                }
              } catch (e) {
                console.error("Error parsing done event:", e);
              }
            }
            status.textContent = "Ready";
            return;
          } else if (eventType === "error") {
            const dataLine = lines[lines.indexOf(line) + 1];
            if (dataLine && dataLine.startsWith("data:")) {
              try {
                const data = JSON.parse(dataLine.slice(5));
                transcript.textContent += `\n\n❌ Error: ${
                  data.message || "Unknown error"
                }\n`;
              } catch (e) {
                transcript.textContent += `\n\n❌ Error: Failed to parse error message\n`;
              }
            }
            status.textContent = "Error";
            return;
          }
        }
      }
    }

    status.textContent = "Ready";
  } catch (error) {
    console.error("Chat error:", error);
    transcript.textContent += `\n\n❌ Error: ${error.message}\n`;
    status.textContent = "Error";
  }
}

// Create quote directly
async function createQuote() {
  const quoteResult = document.getElementById("quote-result");
  quoteResult.textContent = "Creating quote...";
  quoteResult.className = "quote-result";

  try {
    const response = await fetch("/actions/create_quote", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        account_id: 1, // Acme Ltd
        pricebook_id: 1, // Standard USD
        idempotency_key: "Q-DEMO-UI-001",
        lines: [
          {
            sku_id: 7, // Widget - Standard (USD)
            qty: 10,
          },
        ],
      }),
    });

    const result = await response.json();

    if (response.ok) {
      quoteResult.textContent = `✅ Quote created successfully!\n\nQuote ID: ${result.quote_id}\nStatus: ${result.status}\nTotal Lines: ${result.total_lines}\n\n📄 <a href="/quotes/${result.quote_id}/pdf" target="_blank" class="pdf-link">View Quote PDF</a>`;
      quoteResult.className = "quote-result success";
    } else {
      quoteResult.textContent = `❌ Error creating quote:\n${JSON.stringify(
        result,
        null,
        2
      )}`;
      quoteResult.className = "quote-result error";
    }
  } catch (error) {
    console.error("Quote creation error:", error);
    quoteResult.textContent = `❌ Error: ${error.message}`;
    quoteResult.className = "quote-result error";
  }
}

// Handle Enter key in message input
document.addEventListener("DOMContentLoaded", function () {
  const msgInput = document.getElementById("msg");
  msgInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      sendChat();
    }
  });
});
