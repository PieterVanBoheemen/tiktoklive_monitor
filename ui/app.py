import argparse
import asyncio
from asyncio import Task
from typing import Optional
import json
import logging
from pathlib import Path
import copy
import sys
from datetime import datetime, timedelta, time
# For correct mime type
import mimetypes
import html



from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from monitor.stream_monitor import StreamMonitor
from utils.system_utils import debug_breakpoint

PRIORITY_GROUPS = ["high", "medium", "low"]

import subprocess
import json

def get_mp4_duration(path: Path) -> str | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path)
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        
        return str(timedelta(seconds=int(float(data["format"]["duration"]))))
    except Exception:
        return None

def get_human_file_size(size: int) -> str:
    if size / 1024 < 1:
        return f"{size}B"
    elif size / (1024**2) < 1:
        return f"{size/1024:.2f}KiB"
    elif size / (1024**3) < 1:
        return f"{size/1024**2:.2f}MiB"
    else:
        return f"{size/1024**3:.2f}GiB"

class ScheduleState:
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    start_task: Optional[Task] = None
    end_task: Optional[Task] = None
    action = None

    def __init__(self, action):
        ScheduleState.action = action
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _seconds_until(t: time) -> float:
        # breakpoint()
        now = datetime.now().astimezone()
        target = datetime.combine(now.date(), t)

        while target <= now:
            target += timedelta(days=1)

        return (target - now).total_seconds()
    
    def are_tasks_active(self) -> tuple[bool,bool]:
        start_task_active = False
        end_task_active = False
        if self.start_task and not (self.start_task.done() or self.start_task.cancelled()):
            start_task_active = True
        if self.end_task and not (self.end_task.done() or self.end_task.cancelled()):
            end_task_active = True
        
        return start_task_active, end_task_active

    def trigger_action(self, value: bool):
        self.logger.info(f"Scheduled action triggered: {value} at {datetime.now()}")
        # call real business logic here
        self.action(value)
        
        # reschedule the task that terminated
        # Assumption is that the self.start_time is earlier than
        # the time we calculate the next trigger, so that the next
        # trigger will happen the next day.
        if value:
            self.start_task = asyncio.create_task(
                    self.schedule_trigger(self.start_time, True)
                )
        else:
            self.end_task = asyncio.create_task(
                self.schedule_trigger(self.end_time, False)
            )
    
    async def schedule_trigger(self,trigger_time: float, value: bool):
        delay = ScheduleState._seconds_until(trigger_time)
        
        try:
            await asyncio.sleep(delay)
            self.trigger_action(value)
        except asyncio.CancelledError:
            pass  # expected on reschedule
    
    def cancel_tasks(self):
        # cancel existing tasks

        for task in (self.start_task, self.end_task):
            if task:
                task.cancel()

        self.start_task = None
        self.end_task = None
        self.start_time = None
        self.end_time = None

    def create_tasks(self) -> bool:
        """
        Creates the tasks and recreate them to keep the schedule running,
        being carefull not to overwrite existing tasks
        """
        # 
        if not (self.start_time and self.end_time):
            self.logger.warning("Cannot create schedule tasks if start and end time are not set, possibly schedule was canceled")
            return False
        
        start_task_active, end_task_active = self.are_tasks_active()

        if start_task_active and end_task_active:
            debug_breakpoint()
            self.logger.warning("Cannot create schedule tasks if start and end tasks are both active")
            return False
        
        if not start_task_active:
            self.start_task = asyncio.create_task(
                    self.schedule_trigger(self.start_time, True)
                )
        if not end_task_active:
            self.end_task = asyncio.create_task(
                self.schedule_trigger(self.end_time, False)
            )

    def create_schedule(self, start_time, end_time):
        if (self.start_time != None and self.start_time != start_time) or (self.end_time != None and self.end_time != end_time):
            self.cancel_tasks()
        self.start_time = start_time
        self.end_time = end_time
        self.create_tasks()


class ScheduleRequest(BaseModel):
    start_time: time
    end_time: time

