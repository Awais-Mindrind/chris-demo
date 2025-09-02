// Minimal JavaScript for Quote Agent UI

let currentSessionId = null;
let currentQuote = null;
let currentPdfUrl = null;

// Send chat message with non-streaming approach
async function sendChat() {
  const msgInput = document.getElementById("msg");
  const message = msgInput.value.trim();

  if (!message) return;

  const transcript = document.getElementById("transcript");
  const status = document.getElementById("status");

  // Clear input and add user message
  msgInput.value = "";
  transcript.textContent += `User: ${message}\n\n`;
  status.textContent = "Processing...";

  // Add processing indicator
  const processingIndicator = document.createElement("div");
  processingIndicator.id = "processing-indicator";
  processingIndicator.textContent = "🤖 AI is thinking...";
  processingIndicator.style.cssText =
    "color: #7f8c8d; font-style: italic; margin: 10px 0;";
  transcript.appendChild(processingIndicator);

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

    const data = await response.json();

    // Remove processing indicator
    const processingIndicator = document.getElementById("processing-indicator");
    if (processingIndicator) {
      processingIndicator.remove();
    }

    // Update session ID if provided
    if (data.session_id) {
      currentSessionId = data.session_id;
    }

    // Add assistant response to transcript
    transcript.textContent += `Assistant: ${data.response}\n\n`;

    // Handle quote data if available
    if (data.quote_data) {
      updateQuotePreview(data.quote_data);
      transcript.textContent += `\n📊 Quote preview updated in sidebar\n`;
    }

    // Handle PDF URL if available
    if (data.pdf_url) {
      currentPdfUrl = data.pdf_url;
      updateQuoteActions(true);
      transcript.textContent += `\n\n📄 <a href="${data.pdf_url}" target="_blank" class="pdf-link">View Quote PDF</a>\n`;
    }

    // Handle errors
    if (!data.success && data.error) {
      transcript.textContent += `\n\n❌ Error: ${data.error}\n`;
      status.textContent = "Error";
    } else {
      status.textContent = "Ready";
    }
  } catch (error) {
    console.error("Chat error:", error);

    // Remove processing indicator
    const processingIndicator = document.getElementById("processing-indicator");
    if (processingIndicator) {
      processingIndicator.remove();
    }

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

// Quote preview functions
function updateQuotePreview(quoteData) {
  const previewContent = document.getElementById("quote-preview-content");

  if (!quoteData) {
    previewContent.innerHTML = '<p class="no-quote">No quote in progress</p>';
    updateQuoteActions(false);
    return;
  }

  let html = `
    <div class="quote-info">
      <h4>Quote #${quoteData.id || "Draft"}</h4>
      <p><strong>Account:</strong> ${
        quoteData.account_name || "Not specified"
      }</p>
      <p><strong>Status:</strong> ${quoteData.status || "Draft"}</p>
      <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
    </div>
  `;

  if (quoteData.lines && quoteData.lines.length > 0) {
    html += `
      <div class="quote-lines">
        <h5>Line Items</h5>
    `;

    quoteData.lines.forEach((line) => {
      const lineTotal = (
        line.qty *
        line.unit_price *
        (1 - (line.discount_pct || 0))
      ).toFixed(2);
      html += `
        <div class="quote-line">
          <span>${line.sku_name || line.sku_code} (×${line.qty})</span>
          <span>$${lineTotal}</span>
        </div>
      `;
    });

    html += `</div>`;

    const subtotal = quoteData.lines.reduce((sum, line) => {
      return sum + line.qty * line.unit_price * (1 - (line.discount_pct || 0));
    }, 0);

    html += `
      <div class="quote-total">
        <div class="quote-line">
          <span>Subtotal:</span>
          <span>$${subtotal.toFixed(2)}</span>
        </div>
        <div class="quote-line">
          <span>Total:</span>
          <span>$${subtotal.toFixed(2)}</span>
        </div>
      </div>
    `;
  } else {
    html += '<p class="no-quote">No line items added yet</p>';
  }

  previewContent.innerHTML = html;
  currentQuote = quoteData;
}

function updateQuoteActions(hasPdf) {
  const quoteActions = document.getElementById("quote-actions");
  const downloadBtn = document.getElementById("download-pdf-btn");

  if (hasPdf && currentPdfUrl) {
    quoteActions.style.display = "block";
    downloadBtn.disabled = false;
  } else {
    quoteActions.style.display = "none";
    downloadBtn.disabled = true;
  }
}

function downloadPDF() {
  if (currentPdfUrl) {
    window.open(currentPdfUrl, "_blank");
  }
}

// Parse quote information from agent responses
function parseQuoteFromResponse(response) {
  // Look for quote-related information in the response
  const quotePatterns = [
    /quote\s*#?(\d+)/i,
    /account[:\s]+([^,\n]+)/i,
    /sku[:\s]+([^,\n]+)/i,
    /quantity[:\s]+(\d+)/i,
    /price[:\s]+\$?([\d,]+\.?\d*)/i,
  ];

  // This is a simple parser - in a real implementation, you might want to
  // extract more structured data from the agent's response
  const accountMatch = response.match(/account[:\s]+([^,\n]+)/i);
  const skuMatch = response.match(/sku[:\s]+([^,\n]+)/i);
  const qtyMatch = response.match(/quantity[:\s]+(\d+)/i);

  if (accountMatch || skuMatch || qtyMatch) {
    return {
      account_name: accountMatch ? accountMatch[1].trim() : null,
      lines:
        skuMatch && qtyMatch
          ? [
              {
                sku_name: skuMatch[1].trim(),
                qty: parseInt(qtyMatch[1]),
                unit_price: 0, // Would need to be fetched from backend
                discount_pct: 0,
              },
            ]
          : [],
    };
  }

  return null;
}

// Test function to demonstrate quote preview
function testQuotePreview() {
  const testQuote = {
    id: 123,
    status: "Draft",
    account_name: "Acme Ltd",
    lines: [
      {
        sku_name: "Widget",
        sku_code: "WID-001",
        qty: 5,
        unit_price: 10.0,
        discount_pct: 0,
      },
      {
        sku_name: "Gadget",
        sku_code: "GAD-002",
        qty: 2,
        unit_price: 25.0,
        discount_pct: 0.1,
      },
    ],
  };

  updateQuotePreview(testQuote);
  currentPdfUrl = "/quotes/123/pdf";
  updateQuoteActions(true);
}

// Handle Enter key in message input
document.addEventListener("DOMContentLoaded", function () {
  const msgInput = document.getElementById("msg");
  msgInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      sendChat();
    }
  });

  // Initialize quote preview
  updateQuotePreview(null);

  // Add test button for demo purposes
  const testBtn = document.createElement("button");
  testBtn.textContent = "Test Quote Preview";
  testBtn.onclick = testQuotePreview;
  testBtn.style.marginTop = "10px";
  testBtn.style.background = "#9b59b6";
  testBtn.onmouseover = () => (testBtn.style.background = "#8e44ad");
  testBtn.onmouseout = () => (testBtn.style.background = "#9b59b6");

  const actionsSection = document.querySelector(".actions-section");
  actionsSection.appendChild(testBtn);
});
