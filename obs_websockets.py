import time
import os
import sys
import asyncio
import obsws_python as obs
from contextlib import contextmanager
from audio_player import AudioManager
from bot_utils import DEBUG
#from obsws_python import ReqClient
#from obsws_python.reqs import get_current_program_scene, GetSceneItemList, SetSceneItemEnabled, SetSceneItemTransform
  # noqa: E402

##########################################################
##########################################################

WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 4455
WEBSOCKET_PASSWORD = "zFhp4uoqr7Xj4ROS"
audio_manager = AudioManager()


@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output."""
    with open(os.devnull, "w") as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr


class OBSWebsocketsManager:
    ws = None
    
    def __init__(self):
        # Connect to websockets
        while True:
            try:
                with suppress_stderr():
                    self.ws = obs.ReqClient(host = WEBSOCKET_HOST, port = WEBSOCKET_PORT, password = WEBSOCKET_PASSWORD, json_response = False)
                break
            except Exception:
                print("\n[ERROR]Could not connect to OBS websockets. Retrying in 10 seconds...")
                time.sleep(10)
        print("[green]Connected to OBS Websockets!\n")

    def activate_assistant(self, assistant_name: str, stationary_assistant_name: str):
        current_scene = self.ws.get_current_program_scene().current_program_scene_name
        scene_items = self.ws.get_scene_item_list(current_scene)
        scene_item_id = None
        stationary = False

        for item in scene_items.scene_items:
            if item["sourceName"] == assistant_name:
                scene_item_id = item["sceneItemId"]
                break
            elif item["sourceName"] == stationary_assistant_name:
                scene_item_id = item["sceneItemId"]
                stationary = True
                break
        if not scene_item_id:
            print(f"[ERROR]{assistant_name} or {stationary_assistant_name} not found in scene.")
            return
        # Reset to off-screen first
        if stationary: #Grabs transform in case of early cancel and returns it to the bot, no need to continue further
            return self.ws.get_scene_item_transform(current_scene, scene_item_id)
        self.ws.set_scene_item_transform(
            current_scene,
            scene_item_id,
            {
                "positionX": 2562,
                "positionY": 0,
                "scaleX": 0.5,
                "scaleY": 0.5
            }
        )
        self.ws.set_scene_item_enabled(current_scene, scene_item_id, True)

        for x in range(2562, 1200, -40):
            self.ws.set_scene_item_transform(
                current_scene,
                scene_item_id,
                {
                    "positionX": x,
                    "positionY": 0,
                    "scaleX": 0.5,
                    "scaleY": 0.5
                }
            )
            time.sleep(0.01)

    def deactivate_assistant(self, assistant_name: str, is_stationary: bool = False, original_transform = None):
        current_scene = self.ws.get_current_program_scene().current_program_scene_name
        scene_items = self.ws.get_scene_item_list(current_scene)
        scene_item_id = None

        for item in scene_items.scene_items:
            if item["sourceName"] == assistant_name:
                scene_item_id = item["sceneItemId"]
                break
        if not scene_item_id:
            print(f"[ERROR]{assistant_name} not found in scene.")
            return
        
        if is_stationary and original_transform:
            try:
                current_transform = self.ws.get_scene_item_transform(current_scene, scene_item_id)
                current_x = current_transform.positionX
                target_x = original_transform.positionX

                step = -40 if current_x > target_x else 40

                for x in range(int(current_x), int(target_x), step):
                    self.ws.set_scene_item_transform(
                        current_scene,
                        scene_item_id, {
                            "positionX": x,
                            "positionY": original_transform.positionY,
                            "scaleX": original_transform.scaleX,
                            "scaleY": original_transform.scaleY
                        }
                    )
                    time.sleep(0.01)

                # Final snap to exact position
                self.ws.set_scene_item_transform(
                    current_scene,
                    scene_item_id,
                    {
                        "positionX": target_x,
                        "positionY": original_transform.positionY,
                        "scaleX": original_transform.scaleX,
                        "scaleY": original_transform.scaleY
                    }
                )
            except Exception as e:
                print(f"[ERROR]Returning stationary assistant to rest: {e}")
            return

        for x in range(1200, 2562, 40):
            self.ws.set_scene_item_transform(
                current_scene,
                scene_item_id,
                {
                    "positionX": x,
                    "positionY": 0,
                    "scaleX": 0.5,
                    "scaleY": 0.5
                }
            )
            time.sleep(0.01)

        self.ws.set_scene_item_enabled(current_scene, scene_item_id, False)

    async def bounce_while_talking(self, volumes, min_vol, max_vol, total_duration_ms, assistant_name, stationary_assistant_name, base_y=0, scene_name=None):
        try:
            if not scene_name:
                scene_name = self.ws.get_current_program_scene().current_program_scene_name
            scene_items = self.ws.get_scene_item_list(scene_name)

            scene_item_id = None
            actual_base_y = base_y
            actual_base_x = 1200

            for item in scene_items.scene_items:
                if item["sourceName"] in (assistant_name, stationary_assistant_name):
                    scene_item_id = item["sceneItemId"]
                    if item["sourceName"] == stationary_assistant_name:
                        try:
                            t = self.ws.get_scene_item_transform(scene_name, scene_item_id)
                            actual_base_y = t.scene_item_transform["positionY"]
                            actual_base_x = t.scene_item_transform["positionX"]
                        except Exception as e:
                            print(f"[ERROR] [bounce] Failed to fetch transform: {e}")
                    break
            if not scene_item_id:
                if DEBUG:
                    print(f"[DEBUG]{assistant_name} not found in scene.")
                return

            frame_ms = 50
            num_frames = len(volumes)
            start_time = time.perf_counter()
            total_duration_s = total_duration_ms / 1000

            while True:
                elapsed = time.perf_counter() - start_time
                if elapsed >= total_duration_s:
                    break

                # Calculate which volume frame to use based on elapsed time
                frame_index = int(elapsed * 1000 // frame_ms) % num_frames
                vol = volumes[frame_index]
                y = await audio_manager.map_volume_to_y(vol, min_vol, max_vol, actual_base_y)

                await asyncio.to_thread(self.ws.set_scene_item_transform,
                    scene_name,
                    scene_item_id,
                    {
                        "positionX": actual_base_x,
                        "positionY": y,
                        "scaleX": 0.5,
                        "scaleY": 0.5
                    }
                )
                # Sleep a small amount to yield control, ~frame_ms or less
                await asyncio.sleep(frame_ms / 2000)  # sleep half frame to be responsive

            # Reset to rest position
            await asyncio.to_thread(self.ws.set_scene_item_transform,
                scene_name,
                scene_item_id,
                {
                    "positionX": actual_base_x,
                    "positionY": actual_base_y,
                    "scaleX": 0.5,
                    "scaleY": 0.5
                }
            )
        except asyncio.CancelledError:
            await asyncio.to_thread(self.ws.set_scene_item_transform,
                scene_name,
                scene_item_id,
                {
                    "positionX": actual_base_x,
                    "positionY": actual_base_y,
                    "scaleX": 0.5,
                    "scaleY": 0.5
                }
            )


    def disconnect(self):
        self.ws.disconnect()

#############################################