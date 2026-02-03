// Constant labels
const RES_MON = "Resume Monitor"
const PAUSE_MON = "Pause Monitor"
const SHOW_DIS = "Show Disabled"
const HIDE_DIS = "Hide Disabled"
const SHOW_OFF = "Show Offline"
const HIDE_OFF = "Hide Offline"

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

/* Return whether the monitoring is paused or not */
async function get_pauseStatus() {
  const res = await fetch("/monitor/is_paused");
  const data = await res.json();
  
  return data.is_paused;
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

async function show_buttons() {
  let btn = document.getElementById("hidDis");
  if (btn_hideDisabled){
    btn.innerText = SHOW_DIS
  }else{
    btn.innerText = HIDE_DIS
  }
  btn = document.getElementById("hidOff");
  if (btn_hideOffline){
    btn.innerText = SHOW_OFF
  }else{
    btn.innerText = HIDE_OFF
  }
  btn = document.getElementById("pausMon");
  let is_paused = await get_pauseStatus();
  if (is_paused){
    btn.innerText = RES_MON
  }else{
    btn.innerText = PAUSE_MON
  }

}

function openFiles() {
  const tab = window.open("/files", "_blank");

  // to redirect or update if needed
  // tab.location.href = "/files?refresh=1";
}

async function show_streamers() {
  const data = await load_streamers();

  ["high", "medium", "low"].forEach(g => {
    const ul = document.getElementById(g);
    ul.innerHTML = "";

    Object.entries(data)
    .filter(([_, value]) => value.priority_group === g)
    .filter(([_, value]) => !(btn_hideDisabled && !value.enabled))
    .filter(([_, value]) => !(btn_hideOffline && !value.is_live))
    .sort(([, a], [, b]) => a.priority - b.priority)   // 🔑 THIS IS REQUIRED
    .forEach(([key, value]) => {
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

}

async function reorder(group, ul) {
  const order = [...ul.children].map(li => li.dataset.name);
  const resp = await fetch(`/api/reorder/${group}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(order)
  });
  const resp_json = await resp.json();
  if (!resp_json.ok) {
    showMessage(resp_json.error);
  }
  await show_streamers();
  return;

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
    await show_streamers();
  }
  return;
}
/* Hide/show disabled streamers */
async function toggleViewDisabled() {
  btn_hideDisabled = !btn_hideDisabled;
  await show_buttons();
  await show_streamers();
}
/* Hide/show streamers that are not live*/
async function toggleViewOffline() {
  btn_hideOffline = !btn_hideOffline;
  await show_buttons();
  await show_streamers();
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
/* Pause/resume monitoring */
async function togglePause() {
  // Read the status and toggle it
  let is_paused = await get_pauseStatus();
  // Check the action is already performed from another UI
  const btn = document.getElementById("pausMon");
  if ( ((btn.innerText == RES_MON) && (!is_paused)) ||
       ((btn.innerText == PAUSE_MON) && (is_paused))
  ){
    showMessage("Monitoring has already been " + is_paused?"paused":"resumed");
  }else{
    const resp = await fetch("/monitor/toggle_pause", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({is_paused:!is_paused})
      }
    );
    const resp_json = await resp.json();
    if (!resp_json.ok) {
      showMessage(resp_json.error);
    }
  }
  await show_buttons();    
}


/* Stop monitoring initiating graceful shutdown */
async function stopMonitor() {
  const resp = await fetch("/monitor/stop", { method: "POST" });
  const resp_json = await resp.json();
  if (!resp_json.ok) {
    showMessage(resp_json.error);
  }else{
    showMessage("Graceful shutdown initiated. UI will stop refreshing");
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

  await show_streamers();
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

/** Refresh the streamers and the buttons periodically */
async function refreshLoop() {
  // Do it at least initially
  await show_streamers();
  await show_buttons();
  while (true) {
    if (stopCalled){
      break;
    }
    is_paused = await get_pauseStatus()
    if (!userActive && !is_paused) {
      await show_streamers();
      await show_buttons();
    }
    await new Promise(r => setTimeout(r, refresh_rate_sec*1000));
  }
}

//
// Run at start
//
document.addEventListener("DOMContentLoaded", () => {

  ["high", "medium", "low"].forEach(g => {
    const ul = document.getElementById(g);
    new Sortable(ul, {
      group: "priority",
      animation: 150,
      draggable: "li.item",
      onAdd: () => reorder(g, ul),
      onUpdate: () => reorder(g, ul),
      onRemove: () => reorder(g, ul)
    });
  });
  /* Listener to not refresh when user is active */
  document.addEventListener("mousedown", () => userActive = true);
  document.addEventListener("mouseup", () => userActive = false);

  refreshLoop();

});
