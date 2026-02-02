var UTC_OFFSET = 0;

async function applySchedule() {
  const start = document.getElementById("startTime").value;
  const end = document.getElementById("endTime").value;

  if (!start || !end) {
    setStatus("Please select both times", true);
    return;
  }
  
  if (start === end) {
    setStatus("Start time and end time must be different", true);
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
  if (data.error){
    setStatus(data.error, true);  
  }
  setStatus(data.status);
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

function setStatus(msg, isError = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.style.color = isError ? "red" : "green";
}

// load backend state on open
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
}

function utcOffset() {
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

function attachValidators(){
    const startTime = document.getElementById("startTime");
    const endTime   = document.getElementById("endTime");
    const applyBtn  = document.getElementById("applyBtn");

    function validateInputs() {
        const start = startTime.value;
        const end   = endTime.value;

        // valid only if both set and different
        const valid = start && end && start !== end;

        applyBtn.disabled = !valid;
    }

    // attach validation to live input changes
    startTime.addEventListener("input", validateInputs);
    endTime.addEventListener("input", validateInputs);

    // initial state
    validateInputs();
}

async function initPage() {
    await loadSchedule();
    attachValidators();
    utcOffset();
}

initPage();

