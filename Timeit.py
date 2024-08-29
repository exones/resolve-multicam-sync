from enum import Enum
import DaVinciResolveScript as dvr_script
import sys
import subprocess
from datetime import timedelta, datetime
import json
import os
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk



class StartTimeSource(Enum):
    OS_FILE_CREATION_TIME = 1
    TAG_CREATION_TIME = 2

# Default params

start_time_source: StartTimeSource = StartTimeSource.TAG_CREATION_TIME
camera_property: str = "Angle"
debug: bool = False
multicam_clip_name: str = "multicam"

def get_creation_time(clip_metadata: dict, start_time_source: StartTimeSource) -> datetime:
    if start_time_source == StartTimeSource.OS_FILE_CREATION_TIME:
        return clip_metadata["os_creation_time"]
    elif start_time_source == StartTimeSource.TAG_CREATION_TIME:
        return clip_metadata["creation_time"]
    else:
        return None

def print_error(message) -> None:
    print(f"❌ [ERROR] {message}")
    messagebox.showerror("Error", message)
    
def print_info(message) -> None:
    print(f"ℹ️ [INFO ] {message}")
    messagebox.showinfo("Information", message)
    
def print_warning(message):
    print(f"⚠️ [WARN ] {message}")    
    
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

def get_clip_ffmpeg_metadata(file_path):    
    startup_info = None
    if os.name == 'nt':  # Check if the OS is Windows
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
    cmd = [
        'ffprobe', '-i', file_path, '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams'
    ]
    
    print_trace(f"Running command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startup_info)
    metadata = json.loads(result.stdout)
    return metadata

def get_clip_metadata(clip, camera_offset):
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
    creation_time = datetime.fromisoformat(creation_time_iso.replace("Z", "+00:00"))
    
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
        "creation_time": creation_time + camera_offset,        
        "os_creation_time": os_creation_time + camera_offset,
        "width": main_video_stream["width"],
        "height": main_video_stream["height"],
        "codec_name": main_video_stream["codec_name"],
        "codec_long_name": main_video_stream["codec_long_name"],        
    }
    
    return clip_metadata

def format_timecode(timecode):
    return f"{timecode['hours']:02}:{timecode['minutes']:02}:{timecode['seconds']:02}:{timecode['frames']:02}"

def get_hours_minutes_seconds_frames(total_frames: int, frame_rate: int):
    hours = total_frames // (3600 * frame_rate)
    total_frames %= int(3600 * frame_rate)
    minutes = total_frames // (60 * frame_rate)
    total_frames %= int(60 * frame_rate)
    seconds = total_frames // frame_rate
    frames = total_frames % int(frame_rate)
    
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "frames": frames,        
    }

def timedelta_to_timecode(time_delta: timedelta, frame_rate: int):
    # Total milliseconds in the timedelta
    total_milliseconds: float = time_delta.total_seconds() * 1000
    
    # Duration of one frame in milliseconds
    frame_duration_ms: float = 1000 / frame_rate
    
    # Total frames
    total_frames = int(total_milliseconds / frame_duration_ms)
    
    return get_hours_minutes_seconds_frames(total_frames, frame_rate)

def get_end_timecode(start_timecode, nb_frames, frame_rate):    
    start_hours = start_timecode["hours"]
    start_minutes = start_timecode["minutes"]
    start_seconds = start_timecode["seconds"]
    start_frames = start_timecode["frames"]
    
    total_seconds = (start_hours * 3600 + start_minutes * 60 + start_seconds)
    total_frames = total_seconds * frame_rate + start_frames + nb_frames    
    total_frames %= 3600 * frame_rate
    
    return get_hours_minutes_seconds_frames(total_frames, frame_rate)