class TikUIApp:
    """
        This class is the back-end for the Web interface
        By design this class does not store any data,
        because the data is always fetched from the 
        authoritative source, the StreamMonitor.
    """
    def __init__(self, monitor: StreamMonitor):
        self.logger = logging.getLogger(__name__)
        self.lock = asyncio.Lock()
        self.monitor = monitor

        self.app = FastAPI()
        self.allowed_exts = {".mp4", ".csv"}
        self.setup_routes()
        self.schedule_state = ScheduleState(action = self.monitor.pause_monitoring)
  
    # ---------- Load / Save ----------
    def _get_conf_file_path(self):
        """
        Returns the path to the configuration file
        """
        return self.monitor.config_manager.config_file
    
    def _get_streamers(self):
        """
        Returns a deepcopy of the streamers to be sure we operate read-only on the internal data structures
        """
        return copy.deepcopy(self.monitor.config_manager.get_streamers())
    
    def _get_settings(self):
        """
        Returns a deepcopy of the settings to be sure we operate read-only on the internal data structures
        """
        return copy.deepcopy(self.monitor.config_manager.get_settings())

    def _get_recording(self) -> list[str]:
        """
        Returns a list of usernames currently being recorded
        No deepcopy needed, it is a generated list of keys
        """
        # breakpoint()
        return self.monitor.active_recordings
    
    def _get_live_streamers(self):
        """
        Returns a list of usernames currently being recorded
        No deepcopy needed, it is a generated list of keys
        """
        return self.monitor.live_streamers

    
    def _save_config(self) -> bool:
        """
        Save configuration to a different file than the original config file
        to avoid overwriting it (this is also why we do not use the save function from ConfigManager)
        """
        suffix = f'{datetime.now().strftime("%d-%m-%Y_%H:%M:%S")}'
        path = Path(self._get_conf_file_path())
        web_file_path = f"{path.stem}_{suffix}{path.suffix}"
        streamers = self._get_streamers()
        settings = self._get_settings()
        obj = {"streamers": streamers, "settings": settings}
        
        with open(web_file_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        
        return True

    def _update_streamers_status(self) -> dict[str,dict]:
        """
        Returns the list of streamers augmented with the status per streamer,
        is the streamer online and is the streamer being recorded        
        """
        streamers = self._get_streamers()
        # breakpoint()
        recorded = self._get_recording()
        live = self._get_live_streamers()
        # breakpoint()
        for k in streamers:
            if k in live:
                streamers[k]['is_live'] = True
            else:
                streamers[k]['is_live'] = False
            if k in recorded:
                streamers[k]['is_recording'] = True
                streamers[k]['is_live'] = True
            else:
                streamers[k]['is_recording'] = False
            if streamers[k]['is_live'] or streamers[k]['is_recording']:
                self.logger.debug(f"User {k} is live: {streamers[k]['is_live']}, is recording: {streamers[k]['is_recording']}")
        return streamers 

    def _get_rec_dir(self):
        """
        Returns the path to the directory where recordings and other live data are saved
        """
        return Path(self.monitor.config_manager.config['settings']['output_directory']).resolve()
    
    def _resolve_file(self, name: str) -> Path:
        """
        Return the path to the file <name> in the recordings directory,
        if it exists and the extension is allowed
        """
        output_dir = self._get_rec_dir()
        path = (output_dir / name).resolve()

        if output_dir not in path.parents:
            raise HTTPException(400, "Invalid path")

        if not path.exists() or path.suffix not in self.allowed_exts:
            raise HTTPException(404, "File not found")

        return path

    def setup_routes(self):
        self.setup_file_routes()
        self.setup_streamers_api()
        self.setup_monitor_api()
        self.setup_schedule_api()

    def setup_schedule_api(self):
        @self.app.get("/schedule")
        async def get_schedule():
            # breakpoint()
            return {
                "start_time": self.schedule_state.start_time.strftime("%H:%M:%S") if self.schedule_state.start_time else "00:00:00",
                "end_time": self.schedule_state.end_time.strftime("%H:%M:%S") if self.schedule_state.end_time else "00:00:00",
                "enabled": self.schedule_state.start_time is not None
            }
        
        @self.app.get("/schedule-ui", response_class=HTMLResponse)
        async def schedule_ui():
            # breakpoint()
            return open("./ui/static/schedule.html").read()
        
        @self.app.post("/schedule")
        async def set_schedule(req: ScheduleRequest):
            # breakpoint()
            async with self.lock:
                
                # special case: disabled
                if req.start_time == time(0, 0, 0) and req.end_time == time(0, 0, 0):
                    self.schedule_state.cancel_tasks()
                    # Reactivate monitoring (safe option, maybe not what the user wanted)
                    # self.monitor.pause_monitoring(to_pause=False)
                    # Better ask the user
                    if self.monitor.is_mon_paused():
                        return {"status": f"Schedule disabled, monitor paused, you might want to resume it"}
                    else:
                        return {"status": f"Schedule disabled"}

                if req.start_time == req.end_time:
                    return {"error": "Start time and end time must be different"}

                # schedule new triggers
                self.schedule_state.create_schedule(req.start_time,req.end_time)
                
                return {"status": "Schedule activated"}

    def setup_file_routes(self):
        # ---------- Static HTML ----------
        self.app.mount("/static", StaticFiles(directory="./ui/static"), name="static")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            return Path("./ui/static/index.html").read_text()
        
        @self.app.get("/files", response_class=HTMLResponse)
        async def list_files():
            files = []

            async with self.lock:
                for p in self._get_rec_dir().iterdir():
                    if not p.is_file():
                        continue
                    if p.suffix.lower() not in self.allowed_exts:
                        continue

                    stat = p.stat()
                    duration = get_mp4_duration(p) if p.suffix.lower() == ".mp4" else None

                    files.append({
                        "name": p.name,
                        "size": get_human_file_size(stat.st_size),
                        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%H:%M:%S %d-%m-%Y"),
                        "duration": duration,
                    })

                # newest first
                files.sort(key=lambda f: f["mtime"], reverse=True)

                rows = []
                for file in files:
                    name = html.escape(file["name"])
                    dl_url = f"/files/download/{name}"

                    rows.append(f"""
                    <tr>
                        <td>{name}</td>
                        <td>{file["size"]}</td>
                        <td>{file["mtime"]}</td>
                        <td>{file["duration"]}</td>
                        <td><a href="{dl_url}">Download</a>
                        </td>
                    </tr>
                    """)

            return f"""
            <html>
            <head>
                <title>Recordings</title>
                <style>
                table {{ border-collapse: collapse }}
                td, th {{ border: 1px solid #ccc; padding: 6px }}
                </style>
            </head>
            <body>
                <h2>Available files</h2>
                <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th><th>Duration</th><th>Download</th></tr>
                {''.join(rows)}
                </table>
            </body>
            </html>
            """
        # This does not work, as the browser downloads it
        @self.app.get("/files/view/{filename}")
        def view_file(filename: str):
            path = self._resolve_file(filename)

            mime, _ = mimetypes.guess_type(path.name)
            # breakpoint()
            return FileResponse(
                path,
                media_type=mime or "application/octet-stream",
                filename=path.name,
            )
        
        @self.app.get("/files/download/{filename}")
        def download_file(filename: str):
            path = self._resolve_file(filename)

            return FileResponse(
                path,
                media_type="application/octet-stream",
                filename=path.name,
                headers={"Content-Disposition": f'attachment; filename="{path.name}"'}
            )
        
    def setup_streamers_api(self):
        @self.app.get("/api/streamers")
        async def get_streamers():
            async with self.lock:
                streamers = self._update_streamers_status()
                return streamers
                # grouped = {g: [] for g in PRIORITY_GROUPS}
                # # breakpoint()
                # for name, s in streamers.items():
                #     # breakpoint()
                #     grouped[s['priority_group']].append((name, s))

                # for g in grouped:
                #     grouped[g].sort(key=lambda x: x[1]['priority'])

                # return grouped

        @self.app.post("/api/add_streamer")
        async def add_streamer(request: Request):
            payload = await request.json()
            
            raw_username = payload.get("username", "")
            priority_group = payload.get("priority_group", "low")
            tags_raw = payload.get("tags", "")
            notes = payload.get("notes", "")
            enabled = bool(payload.get("enabled", True))

            # normalize username
            username = raw_username.strip().replace(" ", "")
            if not username.startswith("@"):
                username = "@" + username

            async with self.lock:
                streamers = self._update_streamers_status()
                # determine priority = append to bottom of group
                same_group = [
                    s for s in streamers.values()
                    if s.get("priority_group") == priority_group
                ]
                priority = len(same_group)
                # breakpoint()
                streamer = {f"{username}": {
                    "enabled": enabled,
                    "session_id": None,
                    "tt_target_idc": None,
                    "priority_group": priority_group,
                    "priority": priority,
                    "tags": [t.strip() for t in tags_raw if t.strip()],
                    "notes": notes
                    }
                }
                if self.monitor.config_manager.add_streamer(streamer):
                    return {"ok": True}
                else:
                    return {"ok": False, "error": "Username already exists"}

        @self.app.post("/api/toggle_enable")
        async def toggle_enable(request: Request):
            data = await request.json()
            name = data["name"]
            enable = data["enable"]
            if enable:
                if self.monitor.config_manager.enable_streamer(name):
                    return {"ok": True, "message":f"User {name} is enabled"}
            else:
                if self.monitor.config_manager.disable_streamer(name):
                    return {"ok": True, "message":f"User {name} is disabled"}

            return {"ok": False, "error": f"Failed {'enabling' if enable else 'disabling'} streamer {name} "}

        @self.app.post("/api/reorder/{group}")
        async def reorder(group: str, request: Request):
            order = await request.json()

            async with self.lock:
                errors = []
                for idx, name in enumerate(order):
                    # breakpoint()
                    if not self.monitor.config_manager.set_streamer_priority(name, group, idx):
                        errors.append(name)
                # breakpoint()

            if len(errors) == 0:
                return {"ok": True}
            else:
                return {"ok": False, "error": f"Error setting priority for the following streamers: {errors}"}

        @self.app.post("/api/save")
        async def save():
            async with self.lock:
                if self._save_config():
                    return {"ok": True}
                else:
                    return {"ok": False, "error": "Error saving conf file"}

    def setup_monitor_api(self):
        @self.app.get("/monitor/is_paused")
        async def is_paused():
            async with self.lock:
                return {"is_paused":self.monitor.is_mon_paused()}

        @self.app.post("/monitor/toggle_pause")
        async def toggle_pause(request: Request):
            data = await request.json()
            is_paused = data["is_paused"]
            if is_paused:
                self.monitor.pause_monitoring(to_pause=True)
            else:
                self.monitor.pause_monitoring(to_pause=False)
            return {"ok": True, "message":f"Monitoring is {'paused' if is_paused else 'resumed'}"}

        @self.app.post("/monitor/stop")
        async def stop():
            async with self.lock:
                self.monitor.monitoring = False                
                return {"ok": True}

    async def run(self):
        self.app.run(debug=True)


async def start_server(monitor:StreamMonitor):
    # breakpoint()
    myapp = TikUIApp(monitor)

    app = myapp.app
    
    srv_config = uvicorn.Config(app, loop="asyncio", host='0.0.0.0', port=8000, log_config=None, reload=False)
    server = uvicorn.Server(srv_config)

    # expose server so caller can stop it
    monitor.uvicorn_server = server
    await server.serve()
    
def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=""""""
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default="./web_config.json",
        help='Path to configuration file (default: ./web_config.json)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    return parser.parse_args()



if __name__ == "__main__":
# breakpoint()
    print("Running UI stand alone not supported due to dependency with Stream Monitor")
    sys.exit(1)
    # args = parse_args()
    # asyncio.run(start_server(args.config))
