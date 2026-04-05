const API_URL = "http://localhost:5000/suggest";

let state = {
  schema: "",
  query: "",
  suggestion: ""
};

let debounceTimer;

// ---------- INIT UI ----------
document.getElementById("app").innerHTML = `
  <div class="container">
      <h1>✍️ Real-Time SQL Writer</h1>
      <div class="grid">
          <div class="input-section">
              <label>1. Define Schema</label>
              <textarea id="schema" placeholder="e.g., CREATE TABLE users..."></textarea>

              <label>2. SQL Input (Press TAB to complete)</label>
              <div class="ghost-wrapper">
                  <textarea id="ghost" class="ghost-textarea" tabindex="-1"></textarea>
                  <textarea id="input" class="real-textarea" placeholder="SELECT * FROM..."></textarea>
              </div>
          </div>

          <div class="suggestion-section">
              <h3>AI Suggestion</h3>
              <div id="suggestion-box" class="info">No suggestion...</div>
          </div>
      </div>
  </div>
`;

const schemaEl = document.getElementById("schema");
const inputEl = document.getElementById("input");
const ghostEl = document.getElementById("ghost");
const suggestionBoxEl = document.getElementById("suggestion-box");

// ---------- API ----------
async function fetchSuggestion() {
  if (!state.query || state.query.trim().length < 3) {
    state.suggestion = "";
    updateUI();
    return;
  }

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        schema: state.schema,
        query: state.query
      })
    });

    const data = await res.json();
    // Only update if the user hasn't cleared the input while waiting
    state.suggestion = data.suggestion || "";
  } catch (err) {
    console.error("Fetch error:", err);
    state.suggestion = "";
  }
  updateUI();
}

// ---------- UI UPDATE ----------
function updateUI() {
  const queryLower = state.query.toLowerCase();
  const suggestionLower = state.suggestion.toLowerCase();

  let remaining = "";
  // Check if suggestion actually starts with what the user typed
  if (state.suggestion && suggestionLower.startsWith(queryLower)) {
    remaining = state.suggestion.slice(state.query.length);
  }

  // Ghost text: Original text + faded remaining part
  ghostEl.value = state.query + remaining;

  // Sync scroll positions
  ghostEl.scrollTop = inputEl.scrollTop;
  ghostEl.scrollLeft = inputEl.scrollLeft;

  // Suggestion panel
  if (state.suggestion) {
    suggestionBoxEl.innerHTML = `<pre><code>${state.suggestion}</code></pre>`;
    suggestionBoxEl.className = "suggestion-code";
  } else {
    suggestionBoxEl.innerHTML = "No suggestion...";
    suggestionBoxEl.className = "info";
  }
}

// ---------- EVENTS ----------

schemaEl.addEventListener("input", (e) => {
  state.schema = e.target.value;
});

inputEl.addEventListener("input", (e) => {
  state.query = e.target.value;
  updateUI();

  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fetchSuggestion, 300);
});

// Sync scroll during manual scrolling
inputEl.addEventListener("scroll", () => {
  ghostEl.scrollTop = inputEl.scrollTop;
  ghostEl.scrollLeft = inputEl.scrollLeft;
});

// TAB HANDLER
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    const queryLower = state.query.toLowerCase();
    const suggestionLower = state.suggestion.toLowerCase();

    // If we have a matching suggestion
    if (state.suggestion && suggestionLower.startsWith(queryLower)) {
      e.preventDefault(); // Stop focus from leaving the textarea
      
      // Apply the suggestion
      state.query = state.suggestion;
      inputEl.value = state.query;
      
      // Clear suggestion state so ghost disappears
      state.suggestion = ""; 
      
      updateUI();

      // Move cursor to the end
      inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
    }
  }
});