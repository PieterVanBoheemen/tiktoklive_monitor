import argparse
import asyncio
import json
import logging
from pathlib import Path
import copy

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from monitor.stream_monitor import StreamMonitor

PRIORITY_GROUPS = ["high", "medium", "low"]


class TikUIApp:
    def __init__(self, monitor: StreamMonitor):
        self.logger = logging.getLogger(__name__)
        self.lock = asyncio.Lock()
        self.monitor = monitor

        self.app = FastAPI()

    async def initialize(self):
        await self.setup_routes()

    
    # ---------- Load / Save ----------
    def _get_conf_path(self):
        return self.monitor.config_manager.config_file
    
    def _get_streamers(self):
        """
        Returns a deepcopy to be sure we do not interfere with logic
        """
        return copy.deepcopy(self.monitor.config_manager.get_streamers())
    
    def _get_settings(self):
        """
        Returns a deepcopy to be sure we do not interfere with logic
        """
        return copy.deepcopy(self.monitor.config_manager.get_settings())

    def _get_recording(self) -> list[str]:
        """
        Returns a list of usernames currently being recorded
        """
        # breakpoint()
        return self.monitor.active_recordings
    
    def _get_live_streamers(self):
        """
        Returns a deepcopy to be sure we do not interfere with logic
        """
        return copy.deepcopy(self.monitor.live_streamers)

    def save_config(self) -> bool:
        """
        Save configuration to a different file than the original config file
        to avoid overwriting it (this is also why we do not use the save function from ConfigManager)
        """
        suffix = ".web"
        path = Path(self._get_conf_path())
        web_file_path = f"{path.stem}{suffix}{path.suffix}"
        streamers = self._get_streamers()
        settings = self._get_settings()
        obj = {"streamers": streamers, "settings": settings}
        
        with open(web_file_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        
        return True

    def update_status(self) -> dict[str,dict]:
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

    async def setup_routes(self):
        # ---------- Static HTML ----------
        self.app.mount("/static", StaticFiles(directory="./ui/static"), name="static")
        
        # ---------- API ----------
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            return Path("./ui/static/index.html").read_text()
        
        @self.app.get("/api/streamers")
        async def get_streamers():
            async with self.lock:
                streamers = self.update_status()
                return streamers
                # grouped = {g: [] for g in PRIORITY_GROUPS}
                # # breakpoint()
                # for name, s in streamers.items():
                #     # breakpoint()
                #     grouped[s['priority_group']].append((name, s))

                # for g in grouped:
                #     grouped[g].sort(key=lambda x: x[1]['priority'])

                # return grouped

        @self.app.post("/api/reorder/{group}")
        async def reorder(group: str, request: Request):
            order = await request.json()

            async with self.lock:
                for idx, name in enumerate(order):
                    s = self.str_state['streamers'][name]
                    s['priority_group'] = group
                    s['priority'] = idx

            return {"ok": True}


        @self.app.post("/api/toggle_enable")
        async def toggle_enable(request: Request):
            data = await request.json()
            name = data["name"]
            enable = data["enable"]
            if enable:
                if self.monitor.config_manager.enable_streamer(name):
                    return {"ok": True}
            else:
                if self.monitor.config_manager.disable_streamer(name):
                    return {"ok": True}

            return {"ok": False, "error": f"Failed {'enabling' if enable else 'disabling'} streamer {name} "}


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
                streamers = self.update_status()
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

        @self.app.post("/api/save")
        async def save():
            async with self.lock:
                if self.save_config():
                    return {"ok": True}
                else:
                    return {"ok": False, "error": "Error saving conf file"}

    async def run(self):
        self.app.run(debug=True)


async def start_server(config_manager):
    # breakpoint()
    myapp = TikUIApp(config_manager)
    await myapp.initialize()
    app = myapp.app
    
    srv_config = uvicorn.Config(app, loop="asyncio", log_config=None, reload=True, reload_dirs="./")
    server = uvicorn.Server(srv_config)
    try:
        await server.serve()
    except asyncio.exceptions.CancelledError as e:
        logger = logging.getLogger(__name__)
        logger.info(f"Caught task cancelation, assuming request to terminate")

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
    args = parse_args()
    asyncio.run(start_server(args.config))
