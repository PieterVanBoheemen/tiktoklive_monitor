// Constants
const refresh_rate_sec = 10;

// UI Status variables
var btn_hideDisabled = false;
var btn_hideOffline = false;

var userActive = false;
var stopCalled = false

//
// Data loading
//
/* Get streamer data enriched with status info */
async function load_streamers() {
  const res = await fetch("/api/streamers");
  const data = await res.json();
  return data;  
}

//
// Layout
//

/* Handle pop-up to add streamers */
function openAddModal() {
  document.getElementById("addModal").classList.remove("hidden");
}

function closeAddModal() {
  document.getElementById("addModal").classList.add("hidden");
}

/* Handle pop-up to communicate messages */
function showMessage(msg) {
  document.getElementById("msgText").innerText = msg;
  document.getElementById("msgModal").classList.remove("hidden");
}

function closeMsgModal() {
  document.getElementById("msgModal").classList.add("hidden");
}

/** Creates the tile for each streamer */
function make_item(username, priority, tags, notes, enabled) {
    return `
    <span class="username">${username}</span><br>
    <span class="priority">Priority: ${priority}</span><br>
    <span class="tags">Tags: ${tags.join(", ")}</span><br>
    <span class="notes">Notes: ${notes}</span><br>
    <button onclick="toggleEnable('${username}','${enabled}')">
      ${enabled ? "Disable" : "Enable"}
    </button>
  `;
}

/* Minimal normalization for usernames */
function normalizeUsername(raw) {
  username = raw
    .trim()
    .replace(/\s+/g, "")
    .replace(/^@+/, "@");
  
  if (!username){
    return "";
  }
  if (!username.startsWith("@")) {
    username = "@" + raw;
  }

  return username;
}

async function show_streamers() {
  const data = await load_streamers();

  ["high", "medium", "low"].forEach(g => {
    const ul = document.getElementById(g);
    ul.innerHTML = "";

    Object.entries(data).forEach(([key, value]) => {
      if (value.priority_group != g) {
        return;
      }
      
      if (!value.enabled && btn_hideDisabled){
        return;
      }
      if (!value.is_live && btn_hideOffline){
        return;
      }
      const li = document.createElement("li");
      
      let classes = ["item"];

      if (!value.enabled) {
        classes.push("disabled");
      }
      if (value.is_live) {
        classes.push("live");
      }
      if (value.is_recording) {
        classes.push("recording");
      }
      li.className = classes.join(" ");

      li.dataset.name = key;
      li.innerHTML = make_item(key, value.priority, value.tags, value.notes, value.enabled);
    
      ul.appendChild(li);
    });
  });
//   ["high", "medium", "low"].forEach(g => {
//   new Sortable(document.getElementById(g), {
//     group: "priority",
//     animation: 150,
//     onEnd: () => reorder(g, document.getElementById(g))
//   });
// });

}

async function reorder(group, ul) {
  const order = [...ul.children].map(li => li.dataset.name);
  await fetch(`/api/reorder/${group}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(order)
  });
}

//
// Button handling
//
/* Enable/disable streamers */
async function toggleEnable(name, toDisable) {
  enable = toDisable=="true" ? false : true;
  const resp = await fetch("/api/toggle_enable", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    name: name,
    enable: enable
  })
});
  const resp_json = await resp.json();
  if (!resp_json.ok) {
    showMessage(resp_json.error);
    return;
  }else{
    show_streamers();
  }
  return;
}
/* Hide/show disabled streamers */
async function toggleViewDisabled() {
  btn_hideDisabled = !btn_hideDisabled;
  const btn = document.getElementById("hidDis");
  if (btn_hideDisabled){
    btn.innerText = "Show Disabled"
  }else{
    btn.innerText = "Hide Disabled"
  }
  show_streamers();
}
/* Hide/show streamers that are not live*/
async function toggleViewOffline() {
  btn_hideOffline = !btn_hideOffline;
  const btn = document.getElementById("hidOff");
  if (btn_hideOffline){
    btn.innerText = "Show Offline"
  }else{
    btn.innerText = "Hide Offline"
  }
  show_streamers();
}
/* Save conf with possibly added streamer */
async function saveConfig() {
  const resp = await fetch("/api/save", { method: "POST" });
  const resp_json = await resp.json();
  if (!resp_json.ok) {
    showMessage(resp_json.error);
  }else{
    showMessage("Current configuration saved to file");
    
  }
  return;
}

/* Stop monitoring initiating graceful shutdown */
async function stopMonitor() {
  const resp = await fetch("/api/stop", { method: "POST" });
  const resp_json = await resp.json();
  if (!resp_json.ok) {
    showMessage(resp_json.error);
  }else{
    showMessage("Graceful shutdown initiated, UI will not refresh");
    stopCalled = true;
  }
  return;
}

/* Handle adding streamers */
async function confirmAddStreamer() {
  let username = normalizeUsername(document.getElementById("new-username").value);
  if (!username) {
    showMessage("Username cannot be empty.");
    return;
  }

  const priorityGroup = document.getElementById("new-priority-group").value;
  const tags = document.getElementById("new-tags").value
    .split(",")
    .map(t => t.trim())
    .filter(Boolean);
  const notes = document.getElementById("new-notes").value.trim();
  const enabled = document.getElementById("new-enabled").value;
  
  const data = await load_streamers();
  if (data && data[username]) {
    if (data[username].enabled){
      showMessage(`User ${username} already exists and is enabled.`);
    }else{
      showMessage(`User ${username} already exists but is disabled.`);
    }

    return;
  }
  
  const resp = await fetch("/api/add_streamer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username,
      priority_group: priorityGroup,
      tags,
      notes,
      enabled
    })
  });
  
  const resp_json = await resp.json();
  if (!resp_json.ok) {
    showMessage(resp_json.error);
    return;
  }

  show_streamers();
  closeAddModal();
  showMessage(`Streamer ${username} added successfully.`);

  // Reset form
  document.getElementById("new-username").value = "";
  document.getElementById("new-tags").value = "";
  document.getElementById("new-notes").value = "";
}

//
// Refresh UI
//

/** Refresh the streamers periodically */
async function refreshLoop() {
  while (true) {
    if (!userActive && !stopCalled) {
      await show_streamers();
    }
    await new Promise(r => setTimeout(r, refresh_rate_sec*1000));
  }
}

//
// Run at start
//
/* Listener to not refresh when user is active */
document.addEventListener("mousedown", () => userActive = true);
document.addEventListener("mouseup", () => userActive = false);

refreshLoop();
