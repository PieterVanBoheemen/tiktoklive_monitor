import argparse
import asyncio
import json
import threading
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


PRIORITY_GROUPS = ["high", "medium", "low"]


class TikUIApp:
    def __init__(self, file_path: str):
        self.lock = asyncio.Lock()
        self.file_path = file_path
        
        self.app = FastAPI()

    async def initialize(self):

        await self.load_config()    
        await self.setup_routes()

    # ---------- Load / Save ----------
    async def load_config(self) -> None:

        with Path(self.file_path).open() as f:
            cfg = json.load(f)

        for s in cfg["streamers"].values():
            s.setdefault("priority_group", "medium")
            s.setdefault("priority", 0)
            s.setdefault("is_recording", False)


        self.str_state = {
            "config": cfg
        }

    async def save_config(self) -> None:
        suffix = ".web"
        path = Path(self.file_path)
        web_file_path = f"{path.stem}{suffix}{path.suffix}"
        with Path(web_file_path).open("w") as f:
            json.dump(self.str_state["config"], f, indent=2)

    async def setup_routes(self):
        # ---------- Static HTML ----------
        self.app.mount("/static", StaticFiles(directory="./ui/static"), name="static")
        
        # ---------- API ----------
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            return Path("./ui/static/index.html").read_text()
        
        @self.app.get("/api/streamers")
        async def get_streamers():
            grouped = {g: [] for g in PRIORITY_GROUPS}

            async with self.lock:
                # breakpoint()
                for name, s in self.str_state["config"]["streamers"].items():
                    grouped[s["priority_group"]].append((name, s))

            for g in grouped:
                grouped[g].sort(key=lambda x: x[1]["priority"])

            return grouped

        @self.app.post("/api/reorder/{group}")
        async def reorder(group: str, request: Request):
            order = await request.json()

            async with self.lock:
                for idx, name in enumerate(order):
                    s = self.str_state["config"]["streamers"][name]
                    s["priority_group"] = group
                    s["priority"] = idx

            return {"ok": True}


        @self.app.post("/api/toggle/{name}")
        async def toggle(name: str):
            async with self.lock:
                s = self.str_state["config"]["streamers"][name]
                s["enabled"] = not s["enabled"]
            return {"enabled": s["enabled"]}


        @self.app.post("/api/save")
        async def save():
            async with self.lock:
                self.save_config()
            return {"saved": True }

    async def run(self):
        self.app.run(debug=True)


async def start_server(config):


    myapp = TikUIApp(config)
    await myapp.initialize()
    app = myapp.app
    
    config = uvicorn.Config(app, loop="asyncio", log_config=None)
    server = uvicorn.Server(config)
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