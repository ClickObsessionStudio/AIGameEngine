#!/usr/bin/env python3
"""
AI Video Editor and Clipper
Author: AI Assistant
Description: Automatically clips long videos into shorts with captions and thumbnails
Dependencies: ffmpeg, whisper
"""

import os
import subprocess
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import whisper
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_editor.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class VideoClip:
    """Data class to represent a video clip with metadata"""
    file_path: str
    start_time: float
    duration: float
    title: str
    description: str
    tags: List[str]
    enhanced_path: Optional[str] = None
    thumbnail_path: Optional[str] = None

class ConfigManager:
    """Manages configuration for the video editor"""
    
    def __init__(self, config_file: str = "video_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file or create default config"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            # Create default configuration
            default_config = {
                "video_settings": {
                    "clip_duration": 12,
                    "overlap_seconds": 2,
                    "max_clips": 20,
                    "output_resolution": "1080:1920",
                    "video_quality": 18
                },
                "caption_settings": {
                    "font_size": 24,
                    "font_color": "white",
                    "outline_color": "black",
                    "outline_width": 2,
                    "enable_captions": True
                },
                "output_settings": {
                    "create_thumbnails": True,
                    "output_format": "mp4",
                    "preserve_audio": True
                }
            }
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
    
    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation"""
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except KeyError:
            return default

class VideoProcessor:
    """Handles video processing, clipping, and enhancement operations"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.whisper_model = None
        self.temp_dir = Path("temp_clips")
        self.temp_dir.mkdir(exist_ok=True)
    
    def get_video_info(self, video_path: str) -> Dict:
        """Extract video information using ffprobe"""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json", 
            "-show_format", "-show_streams", video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            # Extract relevant information
            video_stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
            duration = float(info['format']['duration'])
            
            return {
                'duration': duration,
                'width': int(video_stream['width']),
                'height': int(video_stream['height']),
                'fps': eval(video_stream['r_frame_rate']),
                'codec': video_stream['codec_name']
            }
        except subprocess.CalledProcessError as e:
            logging.error(f"Error getting video info: {e}")
            raise
    
    def generate_clips(self, video_path: str, output_dir: str = "clips") -> List[VideoClip]:
        """Generate multiple clips from a long video using intelligent segmentation"""
        logging.info(f"Starting clip generation from {video_path}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Get video information
        video_info = self.get_video_info(video_path)
        duration = video_info['duration']
        
        logging.info(f"Video duration: {duration:.2f} seconds")
        logging.info(f"Video resolution: {video_info['width']}x{video_info['height']}")
        
        # Configuration from config manager
        clip_duration = self.config.get('video_settings.clip_duration', 12)
        overlap = self.config.get('video_settings.overlap_seconds', 2)
        max_clips = self.config.get('video_settings.max_clips', 20)
        resolution = self.config.get('video_settings.output_resolution', '1080:1920')
        
        # Generate intelligent clip segments
        segments = self._find_interesting_segments(video_path, duration, clip_duration, overlap)
        
        clips = []
        for i, (start_time, end_time) in enumerate(segments[:max_clips]):
            output_file = os.path.join(output_dir, f"clip_{i:03d}_{int(start_time)}s.mp4")
            
            # Create clip with ffmpeg
            success = self._create_clip(
                video_path, output_file, start_time, 
                end_time - start_time, resolution
            )
            
            if success:
                # Generate metadata for the clip
                title = self._generate_clip_title(i, start_time)
                description = self._generate_clip_description(video_path, start_time)
                tags = self._generate_tags(description)
                
                clip = VideoClip(
                    file_path=output_file,
                    start_time=start_time,
                    duration=end_time - start_time,
                    title=title,
                    description=description,
                    tags=tags
                )
                clips.append(clip)
                logging.info(f"Created clip {i+1}: {output_file}")
        
        logging.info(f"Generated {len(clips)} clips successfully")
        return clips
    
    def _find_interesting_segments(self, video_path: str, duration: float, 
                                   clip_duration: float, overlap: float) -> List[Tuple[float, float]]:
        """Find interesting segments in the video using intelligent spacing"""
        segments = []
        current_time = 0
        step = clip_duration - overlap
        
        # Calculate optimal number of clips based on video length
        max_possible_clips = int((duration - clip_duration) / step) + 1
        actual_clips = min(max_possible_clips, 20)
        
        logging.info(f"Planning to create {actual_clips} clips from {duration:.1f}s video")
        
        # If video is short, create fewer clips with less overlap
        if duration < 120:  # Less than 2 minutes
            step = max(clip_duration * 0.5, duration / min(actual_clips, 5))
        
        while current_time + clip_duration <= duration and len(segments) < actual_clips:
            # Add some variance to avoid mechanical cuts
            start_variance = min(1.0, step * 0.1)
            actual_start = current_time + (start_variance * (len(segments) % 3 - 1))
            actual_start = max(0, actual_start)  # Don't go negative
            
            # Ensure we don't exceed video duration
            if actual_start + clip_duration <= duration:
                segments.append((actual_start, actual_start + clip_duration))
            
            current_time += step
        
        return segments
    
    def _create_clip(self, input_path: str, output_path: str, start_time: float, 
                     duration: float, resolution: str) -> bool:
        """Create a single clip using ffmpeg"""
        quality = self.config.get('video_settings.video_quality', 18)
        preserve_audio = self.config.get('output_settings.preserve_audio', True)
        
        # Build ffmpeg command
        cmd = [
            "ffmpeg", "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-vf", f"scale={resolution}:force_original_aspect_ratio=increase,crop={resolution}",
            "-c:v", "libx264", "-crf", str(quality),
        ]
        
        if preserve_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.append("-an")  # No audio
        
        cmd.extend([
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            "-y", output_path
        ])
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error creating clip {output_path}: {e}")
            if e.stderr:
                logging.error(f"FFmpeg stderr: {e.stderr}")
            return False
    
    def add_captions(self, clips: List[VideoClip]) -> List[VideoClip]:
        """Add captions to all clips using Whisper"""
        if not self.config.get('caption_settings.enable_captions', True):
            logging.info("Captions disabled in configuration")
            return clips
            
        logging.info("Adding captions to clips")
        
        if self.whisper_model is None:
            logging.info("Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")
        
        enhanced_clips = []
        for clip in clips:
            try:
                enhanced_path = self._add_captions_to_clip(clip)
                clip.enhanced_path = enhanced_path
                enhanced_clips.append(clip)
                logging.info(f"Added captions to {clip.file_path}")
            except Exception as e:
                logging.error(f"Error adding captions to {clip.file_path}: {e}")
                # Keep original clip if captioning fails
                enhanced_clips.append(clip)
        
        return enhanced_clips
    
    def _add_captions_to_clip(self, clip: VideoClip) -> str:
        """Add captions to a single clip"""
        # Transcribe audio
        result = self.whisper_model.transcribe(clip.file_path)
        
        # Create SRT file
        srt_content = self._create_srt_content(result['segments'])
        srt_file = clip.file_path.replace(".mp4", ".srt")
        
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
        
        # Add captions to video
        enhanced_path = clip.file_path.replace(".mp4", "_captioned.mp4")
        
        # Caption styling from config
        font_size = self.config.get('caption_settings.font_size', 24)
        font_color = self.config.get('caption_settings.font_color', 'white')
        outline_color = self.config.get('caption_settings.outline_color', 'black')
        outline_width = self.config.get('caption_settings.outline_width', 2)
        
        cmd = [
            "ffmpeg", "-i", clip.file_path,
            "-vf", f"subtitles={srt_file}:force_style='Fontsize={font_size},PrimaryColour=&H{font_color},OutlineColour=&H{outline_color},Outline={outline_width}'",
            "-c:a", "copy", "-y", enhanced_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return enhanced_path
    
    def _create_srt_content(self, segments: List[Dict]) -> str:
        """Create SRT subtitle content from Whisper segments"""
        srt_content = ""
        for i, segment in enumerate(segments):
            start_time = self._format_srt_time(segment["start"])
            end_time = self._format_srt_time(segment["end"])
            text = segment["text"].strip()
            
            srt_content += f"{i+1}\n{start_time} --> {end_time}\n{text}\n\n"
        
        return srt_content
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace('.', ',')
    
    def _generate_clip_title(self, index: int, start_time: float) -> str:
        """Generate engaging title for clip"""
        titles = [
            f"Clip {index + 1} - {int(start_time//60)}:{int(start_time%60):02d}",
            f"Moment {index + 1}",
            f"Scene {index + 1}",
            f"Part {index + 1}",
            f"Segment {index + 1}"
        ]
        return titles[index % len(titles)]
    
    def _generate_clip_description(self, video_path: str, start_time: float) -> str:
        """Generate description for clip"""
        video_name = Path(video_path).stem
        return f"Clip from {video_name} starting at {int(start_time//60)}:{int(start_time%60):02d}"
    
    def _generate_tags(self, description: str) -> List[str]:
        """Generate relevant tags for the clip"""
        base_tags = ["clip", "short", "video", "segment"]
        # Simple keyword extraction from description
        words = description.lower().split()
        content_tags = [word.strip('.,!?') for word in words if len(word) > 3][:3]
        return base_tags + content_tags
    
    def create_thumbnails(self, clips: List[VideoClip]) -> List[VideoClip]:
        """Create thumbnails for all clips"""
        if not self.config.get('output_settings.create_thumbnails', True):
            logging.info("Thumbnail creation disabled")
            return clips
            
        logging.info("Creating thumbnails for clips")
        
        for clip in clips:
            try:
                thumbnail_path = clip.file_path.replace(".mp4", "_thumb.jpg")
                # Take thumbnail from middle of clip for better representation
                thumb_time = clip.duration / 2
                cmd = [
                    "ffmpeg", "-i", clip.file_path, "-ss", str(thumb_time),
                    "-vframes", "1", "-q:v", "2", "-y", thumbnail_path
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                clip.thumbnail_path = thumbnail_path
                logging.info(f"Created thumbnail: {thumbnail_path}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error creating thumbnail for {clip.file_path}: {e}")
        
        return clips

class VideoEditorApp:
    """Main application class for video editing and clipping"""
    
    def __init__(self, config_file: str = "video_config.json"):
        self.config = ConfigManager(config_file)
        self.processor = VideoProcessor(self.config)
        
        logging.info("Video Editor App initialized")
    
    def process_video(self, video_path: str, output_dir: str = "clips") -> Dict:
        """Main method to process a video and create clips"""
        try:
            logging.info(f"Starting video processing for {video_path}")
            
            # Validate input
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Step 1: Generate clips from video
            logging.info("Step 1: Generating clips")
            clips = self.processor.generate_clips(video_path, output_dir)
            
            if not clips:
                raise ValueError("No clips were generated from the video")
            
            # Step 2: Add captions to clips (if enabled)
            if self.config.get('caption_settings.enable_captions', True):
                logging.info("Step 2: Adding captions")
                clips = self.processor.add_captions(clips)
            else:
                logging.info("Step 2: Skipping captions (disabled)")
            
            # Step 3: Create thumbnails (if enabled)
            if self.config.get('output_settings.create_thumbnails', True):
                logging.info("Step 3: Creating thumbnails")
                clips = self.processor.create_thumbnails(clips)
            else:
                logging.info("Step 3: Skipping thumbnails (disabled)")
            
            # Compile results
            results = {
                'status': 'success',
                'clips_generated': len(clips),
                'output_directory': output_dir,
                'clips': []
            }
            
            for clip in clips:
                clip_info = {
                    'file_path': clip.file_path,
                    'enhanced_path': clip.enhanced_path,
                    'thumbnail_path': clip.thumbnail_path,
                    'title': clip.title,
                    'start_time': clip.start_time,
                    'duration': clip.duration,
                    'file_size_mb': round(os.path.getsize(clip.file_path) / (1024*1024), 2) if os.path.exists(clip.file_path) else 0
                }
                results['clips'].append(clip_info)
            
            logging.info(f"Video processing completed successfully. Generated {len(clips)} clips in {output_dir}")
            return results
            
        except Exception as e:
            logging.error(f"Error processing video {video_path}: {str(e)}")
            logging.error(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e),
                'clips_generated': 0
            }
    
    def get_video_info(self, video_path: str) -> Dict:
        """Get detailed information about a video file"""
        try:
            return self.processor.get_video_info(video_path)
        except Exception as e:
            logging.error(f"Error getting video info: {e}")
            return {'error': str(e)}
    
    def update_config(self, updates: Dict):
        """Update configuration settings"""
        def update_nested_dict(original, updates):
            for key, value in updates.items():
                if isinstance(value, dict) and key in original:
                    update_nested_dict(original[key], value)
                else:
                    original[key] = value
        
        update_nested_dict(self.config.config, updates)
        self.config.save_config(self.config.config)
        logging.info("Configuration updated")
    
    def show_config(self):
        """Display current configuration"""
        print("\n" + "="*50)
        print("         VIDEO EDITOR CONFIGURATION")
        print("="*50)
        
        # Video settings
        print("\nVIDEO SETTINGS:")
        print(f"  Clip Duration: {self.config.get('video_settings.clip_duration', 12)} seconds")
        print(f"  Max Clips: {self.config.get('video_settings.max_clips', 20)}")
        print(f"  Video Quality: {self.config.get('video_settings.video_quality', 18)} CRF")
        print(f"  Output Resolution: {self.config.get('video_settings.output_resolution', '1080:1920')}")
        
        # Caption settings
        print("\nCAPTION SETTINGS:")
        print(f"  Enable Captions: {self.config.get('caption_settings.enable_captions', True)}")
        print(f"  Font Size: {self.config.get('caption_settings.font_size', 24)}")
        print(f"  Font Color: {self.config.get('caption_settings.font_color', 'white')}")
        
        # Output settings
        print("\nOUTPUT SETTINGS:")
        print(f"  Create Thumbnails: {self.config.get('output_settings.create_thumbnails', True)}")
        print(f"  Output Format: {self.config.get('output_settings.output_format', 'mp4')}")
        print(f"  Preserve Audio: {self.config.get('output_settings.preserve_audio', True)}")

def check_dependencies() -> List[str]:
    """Check if all required dependencies are available"""
    missing = []
    
    # Check FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("ffmpeg")
    
    # Check ffprobe
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("ffprobe")
    
    # Check Python packages
    required_packages = ['whisper']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(f"python package: {package}")
    
    return missing

def setup_directories():
    """Create necessary directories"""
    directories = ['clips', 'temp_clips', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def is_notebook_environment():
    """Check if running in Jupyter notebook"""
    try:
        get_ipython
        return True
    except NameError:
        return False

# VIDEO FILE PATH - PUT YOUR VIDEO HERE
VIDEO_PATH = "ssvid.net--Journey-Through-Switzerland-2-Minutes-Cinematic-Travel-Video_v720P.mp4"  # <- Change this to your video file path

# For Jupyter notebook usage
def create_video_editor(config_file: str = "video_config.json") -> VideoEditorApp:
    """Convenience function to create video editor instance in notebooks"""
    return VideoEditorApp(config_file)

def quick_process(video_path: str = None) -> Dict:
    """Quick function to process video with default settings"""
    if video_path is None:
        video_path = VIDEO_PATH
    
    editor = VideoEditorApp()
    return editor.process_video(video_path)

def main():
    """Main entry point for the application"""
    
    # Check if running in notebook environment
    if is_notebook_environment():
        print("Video Editor detected Jupyter environment")
        print("Use the VideoEditorApp class directly:")
        print("editor = VideoEditorApp()")
        print("result = editor.process_video('your_video.mp4')")
        return
    
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Video Editor and Clipper')
    parser.add_argument('video_path', nargs='?', help='Path to the input video file')
    parser.add_argument('--output-dir', default='clips', help='Output directory for clips')
    parser.add_argument('--config', default='video_config.json', help='Configuration file path')
    parser.add_argument('--info', action='store_true', help='Show video information')
    parser.add_argument('--show-config', action='store_true', help='Show current configuration')
    
    # Filter out Jupyter kernel arguments
    filtered_args = []
    skip_next = False
    
    for i, arg in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if arg in ['-f', '--kernel']:
            skip_next = True
            continue
        if arg.startswith('--kernel=') or arg.startswith('-f='):
            continue
        filtered_args.append(arg)
    
    args = parser.parse_args(filtered_args)
    
    # Initialize app
    editor = VideoEditorApp(args.config)
    
    # Handle configuration display
    if args.show_config:
        editor.show_config()
        return
    
    # Require video path for other operations
    if not args.video_path:
        print("\nUsage: python video_editor.py <video_path> [options]")
        print("Use --show-config to see current settings")
        return
    
    if not os.path.exists(args.video_path):
        print(f"Error: Video file {args.video_path} not found")
        return
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print("Missing dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install missing dependencies before running.")
        return
    
    # Setup directories
    setup_directories()
    
    if args.info:
        # Show video information
        info = editor.get_video_info(args.video_path)
        print(f"\nVideo Information for: {args.video_path}")
        print("="*50)
        for key, value in info.items():
            print(f"{key.capitalize()}: {value}")
    else:
        # Process video
        print(f"Processing video: {args.video_path}")
        result = editor.process_video(args.video_path, args.output_dir)
        
        if result['status'] == 'success':
            print(f"\nSuccess! Generated {result['clips_generated']} clips")
            print(f"Output directory: {result['output_directory']}")
            print("\nGenerated clips:")
            for clip in result['clips']:
                print(f"  - {clip['file_path']} ({clip['file_size_mb']} MB)")
        else:
            print(f"Error: {result['error']}")

if __name__ == "__main__":
    main()
    
    
    
# Super easy - just run this:
result = quick_process()

# Or specify a different video:
result = quick_process("another_video.mp4")

# Or use the original way:
editor = VideoEditorApp()
result = editor.process_video(VIDEO_PATH)