# Create a custom dialog class
class SettingsDialog(simpledialog.Dialog):
    def body(self, master):
        self.result = None

        tk.Label(master, text="Start Time Source:").grid(row=0)
        tk.Label(master, text="Camera Property:").grid(row=1)
        tk.Label(master, text="Multicam Clip Name:").grid(row=2)
        tk.Label(master, text="Debug:").grid(row=3)

        global start_time_source
        global camera_property
        global multicam_clip_name
        global debug

        self.start_time_source_var = tk.StringVar(value=start_time_source.name)
        self.camera_property_var = tk.StringVar(value=camera_property)
        self.multicam_clip_name_var = tk.StringVar(value=multicam_clip_name)
        self.debug_var = tk.BooleanVar(value=debug)

        self.start_time_source_combobox = ttk.Combobox(master, textvariable=self.start_time_source_var, state="readonly")
        self.start_time_source_combobox['values'] = ("OS_FILE_CREATION_TIME", "TAG_CREATION_TIME")
        self.start_time_source_combobox.grid(row=0, column=1)

        self.camera_property_combobox = ttk.Combobox(master, textvariable=self.camera_property_var)
        self.camera_property_combobox['values'] = ("Camera #", "Angle")
        self.camera_property_combobox.grid(row=1, column=1)

        self.multicam_clip_name_entry = tk.Entry(master, textvariable=self.multicam_clip_name_var)
        self.multicam_clip_name_entry.grid(row=2, column=1)

        self.debug_checkbox = tk.Checkbutton(master, variable=self.debug_var)
        self.debug_checkbox.grid(row=3, column=1)

        return self.start_time_source_combobox  # initial focus

    def apply(self):
        self.result = {
            "start_time_source": self.start_time_source_var.get(),
            "camera_property": self.camera_property_var.get(),
            "multicam_clip_name": self.multicam_clip_name_var.get(),
            "debug": self.debug_var.get()
        }

def show_settings_dialog():
    # Create a dialog window
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    
    dialog = SettingsDialog(root, title="Timecode Generator Settings")
    
    return dialog.result

# get currently selected clip


resolve = dvr_script.scriptapp("Resolve")
project_manager = resolve.GetProjectManager()
current_project = project_manager.GetCurrentProject()

if (current_project == None):
    print_error("No current_project is currently open. Please open a current_project and try again.")
    exit()
    
print(f"Working with current_project '{current_project.GetName()}'")

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
for sub_folder in sub_folders.values():
    cameraIndex += 1
    clips = list(filter(is_video_file_clip, sub_folder.GetClips().values()))
    camera_name = sub_folder.GetName()    
    nb_clips_total += len(clips)
    print(f"- Camera {cameraIndex} '{camera_name}': {len(clips)} clips")
    
print(f"Total number of clips: {nb_clips_total}")
    
    
# ask the user if they want to proceed

print()
print_question("This script will analyze the clips in the selected folder and its subfolders. Do you want to proceed?")

settings = show_settings_dialog()

if (settings == None):
    print_warning("Operation cancelled by user")
    exit()

multicam_clip_name = settings["multicam_clip_name"]
start_time_source = StartTimeSource[settings["start_time_source"]]
camera_property = settings["camera_property"]
debug = settings["debug"]

# Prompt for user confirmation using tkinter


# # read user input
# if not messagebox.askyesno("Confirmation", "This script will analyze the clips in the selected folder and its subfolders. Do you want to proceed? \nDo you want to proceed?"):
#     messagebox.showinfo("Information", "Operation cancelled by user")
#     exit()

# # Prompt for user input using tkinter with default value "multicam"
# multicam_clip_name = simpledialog.askstring("Multicam name", "Enter the name of the multicam clip", initialvalue="multicam")    

root = tk.Tk()
root.withdraw()  # Hide the root window

