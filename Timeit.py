from enum import Enum
import DaVinciResolveScript as dvr_script
import sys
import subprocess
from datetime import timedelta, datetime
import json
import os
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import time

def print_error(message) -> None:
    print(f"❌ [ERROR] {message}")
    messagebox.showerror("Error", message)
    
def print_info(message) -> None:
    print(f"ℹ️ [INFO ] {message}")
    messagebox.showinfo("Information", message)
    
def print_warning(message):
    print(f"⚠️ [WARN ] {message}")    
    messagebox.showwarning("Warning", message)
    
def print_debug(message):
    global debug
    if (debug):
        print(f"🧪 [DEBUG] {message}")
    
def print_trace(message):
    #print(f"🔍 [TRACE] {message}")    
    pass
    
def print_question(message):
    print(f"❓")
    print(f"❓{message}")
    print(f"❓")

# --- Classes ---


try:
    class StartTimeSource(Enum):
        OS_FILE_CREATION_TIME = 1
        FORMAT_TAG_CREATION_TIME = 2

    # Default params

    start_time_source: StartTimeSource = StartTimeSource.FORMAT_TAG_CREATION_TIME
    camera_property: str = "Angle"
    show_ui: bool = True
    debug: bool = False
    multicam_clip_name: str = "multicam"
    clips_number_limit: int = 1000000
    
        
    class Timecode:
        # properties
        hours: int = 0
        minutes: int = 0
        seconds: int = 0
        frames: int = 0    
        frame_rate: float
        
        def __init__(self, frame_rate, hours: int = 0, minutes: int = 0, seconds: int = 0, frames: int = 0):        
            if (frames >= frame_rate):
                raise ValueError(f"Frames value {frames} is greater than the frame rate {frame_rate}")
            
            if not isinstance(hours, int):
                raise ValueError(f"Hours value {hours} is not an integer")
            
            if not isinstance(minutes, int):
                raise ValueError(f"Minutes value {minutes} is not an integer")
            
            if not isinstance(seconds, int):
                raise ValueError(f"Seconds value {seconds} is not an integer")
            
            if not isinstance(frames, int):
                raise ValueError(f"Frames value {frames} is not an integer")                     
            
            if (hours < 0):
                raise ValueError(f"Hours value {hours} is negative")
            
            if (minutes < 0 or minutes >= 60):
                raise ValueError(f"Minutes value {minutes} is not in the range 0-59")
            
            if (seconds < 0 or seconds >= 60):
                raise ValueError(f"Seconds value {seconds} is not in the range 0-59")
            
            if (frames < 0 or frames >= frame_rate):
                raise ValueError(f"Frames value {frames} is not in the range 0-{frame_rate - 1}")
            
            self.hours = hours
            self.minutes = minutes
            self.seconds = seconds
            self.frames = frames
            self.frame_rate = frame_rate
            
        def __add__(self, other):
            if not isinstance(other, Timecode):
                return NotImplemented        

            total_frames_self = self.to_total_frames()
            total_frames_other = other.to_total_frames()
            total_frames = total_frames_self + total_frames_other

            return self.from_total_frames(total_frames, self.frame_rate)
        
        def __sub__(self, other):
            if not isinstance(other, Timecode):
                return NotImplemented        

            total_frames_self = self.to_total_frames()
            total_frames_other = other.to_total_frames()
            total_frames = total_frames_self - total_frames_other

            return self.from_total_frames(total_frames, self.frame_rate)

        def to_total_frames(self) -> int:
            return int(self.hours * 3600 * self.frame_rate +
                    self.minutes * 60 * self.frame_rate +
                    self.seconds * self.frame_rate +
                    self.frames)

        @classmethod
        def from_total_frames(cls, total_frames: int, frame_rate: float):
            hours = int(total_frames / (3600 * frame_rate))
            total_frames %= int(3600 * frame_rate)
            minutes = int(total_frames / (60 * frame_rate))
            total_frames %= int(60 * frame_rate)
            seconds = int(total_frames / frame_rate)
            frames = total_frames % int(frame_rate)
            
            return cls(frame_rate, hours, minutes, seconds, frames)
        
        @classmethod
        def from_timecode_str(cls, timecode_str: str, frame_rate: float):
            parts = timecode_str.split(":")
            if (len(parts) != 4):
                raise ValueError(f"Invalid timecode format: {timecode_str}. Please use the format HH:MM:SS:FF")
            try:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                frames = int(parts[3])
                return cls(frame_rate, hours, minutes, seconds, frames)
            except ValueError as e:
                raise ValueError(f"Invalid timecode format: {timecode_str}. Please use the format HH:MM:SS:FF")
            
        @classmethod
        def from_timedelta(cls, time_delta: timedelta, frame_rate: float):
            # Total milliseconds in the timedelta
            total_milliseconds: float = time_delta.total_seconds() * 1000
            
            # Duration of one frame in milliseconds
            frame_duration_ms: float = 1000 / frame_rate
            
            # Total frames
            total_frames = int(total_milliseconds / frame_duration_ms)
            
            return cls.from_total_frames(total_frames, frame_rate)

        def to_timedelta(self) -> timedelta:
            total_frames = self.to_total_frames()
            total_seconds = total_frames / self.frame_rate
            
            return timedelta(seconds=total_seconds)

        def __str__(self):
            return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}:{self.frames:02d}"
    

    # --- Functions ---

    def get_creation_time(clip_metadata: dict, start_time_source: StartTimeSource) -> datetime:
        if start_time_source == StartTimeSource.OS_FILE_CREATION_TIME:
            return clip_metadata["os_creation_time"]
        elif start_time_source == StartTimeSource.FORMAT_TAG_CREATION_TIME:
            return clip_metadata["creation_time"]
        else:
            return None
    
    def get_clip_ffmpeg_metadata(file_path):    
        startup_info = None
        if os.name == 'nt':  # Check if the OS is Windows
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        # file_path = 'F:\\Footage\\2024-06-22 валентина - арман\\camera1\\CLIP\\C0001.MP4'
                    
        cmd = [
            # 'ffprobe', '-i', file_path, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams'
            'ffprobe', file_path, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams'
        ]
        
        timeout=10
        
        try:
            print_debug(f"Running command: {' '.join(cmd)}")
            
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startup_info) as proc:
                try:                
                    stdout, stderr = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    print_error(f"Timeout expired for ffprobe command on '{file_path}'")
                    return None
                
                if proc.returncode != 0:
                    print_error(f"Error running ffprobe for '{file_path}' (command '{cmd}') (exit code {proc.returncode}).\n stderr:\n{stderr}\n\nstdout:\n{stdout}")
                    return None
                
                # print_debug(f"stdout: {stdout}")
                metadata = json.loads(stdout)
                return metadata                        
        except Exception as e:
            print_error(f"Error running ffprobe for '{file_path}': {str(e)}")
            return None

    def get_clip_metadata(clip):
        clipPath = clip.GetClipProperty("File Path")
        ffmpeg_metadata = get_clip_ffmpeg_metadata(clipPath)
        
        nb_streams = ffmpeg_metadata["format"]["nb_streams"] # number of streams in the clip        
        video_streams = [stream for stream in ffmpeg_metadata["streams"] if stream["codec_type"] == "video"]
        
        if (len(video_streams) == 0):
            print_warning(f"Clip '{clip.GetName()}' does not have a video stream. Skipping this clip.")
            return None
        
        if (len(video_streams) > 1):
            print_warning(f"Clip '{clip.GetName()}' has more than one video stream. Only the first stream will be considered.")
        
        main_video_stream = video_streams[0]                            
        # file path, size, creation time etc.
        
        creation_time_iso = ffmpeg_metadata["format"]["tags"]["creation_time"]
        creation_time = datetime.fromisoformat(creation_time_iso)                        
        os_creation_timestamp = os.path.getctime(clipPath)
        os_creation_time = datetime.fromtimestamp(os_creation_timestamp)
        
        print_debug(f"Clip '{clip.GetName()}': creation time (ffmpeg) = {creation_time}, creation time (OS) = {os_creation_time}")
        
        clip_metadata = {        
            "file_path": clipPath,
            "video_stream": main_video_stream,
            "nb_streams": nb_streams,
            "size_bytes": int(ffmpeg_metadata["format"]["size"]),
            "duration_seconds": float(ffmpeg_metadata["format"]["duration"]),
            "frame_rate": int(main_video_stream["r_frame_rate"].split("/")[0]), # frame rate as integer (from 50/1 format)
            "nb_frames": int(float(main_video_stream["nb_frames"])), # number of frames as integer
            "creation_time": creation_time,        
            "os_creation_time": os_creation_time,
            "width": main_video_stream["width"],
            "height": main_video_stream["height"],
            "codec_name": main_video_stream["codec_name"],
            "codec_long_name": main_video_stream["codec_long_name"],        
        }
        
        return clip_metadata

    def get_end_timecode(start_timecode: Timecode, nb_frames: int, frame_rate: float) -> Timecode:    
        start_hours = start_timecode.hours
        start_minutes = start_timecode.minutes
        start_seconds = start_timecode.seconds
        start_frames = start_timecode.frames
        
        total_seconds = (start_hours * 3600 + start_minutes * 60 + start_seconds)
        total_frames = int(total_seconds * frame_rate + start_frames + nb_frames )
        total_frames %= 3600 * frame_rate
        
        return Timecode.from_total_frames(total_frames, frame_rate)

    # Create a custom dialog class
    class SettingsDialog(simpledialog.Dialog):        
        camera_names: list[str] = []
        
        def __init__(self, parent, title, camera_names: list[str]):
            self.camera_names = camera_names
            super().__init__(parent, title)
        
        def body(self, master):
            self.result = None

            global start_time_source
            global camera_property
            global multicam_clip_name
            global debug
            global selected_folder
            global clips_number_limit

            tk.Label(master, text=f"Folder:").grid(row=0, sticky="W")        
            tk.Label(master, text=f"{selected_folder.GetName()}").grid(row=0, column=1, sticky="W")

            # Show detected cameras as Camera1, Camera2, etc.
            tk.Label(master, text=f"Detected Cameras:").grid(row=1, sticky="W")        
            tk.Label(master, text=', '.join(self.camera_names)).grid(row=1, column=1, sticky="W")

            tk.Label(master, text="Start Time Source:").grid(row=2, sticky="W")
            tk.Label(master, text="Camera Property:").grid(row=3, sticky="W")
            tk.Label(master, text="Multicam Clip Name:").grid(row=4, sticky="W")
            tk.Label(master, text="Clips Number Limit:").grid(row=5, sticky="W")
            tk.Label(master, text="Debug:").grid(row=6, sticky="W")        

            self.start_time_source_var = tk.StringVar(value=start_time_source.name)
            self.camera_property_var = tk.StringVar(value=camera_property)
            self.multicam_clip_name_var = tk.StringVar(value=multicam_clip_name)
            self.debug_var = tk.BooleanVar(value=debug)
            self.clips_number_limit_var = tk.IntVar(value=clips_number_limit)

            self.start_time_source_combobox = ttk.Combobox(master, textvariable=self.start_time_source_var, state="readonly")
            self.start_time_source_combobox['values'] = ("OS_FILE_CREATION_TIME", "TAG_CREATION_TIME")
            self.start_time_source_combobox.grid(row=2, column=1, sticky="W")

            self.camera_property_combobox = ttk.Combobox(master, textvariable=self.camera_property_var)
            self.camera_property_combobox['values'] = ("Camera #", "Angle")
            self.camera_property_combobox.grid(row=3, column=1, sticky="W")

            self.multicam_clip_name_entry = tk.Entry(master, textvariable=self.multicam_clip_name_var)
            self.multicam_clip_name_entry.grid(row=4, column=1, sticky="W")
            
            self.clips_number_limit_entry = tk.Entry(master, textvariable=self.clips_number_limit_var)
            self.clips_number_limit_entry.grid(row=5, column=1, sticky="W")

            self.debug_checkbox = tk.Checkbutton(master, variable=self.debug_var)
            self.debug_checkbox.grid(row=6, column=1, sticky="W")

            return self.start_time_source_combobox  # initial focus

        def apply(self):
            self.result = {
                "start_time_source": self.start_time_source_var.get(),
                "camera_property": self.camera_property_var.get(),
                "multicam_clip_name": self.multicam_clip_name_var.get(),
                "clips_number_limit": self.clips_number_limit_var.get(),
                "debug": self.debug_var.get()
            }

    root = tk.Tk()
    root.withdraw()  # Hide the root window

    def show_settings_dialog(camera_names: list[str]) -> dict:
        # Create a dialog window
        global root
        
        dialog_result = None
        dialog = SettingsDialog(root, title="Timecode Generator Settings", camera_names = camera_names)
        try:            
            dialog.update_idletasks()            
            dialog_result = dialog.result            
        finally:
            dialog.destroy()
            
        return dialog_result

    # get currently selected clip
    resolve = dvr_script.scriptapp("Resolve")
    project_manager = resolve.GetProjectManager()
    current_project = project_manager.GetCurrentProject()

    if (current_project == None):
        print_error("No current_project is currently open. Please open a current_project and try again.")
        exit()
        
    print(f"Working with current_project '{current_project.GetName()}'")
    current_project_framerate = current_project.GetSetting("timelineFrameRate")
    print(f"Current project frame rate: {current_project_framerate}")

    current_page = resolve.GetCurrentPage()
    selected_folder = None

    media_pool = current_project.GetMediaPool()
    selected_folder = media_pool.GetCurrentFolder()

    if (selected_folder == None):
        print_error("Multiple folders selected: please select only one folder with subfolders representing the clips for each camera. E.g. footage/Camera1, footage/Camera2, etc.")
        exit()
        
    print(f"Currently selected folder: '{selected_folder.GetName()}'")

    sub_folders = selected_folder.GetSubFolders()

    if (len(sub_folders) == 0):
        print_error("No subfolders found in the selected folder. Please select a folder with subfolders representing the clips for each camera. E.g. footage/Camera1, footage/Camera2, etc.")
        exit()  

    print(f"Found {len(sub_folders)} subfolders: will consider each subfolder a camera subfolder:")

    # definition of a dictionary of clips per camera
    # key: camera name
    # value: list of clips with metadata

    def is_video_file_clip(clip):
        return "Video" in clip.GetClipProperty("Type")

    nb_clips_total = 0
    cameraIndex = 0
    camera_names = []
    for sub_folder in sub_folders.values():
        cameraIndex += 1
        clips = list(filter(is_video_file_clip, sub_folder.GetClips().values()))
        camera_name = sub_folder.GetName()    
        camera_names.append(camera_name)
        nb_clips_total += len(clips)
        print(f"- Camera {cameraIndex} '{camera_name}': {len(clips)} clips")
        
    print(f"Total number of clips: {nb_clips_total}")
        
    if (True): # ask for settings
        # ask the user if they want to proceed and show settings dialog
        settings = show_settings_dialog(camera_names)

        if (settings == None):
            print_warning("Operation cancelled by user")
            exit()

        multicam_clip_name = settings["multicam_clip_name"]
        start_time_source = StartTimeSource[settings["start_time_source"]]
        camera_property = settings["camera_property"]
        debug = settings["debug"]
        clips_number_limit = settings["clips_number_limit"]

    # Prompt for user confirmation using tkinter


    # # read user input
    # if not messagebox.askyesno("Confirmation", "This script will analyze the clips in the selected folder and its subfolders. Do you want to proceed? \nDo you want to proceed?"):
    #     messagebox.showinfo("Information", "Operation cancelled by user")
    #     exit()

    # # Prompt for user input using tkinter with default value "multicam"
    # multicam_clip_name = simpledialog.askstring("Multicam name", "Enter the name of the multicam clip", initialvalue="multicam")    

    cancelled = False
    nb_clips_processed = 0
    progress_bar = None
    progress_label = None
    progress_window = None
        
    if (True):
        # # Create a progress bar window
        progress_window = tk.Toplevel(root)
        progress_window.title("Processing Clips")
        progress_label = tk.Label(progress_window, text="Processing clips...")
        progress_label.pack(pady=10)
        progress_bar = ttk.Progressbar(progress_window, orient="horizontal", length=300, mode="determinate")
        progress_bar.pack(pady=10)

        def cancel_processing():
            global cancelled
            cancelled = True
            progress_window.destroy()

        cancel_button = tk.Button(progress_window, text="Cancel", command=cancel_processing)
        cancel_button.pack(pady=10)
        progress_window.update()

    def update_progress_bar(value: float | int, text):                        
        global show_ui
        if (True):            
            global progress_bar
            global progress_window
            global progress_label
            
            progress_bar["value"] = int(value)
            progress_label["text"] = text
            progress_bar.update_idletasks()
            progress_label.update_idletasks()
            progress_window.update()

    # class for timecode

    creation_time_property = None
    if (start_time_source == StartTimeSource.OS_FILE_CREATION_TIME):
        creation_time_property = "os_creation_time"
    elif (start_time_source == StartTimeSource.FORMAT_TAG_CREATION_TIME):
        creation_time_property = "creation_time"

    # --- Obtain clips metadata per camera ---
    cameras = {}
    cameraIndex = 0    
    for sub_folder in sub_folders.values():
        if cancelled:
            print_warning("Processing cancelled by user.")
            break
        cameraIndex += 1
        clips = sub_folder.GetClips().values()
        camera_name = sub_folder.GetName()    
        print(f"- Camera {cameraIndex} '{camera_name}': {len(clips)} clips")            
        
        clips_with_metadata = []
        # for each clip, get metadata and add metadata to the list
        clip_index = 0
        video_file_clips = list(filter(is_video_file_clip, clips))
        
        if (video_file_clips == None or len(video_file_clips) == 0):
            print_warning(f"No video file clips found in camera '{camera_name}'. Skipping this camera.")
            continue
        
        minimum_creation_time = None
        minimum_creation_time_clip = None
        
        for clip in video_file_clips:
            clip_index += 1
            if (clip_index > clips_number_limit):
                print_debug(f"Number of clips for camera '{camera_name}' exceeds the limit of {clips_number_limit}. Skipping the rest of the clips.")
                break
            print_debug(f"Reading metadata for clip '{clip.GetName()}' (Camera {camera_name})")
            clip_metadata = get_clip_metadata(clip)
            clip_record = {
                "clip": clip,
                "metadata": clip_metadata,
                "camera_name": camera_name,
            }
            clips_with_metadata.append(clip_record)
            nb_clips_processed += 1
            
            update_progress_bar(float(nb_clips_processed) / nb_clips_total * 100, f"Reading clips information (Camera '{camera_name}')... ({nb_clips_processed} of {nb_clips_total})")
            
            creation_time = get_creation_time(clip_metadata, start_time_source)
            
            if (minimum_creation_time == None or creation_time < minimum_creation_time):
                minimum_creation_time = creation_time
                minimum_creation_time_clip = clip_record                            
            
            # print_debug(json.dumps*clip_record)
        cameras[camera_name] = {
            'clips': clips_with_metadata,
            'minimum_creation_time': minimum_creation_time,
            'minimum_creation_time_clip': minimum_creation_time_clip,
            'offset': Timecode(current_project_framerate, 0, 0, 0, 0),
        } 

    zero_creation_time = min([camera["minimum_creation_time"] for camera in cameras.values()])

    # -- Calculate default camera offsets considering they all started recording roughly at the same time --
    for camera in cameras.values():        
        camera_earliest_creation_time = camera["minimum_creation_time"]
        offset_time_delta = camera_earliest_creation_time - zero_creation_time
        offset_timecode = Timecode.from_timedelta(offset_time_delta, current_project_framerate)
        
        print_debug(f"Camera '{camera_name}': earliest creation time = {camera_earliest_creation_time}, offset time  = {offset_time_delta}, offset timecode = {offset_timecode}")
        
        camera["offset"] = offset_timecode
        
    class CameraOffsetsDialog(simpledialog.Dialog):
        cameras: dict = {}
        
        def __init__(self, parent, title, cameras: dict):
            self.cameras = cameras
            super().__init__(parent, title)
            
        def body(self, master):
            self.result = None
            
            tk.Label(master, text="Camera").grid(row=0, column=0)
            tk.Label(master, text="Offset").grid(row=0, column=1)
            
            self.camera_offset_entries = {}
            
            row_index = 1
            for camera_name, camera in self.cameras.items():
                tk.Label(master, text=camera_name).grid(row=row_index, column=0)
                self.camera_offset_entries[camera_name] = tk.Entry(master)
                
                self.camera_offset_entries[camera_name].grid(row=row_index, column=1)
                self.camera_offset_entries[camera_name].insert(0, str(camera["offset"]))
                row_index += 1
                
            return self.camera_offset_entries[camera_name] # initial focus
        
        def apply(self) -> None:
            global current_project_framerate
            self.result = {}
            for camera_name, camera in self.cameras.items():
                offset_str = self.camera_offset_entries[camera_name].get()
                
                try:
                    self.result[camera_name] = Timecode.from_timecode_str(offset_str, current_project_framerate)
                except ValueError as e:
                    print_error(f"Invalid timecode format for camera '{camera_name}': {offset_str}. Please use the format HH:MM:SS:FF")
                    return                        
    
    update_progress_bar(float(0), f"Waiting for user input... ({nb_clips_processed} of {nb_clips_total})")        
        
    def show_dialog_with_editable_camera_offsets(cameras: dict) -> dict:
        if (show_ui):
            # Create a dialog window
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            
            dialog_result = None
            try:
                dialog = CameraOffsetsDialog(root, title="Camera Offsets", cameras = cameras)
                dialog.update_idletasks()
                
                dialog_result = dialog.result

                
            finally:
                root.destroy()
            return dialog_result

    camera_offsets = {}

    if (show_ui):
        camera_offsets = show_dialog_with_editable_camera_offsets(cameras)
        
        for camera_name, camera_offset in camera_offsets.items():
            cameras[camera_name]["offset"] = camera_offset
    else:
        camera_offsets = map(lambda camera: camera["offset"], cameras.values())
        
    if (camera_offsets == None):
        print_warning("Operation cancelled by user")
        exit()
    
    progress_bar["mode"] = "determinate"
    progress_window.update_idletasks()

    # -- Set "Start TC" and "End TC" for all clips, as well as "Camera #" --
    # Earliest clip will be the reference for the multicam clip being "00:00:00:00"
    nb_clips_processed = 0
    for camera in cameras.values():
        camera_clips = camera["clips"]
        for clip_record in camera_clips:
            clip = clip_record["clip"]
            clip_metadata = clip_record["metadata"]
            camera_name = clip_record["camera_name"]
            frame_rate = clip_metadata["frame_rate"]
            nb_frames = clip_metadata["nb_frames"]
            camera_offset: Timecode = camera["offset"]
            
            clip_creation_time = get_creation_time(clip_metadata, start_time_source)            
            camera_offset_time_delta = camera_offset.to_timedelta()
            adjusted_clip_creation_time = clip_creation_time - camera_offset_time_delta
                        
            time_delta = adjusted_clip_creation_time - zero_creation_time
            start_timecode = Timecode.from_timedelta(time_delta, current_project_framerate)            
            
            print_debug(f"Clip '{clip.GetName()}' (Camera {camera_name}): creation time = {clip_creation_time}")
            print_debug(f"  clip creation time = {clip_creation_time}")
            print_debug(f"  camera offset time delta = {camera_offset_time_delta}")
            print_debug(f"  adjusted clip creation time = {adjusted_clip_creation_time}")    
            print_debug(f"  time delta = {time_delta}")
            print_debug(f"  start timecode = {start_timecode}")
                                
            # end_timecode = get_end_timecode(start_timecode, nb_frames, current_project_framerate)                    
            # print_debug(f"Clip '{clip.GetName()}' (Camera {camera_name}): Start TC = {start_timecode_str}, End TC = {end_timecode_str}")            
            # end_timecode = frames_to_timecode(start_timecode, nb_frames, frame_rate)
            
            clip.SetClipProperty("Start TC", str(start_timecode))
            # clip.SetClipProperty("End TC", str(end_timecode))
            clip.SetClipProperty(camera_property, camera_name) # TODO: configure which property to use for camera name (e.g. "Camera #" or "Angle")
            # clip.SetClipProperty("Angle", camera_name)
            
            # print_debug(f"Clip '{clip.GetName()}' (Camera {camera_name}): Start TC = {start_timecode}, End TC = {end_timecode}")
            
            nb_clips_processed += 1            
            
            update_progress_bar(float(nb_clips_processed) / nb_clips_total * 100, f"Setting clips time codes and angles... ({nb_clips_processed} of {nb_clips_total})")
            
    progress_window.destroy()
    messagebox.showinfo("Information", "Time codes and camera names have been set for all clips.")
    
except Exception as e:
    print_error(str(e))
    raise e