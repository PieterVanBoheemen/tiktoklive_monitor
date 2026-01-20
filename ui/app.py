import argparse
import asyncio
import json
import threading
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from monitor.stream_monitor import StreamMonitor

PRIORITY_GROUPS = ["high", "medium", "low"]


class TikUIApp:
    def __init__(self, monitor: StreamMonitor):
        self.lock = asyncio.Lock()
        self.monitor = monitor
        self.str_state = {
            "streamers": {},
            "settings": {}
        }
        
        self.app = FastAPI()

    async def initialize(self):

        await self.load_config()
        await self.update_status()
        await self.setup_routes()

    def _get_streamers(self):
        return self.monitor.config_manager.get_streamers().items()
    
    # ---------- Load / Save ----------
    async def load_config(self) -> None:
        
        for k,v in self._get_streamers():
            self.str_state['streamers'][k] = v


    async def save_config(self) -> None:
        suffix = ".web"
        path = Path(self.config_manager.config_file)
        web_file_path = f"{path.stem}{suffix}{path.suffix}"
        with Path(web_file_path).open("w") as f:
            json.dump(self.str_state, f, indent=2)

    async def update_status(self):
        async with self.lock:
            recorded = self.monitor.active_recordings
            live = self.monitor.live_streamers
            # breakpoint()
            for k in self.str_state['streamers']:
                if k in live:
                    self.str_state['streamers'][k]["is_live"] = True
                else:
                    self.str_state['streamers'][k]["is_live"] = False
                if k in recorded:
                    self.str_state['streamers'][k]["is_recording"] = True
                    self.str_state['streamers'][k]["is_recording"] = True
                else:
                    self.str_state['streamers'][k]["is_recording"] = False
                


    async def setup_routes(self):
        # ---------- Static HTML ----------
        self.app.mount("/static", StaticFiles(directory="./ui/static"), name="static")
        
        # ---------- API ----------
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            return Path("./ui/static/index.html").read_text()
        
        @self.app.get("/api/streamers")
        async def get_streamers():
            await self.update_status()
            grouped = {g: [] for g in PRIORITY_GROUPS}

            async with self.lock:
                # breakpoint()
                for name, s in self.str_state["streamers"].items():
                    # breakpoint()
                    grouped[s["priority_group"]].append((name, s))

            for g in grouped:
                grouped[g].sort(key=lambda x: x[1]["priority"])

            return grouped

        @self.app.post("/api/reorder/{group}")
        async def reorder(group: str, request: Request):
            order = await request.json()

            async with self.lock:
                for idx, name in enumerate(order):
                    s = self.str_state["streamers"][name]
                    s["priority_group"] = group
                    s["priority"] = idx

            return {"ok": True}


        @self.app.post("/api/toggle/{name}")
        async def toggle(name: str):
            async with self.lock:
                s = self.str_state["streamers"][name]
                s["enabled"] = not s["enabled"]
            return {"enabled": s["enabled"]}


        @self.app.post("/api/save")
        async def save():
            async with self.lock:
                self.save_config()
            return {"saved": True }

    async def run(self):
        self.app.run(debug=True)


async def start_server(config_manager):

    myapp = TikUIApp(config_manager)
    await myapp.initialize()
    app = myapp.app
    
    srv_config = uvicorn.Config(app, loop="asyncio", log_config=None, reload=True)
    server = uvicorn.Server(srv_config)
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
    args = parse_args()
    asyncio.run(start_server(args.config))