# Create a progress bar window
progress_window = tk.Toplevel(root)
progress_window.title("Processing Clips")
progress_label = tk.Label(progress_window, text="Processing clips...")
progress_label.pack(pady=10)
progress_bar = ttk.Progressbar(progress_window, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(pady=10)
progress_window.update()

nb_clips_processed = 0

# Variable to track cancellation
cancelled = False

def cancel_processing():
    global cancelled
    cancelled = True
    progress_window.destroy()

cancel_button = tk.Button(progress_window, text="Cancel", command=cancel_processing)
cancel_button.pack(pady=10)
progress_window.update()


# class for timecode
class Timecode:
    # properties
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    frames: int = 0    
    
    def __init__(self, hours: int = 0, minutes: int = 0, seconds: int = 0, frames: int = 0):
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.frames = frames

camera_offsets = {
    'Camera1': timedelta(hours=0),
    'Camera2': timedelta(hours=12),
}

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
    
    clip_with_metadata = []
    # for each clip, get metadata and add metadata to the list
    clip_index = 0
    video_file_clips = filter(is_video_file_clip, clips)
    for clip in video_file_clips:
        clip_index += 1
        # if (clip_index == 20):
        #     break
        print_debug(f"Reading metadata for clip '{clip.GetName()}' (Camera {camera_name})")
        clip_metadata = get_clip_metadata(clip, camera_offsets[camera_name])        
        clip_record = {
            "clip": clip,
            "metadata": clip_metadata,
            "camera_name": camera_name,
        }
        clip_with_metadata.append(clip_record)
        nb_clips_processed += 1
        progress_bar["value"] = float(nb_clips_processed) / nb_clips_total * 100
        progress_label["text"] = f"Reading clips information (Camera '{camera_name}')... ({nb_clips_processed} of {nb_clips_total})"
        progress_window.update()
        
        # set camera clip property
        clip.SetClipProperty("Camera #", camera_name)                
        
        # print_debug(json.dumps*clip_record)
    cameras[camera_name] = clip_with_metadata        

# -- Find clip with earliest creation time --

creation_time_property = None
if (start_time_source == StartTimeSource.OS_FILE_CREATION_TIME):
    creation_time_property = "os_creation_time"
elif (start_time_source == StartTimeSource.TAG_CREATION_TIME):
    creation_time_property = "creation_time"

earliest_creation_time = min(clip_record["metadata"][creation_time_property] for camera in cameras.values() for clip_record in camera)            
print_debug(f"Earliest creation time {earliest_creation_time.isoformat()}")

# -- Set "Start TC" and "End TC" for all clips, as well as "Camera #" --
# Earliest clip will be the reference for the multicam clip being "00:00:00:00"
nb_clips_processed = 0
for camera in cameras.values():
    for clip_record in camera:
        clip = clip_record["clip"]
        clip_metadata = clip_record["metadata"]
        camera_name = clip_record["camera_name"]
        frame_rate = clip_metadata["frame_rate"]
        nb_frames = clip_metadata["nb_frames"]
        creation_time = get_creation_time(clip_metadata, start_time_source) 
        
        time_delta = creation_time - earliest_creation_time        
        start_timecode = timedelta_to_timecode(time_delta, frame_rate)
        end_timecode = get_end_timecode(start_timecode, nb_frames, frame_rate)
        
        start_timecode_str = format_timecode(start_timecode)
        end_timecode_str = format_timecode(end_timecode)
        
        print_debug(f"Creation time: {creation_time.isoformat()}")
        # print_debug(f"Clip '{clip.GetName()}' (Camera {camera_name}): Start TC = {start_timecode_str}, End TC = {end_timecode_str}")
        
        # end_timecode = frames_to_timecode(start_timecode, nb_frames, frame_rate)
        
        clip.SetClipProperty("Start TC", start_timecode_str)
        clip.SetClipProperty("End TC", end_timecode_str)
        clip.SetClipProperty(camera_property, camera_name) # TODO: configure which property to use for camera name (e.g. "Camera #" or "Angle")
        # clip.SetClipProperty("Angle", camera_name)
        
        print_debug(f"Clip '{clip.GetName()}' (Camera {camera_name}): Start TC = {start_timecode_str}, End TC = {end_timecode_str}")
        
        nb_clips_processed += 1
        progress_bar["value"] = float(nb_clips_processed) / nb_clips_total * 100
        progress_label["text"] = f"Setting clips time codes and angles... ({nb_clips_processed} of {nb_clips_total})"
        progress_window.update()

progress_window.destroy()