import signal
import psutil
import types
import sys
import os
import json
import logging

from httpx import Response

from TikTokLive.client.client import TikTokLiveClient
from TikTokLive.client.errors import UserNotFoundError
from TikTokLive.client.web.routes.fetch_room_id_live_html import FailedParseRoomIdError
from TikTokLive.client.web.web_base import ClientRoute, TikTokHTTPClient
from TikTokLive.client.web.web_settings import WebDefaults

from utils.system_utils import debug_breakpoint

async def _fetch_user_room_data(cls, web: TikTokHTTPClient, unique_id: str) -> dict:
        """
        PATCHED METHOD TO REPLACE ORIGINAL METHOD!!!
        Fetch user room from the API (not the same as room info)

        :param web: The TikTokHTTPClient client to use
        :param unique_id: The user to check
        :return: The user's room info

        """
        
        response: Response = await web.get(
            url=WebDefaults.tiktok_app_url + f"/api-live/user/room/",
            extra_params=(
                {
                    "uniqueId": unique_id,
                    "sourceType": 54
                }
            )
        )
        try:
            response_json: dict = response.json()
        except json.decoder.JSONDecodeError as e:
            if response.status_code == 503:
                logger = logging.getLogger(cls.__name__)
                logger.warning(f"⚠️  Service unavailable fetching room data for {unique_id}: {e}")
                # debug_breakpoint()
                raise FailedParseRoomIdError(
                    unique_id,
                    "Service Unavailable (503) from TikTok when fetching room data."
                )
            elif response.status_code == 200 and response.text == "":
                logger = logging.getLogger(cls.__name__)
                logger.warning(f"⚠️  Service replies with empty response fetching room data for {unique_id}: {e}")
                # debug_breakpoint()
                raise FailedParseRoomIdError(
                    unique_id,
                    "Empty response from TikTok when fetching room data."
                )
            else:
                debug_breakpoint()

        except Exception as e:
            logger = logging.getLogger(cls.__name__)
            logger.error(f"❌ Exception {e} of type {type(e)}, received response: {response} - {response.text}")
            debug_breakpoint()
            raise FailedParseRoomIdError(
                    unique_id,
                    f"Exception {e} of type {type(e)}, received response: {response} - {response.text}"
                )

        # Invalid user
        if response_json["message"] == "user_not_found":
            # debug_breakpoint()
            raise UserNotFoundError(
                unique_id,
                (
                    f"The requested user '{unique_id}' is not capable of going LIVE on TikTok, "
                    "or has never gone live on TikTok, or does not exist."
                )
            )
        if response_json["message"] == "Service Unavailable":
            raise FailedParseRoomIdError(
                unique_id,
                f"Service Unavailable from TikTok when fetching room data, entire response: {response_json}"
            )
        if not ("data" in response_json and response_json["data"] != None and 
                "liveRoom" in response_json["data"] and response_json["data"]["liveRoom"] != None and 
                "status" in response_json["data"]["liveRoom"] and response_json["data"]["liveRoom"]["status"] != None):
            debug_breakpoint()
            raise FailedParseRoomIdError(
                unique_id,
                "Could not find 'data.liveRoom.status' in the response from TikTok."
            )
        return response_json


def _stop(self) -> None:
    """
    Stop a livestream recording if it is ongoing

    :return: None

    """
    # debug_breakpoint()
    if not self.is_recording:
        self._logger.warning("⚠️  Attempted to stop a stream that does not exist or has not started.")
        return
    # Avoid exception since apparently sometimes _ffmpeg has already terminated
    if psutil.pid_exists(self._ffmpeg.process.pid):
        os.kill(self._ffmpeg.process.pid, signal.SIGTERM)
    else:
        self._logger.debug("FFmpeg process already terminated.")

    self._ffmpeg = None
    self._thread = None


def patch_TikTokLiveClient(client: TikTokLiveClient):
    """Apply all patches to TikTokLiveClient"""
    # Override the stop method to avoid exception since apparently sometimes the video writing process has already terminated
    client.web.fetch_video_data.stop = types.MethodType(_stop, client.web.fetch_video_data)
    # Override fetch_user_room_data method to have error handling for httpx exceptions
    sys.modules[client._web.fetch_is_live.__class__.__module__].FetchRoomIdAPIRoute.fetch_user_room_data = classmethod(_fetch_user_room_data)
