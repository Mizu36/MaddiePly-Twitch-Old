import time
import os
import sys
import asyncio
import obsws_python as obs
from contextlib import contextmanager
from audio_player import AudioManager
from bot_utils import DEBUG
from json_manager import load_settings, load_tracker, save_tracker

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

    async def set_local_variables(self):
        settings = await load_settings()
        self.onscreen_location = settings.get("Onscreen Location")
        self.offscreen_location = settings.get("Offscreen Location")

    async def capture_location(self, is_onscreen, assistant_name):
        current_scene = self.ws.get_current_program_scene().current_program_scene_name
        scene_items = self.ws.get_scene_item_list(current_scene)
        scene_item_id = None

        for item in scene_items.scene_items:
            if item["sourceName"] == assistant_name:
                scene_item_id = item["sceneItemId"]
                break

        if not scene_item_id:
            print(f"[ERROR] {assistant_name} not found in scene.")
            return None

        try:
            current_transform = self.ws.get_scene_item_transform(current_scene, scene_item_id)
            transform = current_transform.scene_item_transform
            location_data = {
                "x": transform["positionX"],
                "y": transform["positionY"],
                "scaleX": transform["scaleX"],
                "scaleY": transform["scaleY"]
            }

            if is_onscreen:
                self.onscreen_location = location_data
            else:
                self.offscreen_location = location_data

            return location_data

        except Exception as e:
            print(f"[ERROR] Failed to get transform for {assistant_name}: {e}")
            return None
        
    async def capture_transform(self, item_name):
        print("capture_transform entered")
        current_scene = self.ws.get_current_program_scene().current_program_scene_name
        scene_items = self.ws.get_scene_item_list(current_scene)
        scene_item_id = None

        for item in scene_items.scene_items:
            if item["sourceName"] == item_name:
                scene_item_id = item["sceneItemId"]
                break

        print(scene_item_id)

        if not scene_item_id:
            print(f"[ERROR] {item_name} not found in scene.")
            return None

        try:
            transform_data = self.ws.get_scene_item_transform(current_scene, scene_item_id)
            transform = transform_data.scene_item_transform
            print(transform)

            transform_data = {
                "positionX": transform["positionX"],
                "positionY": transform["positionY"],
                "scaleX": transform["scaleX"],
                "scaleY": transform["scaleY"],
                "rotation": transform["rotation"],
                "cropTop": transform["cropTop"],
                "cropBottom": transform["cropBottom"],
                "cropLeft": transform["cropLeft"],
                "cropRight": transform["cropRight"]
            }

            # Include manually saved base dimensions
            settings = await load_settings()
            transform_data["baseWidth"] = settings.get("Progress Bar BaseX", 1)
            transform_data["baseHeight"] = settings.get("Progress Bar BaseY", 1)

            print(transform_data)
            return transform_data

        except Exception as e:
            print(f"[ERROR] Failed to get transform for {item_name}: {e}")
            return None


    async def update_bar(self, points_added: int):
        settings = await load_settings()
        original_transform = settings["Progress Bar Transform Full-Sized"]
        streamathon_tracker = await load_tracker()

        current_points = streamathon_tracker["Current Point Total"]
        goal_points = streamathon_tracker["Current Goal Tier"]

        if goal_points < current_points:
            current_points = goal_points

        # Progress as a float between 0.0 and 1.0
        progress_ratio = current_points / goal_points if goal_points > 0 else 0.0

        # Calculate true width/height based on scale * base size from settings
        base_width = settings["Progress Bar Transform Full-Sized"].get("baseWidth", 1)
        base_height = settings["Progress Bar Transform Full-Sized"].get("baseHeight", 1)
        bar_width = original_transform["scaleX"] * base_width
        bar_height = original_transform["scaleY"] * base_height

        is_horizontal = bar_width >= bar_height
        full_crop = int(base_width if is_horizontal else base_height)
        crop_key = "cropRight" if is_horizontal else "cropTop"

        # Determine desired crop amount based on current progress
        target_crop = int(full_crop * (1 - progress_ratio))

        # Get current scene item
        bar_name = settings["Progress Bar Name"]
        scene_name = self.ws.get_current_program_scene().current_program_scene_name
        scene_items = self.ws.get_scene_item_list(scene_name)

        scene_item_id = None
        for item in scene_items.scene_items:
            if item["sourceName"] == bar_name:
                scene_item_id = item["sceneItemId"]
                break

        if not scene_item_id:
            print(f"[ERROR] Progress bar '{bar_name}' not found in scene.")
            return

        # Get current crop state
        transform = self.ws.get_scene_item_transform(scene_name, scene_item_id).scene_item_transform
        current_crop = transform.get(crop_key, 0)

        # Exit early if already correctly cropped (when just checking on scene change)
        if points_added == 0 and current_crop == target_crop:
            return

        # Animate crop change
        steps = 20
        for i in range(1, steps + 1):
            t = i / steps
            new_crop = int(current_crop + (target_crop - current_crop) * t)

            crop_data = {
                "cropTop": transform["cropTop"],
                "cropBottom": transform["cropBottom"],
                "cropLeft": transform["cropLeft"],
                "cropRight": transform["cropRight"],
            }
            crop_data[crop_key] = new_crop

            await asyncio.to_thread(
                self.ws.set_scene_item_transform,
                scene_name,
                scene_item_id,
                {
                    "positionX": transform["positionX"],
                    "positionY": transform["positionY"],
                    "scaleX": transform["scaleX"],
                    "scaleY": transform["scaleY"],
                    "rotation": transform["rotation"],
                    **crop_data
                }
            )

            await asyncio.sleep(0.02)

        # Final snap to exact crop target
        crop_data[crop_key] = target_crop
        await asyncio.to_thread(
            self.ws.set_scene_item_transform,
            scene_name,
            scene_item_id,
            {
                "positionX": transform["positionX"],
                "positionY": transform["positionY"],
                "scaleX": transform["scaleX"],
                "scaleY": transform["scaleY"],
                "rotation": transform["rotation"],
                **crop_data
            }
        )



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

        if stationary:
            return self.ws.get_scene_item_transform(current_scene, scene_item_id)

        if (not self.onscreen_location or not self.offscreen_location):
            print("[ERROR]Set onscreen and offscreen locations for the non-stationary assistant. Use the tools tab of the GUI.")
            return

        self.ws.set_scene_item_transform(
            current_scene,
            scene_item_id,
            {
                "positionX": self.offscreen_location["x"],
                "positionY": self.offscreen_location["y"],
                "scaleX": self.offscreen_location["scaleX"],
                "scaleY": self.offscreen_location["scaleY"]
            }
        )
        self.ws.set_scene_item_enabled(current_scene, scene_item_id, True)

        steps = 30
        for i in range(1, steps + 1):
            t = i / steps
            x = self.offscreen_location["x"] + (self.onscreen_location["x"] - self.offscreen_location["x"]) * t
            y = self.offscreen_location["y"] + (self.onscreen_location["y"] - self.offscreen_location["y"]) * t
            self.ws.set_scene_item_transform(
                current_scene,
                scene_item_id,
                {
                    "positionX": x,
                    "positionY": y,
                    "scaleX": self.onscreen_location["scaleX"],
                    "scaleY": self.onscreen_location["scaleY"]
                }
            )
            time.sleep(0.01)

        self.ws.set_scene_item_transform(
            current_scene,
            scene_item_id,
            {
                "positionX": self.onscreen_location["x"],
                "positionY": self.onscreen_location["y"],
                "scaleX": self.onscreen_location["scaleX"],
                "scaleY": self.onscreen_location["scaleY"]
            }
        )

    def deactivate_assistant(self, assistant_name: str, is_stationary: bool = False, original_transform=None):
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

        try:
            transform_data = self.ws.get_scene_item_transform(current_scene, scene_item_id)
            transform = transform_data.scene_item_transform
            current_x = transform["positionX"]
            current_y = transform["positionY"]
        except Exception as e:
            print(f"[ERROR]Failed to get current transform: {e}")
            return

        if is_stationary and original_transform:
            try:
                target_x = original_transform["positionX"]
                target_y = original_transform["positionY"]
                steps = 30
                for i in range(1, steps + 1):
                    t = i / steps
                    x = current_x + (target_x - current_x) * t
                    y = current_y + (target_y - current_y) * t
                    self.ws.set_scene_item_transform(
                        current_scene,
                        scene_item_id,
                        {
                            "positionX": x,
                            "positionY": y,
                            "scaleX": original_transform["scaleX"],
                            "scaleY": original_transform["scaleY"]
                        }
                    )
                    time.sleep(0.01)

                self.ws.set_scene_item_transform(
                    current_scene,
                    scene_item_id,
                    {
                        "positionX": target_x,
                        "positionY": target_y,
                        "scaleX": original_transform["scaleX"],
                        "scaleY": original_transform["scaleY"]
                    }
                )
            except Exception as e:
                print(f"[ERROR]Returning stationary assistant to rest: {e}")
            return

        if not self.offscreen_location:
            print("[ERROR]Offscreen location not set. Use the GUI tools to define it.")
            return

        try:
            target_x = self.offscreen_location["x"]
            target_y = self.offscreen_location["y"]
            steps = 30
            for i in range(1, steps + 1):
                t = i / steps
                x = current_x + (target_x - current_x) * t
                y = current_y + (target_y - current_y) * t
                self.ws.set_scene_item_transform(
                    current_scene,
                    scene_item_id,
                    {
                        "positionX": x,
                        "positionY": y,
                        "scaleX": self.offscreen_location["scaleX"],
                        "scaleY": self.offscreen_location["scaleY"]
                    }
                )
                time.sleep(0.01)

            self.ws.set_scene_item_transform(
                current_scene,
                scene_item_id,
                {
                    "positionX": target_x,
                    "positionY": target_y,
                    "scaleX": self.offscreen_location["scaleX"],
                    "scaleY": self.offscreen_location["scaleY"]
                }
            )
        except Exception as e:
            print(f"[ERROR]Deactivating assistant: {e}")

        self.ws.set_scene_item_enabled(current_scene, scene_item_id, False)


    async def bounce_while_talking(self, volumes, min_vol, max_vol, total_duration_ms, assistant_name, stationary_assistant_name, scene_name=None, original_transform=None):
        try:
            if not scene_name:
                scene_name = self.ws.get_current_program_scene().current_program_scene_name
            scene_items = self.ws.get_scene_item_list(scene_name)            

            scene_item_id = None

            for item in scene_items.scene_items:
                if item["sourceName"] in (assistant_name, stationary_assistant_name):
                    scene_item_id = item["sceneItemId"]
                    break

            if not scene_item_id:
                if DEBUG:
                    print(f"[DEBUG]{assistant_name} not found in scene.")
                return

            # Override base X/Y from original transform if available
            if original_transform:
                actual_base_y = original_transform.positionY
                actual_base_x = original_transform.positionX
                scale_x = original_transform.scaleX
                scale_y = original_transform.scaleY
            else:
                actual_base_y = self.onscreen_location["y"]
                actual_base_x = self.onscreen_location["x"]
                scale_x = self.onscreen_location["scaleX"]
                scale_y = self.onscreen_location["scaleY"]

            frame_ms = 50
            num_frames = len(volumes)
            start_time = time.perf_counter()
            total_duration_s = total_duration_ms / 1000

            while True:
                elapsed = time.perf_counter() - start_time
                if elapsed >= total_duration_s:
                    break

                frame_index = int(elapsed * 1000 // frame_ms) % num_frames
                vol = volumes[frame_index]
                y = await audio_manager.map_volume_to_y(vol, min_vol, max_vol, actual_base_y)

                await asyncio.to_thread(self.ws.set_scene_item_transform,
                    scene_name,
                    scene_item_id,
                    {
                        "positionX": actual_base_x,
                        "positionY": y,
                        "scaleX": scale_x,
                        "scaleY": scale_y
                    }
                )
                await asyncio.sleep(frame_ms / 2000)

            # Reset to original transform
            await asyncio.to_thread(self.ws.set_scene_item_transform,
                scene_name,
                scene_item_id,
                {
                    "positionX": actual_base_x,
                    "positionY": actual_base_y,
                    "scaleX": scale_x,
                    "scaleY": scale_y
                }
            )

        except asyncio.CancelledError:
            await asyncio.to_thread(self.ws.set_scene_item_transform,
                scene_name,
                scene_item_id,
                {
                    "positionX": actual_base_x,
                    "positionY": actual_base_y,
                    "scaleX": scale_x,
                    "scaleY": scale_y
                }
            )



    def disconnect(self):
        self.ws.disconnect()

#############################################