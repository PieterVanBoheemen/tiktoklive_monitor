UTC_OFFSET = 0;

async function applySchedule() {
  const start = document.getElementById("startTime").value;
  const end = document.getElementById("endTime").value;

  if (!start || !end) {
    setStatus("Please select both times", true);
    return;
  }

  const resp = await fetch("/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_time: start + UTC_OFFSET,
      end_time: end + UTC_OFFSET
    })
  });

  const data = await resp.json();
  setStatus(`Result: ${data.status}`);
}

async function disableSchedule() {
  await fetch("/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_time: "00:00:00",
      end_time: "00:00:00"
    })
  });

  document.getElementById("startTime").value = "";
  document.getElementById("endTime").value = "";
  setStatus("Schedule disabled");
}

async function loadSchedule() {
  const resp = await fetch("/schedule");
  const data = await resp.json();

  if (data.enabled) {
    document.getElementById("startTime").value = data.start_time;
    document.getElementById("endTime").value = data.end_time;
    setStatus("Loaded existing schedule");
  } else {
    setStatus("No active schedule");
  }
  // Calculate UTC offset
  const date = new Date();
  const timezoneOffset = date.getTimezoneOffset();
  let offset = -(timezoneOffset/60);
  if (offset >= 0){
    UTC_OFFSET = "+";
  }else{
    UTC_OFFSET = "-";
  }
  UTC_OFFSET = UTC_OFFSET + offset.toString().padStart(2, '0') + ":00"
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.style.color = isError ? "red" : "green";
}

// load backend state on open
loadSchedule();
