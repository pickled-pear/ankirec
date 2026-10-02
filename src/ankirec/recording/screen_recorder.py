from ..base.mixin import VerboseMixin

import threading
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from math import floor
from PIL import Image

@dataclass
class ScreenshotConfigProtocol:
    fps: int
    output_image_height_px: int
    output_dir: Path
    timestamp: str
    screenshot_time: float


@dataclass
class Screenshot:
    """Minimal screenshot metadata"""
    filepath: Path
    timestamp: float


class ScreenshotTaker(VerboseMixin):
    """Lightweight screenshot capture for Windows and Linux"""

    def __init__(self, config: ScreenshotConfigProtocol):
        super().__init__()
        self.config = config
        self.screenshots: list[Screenshot] = []
        self._backend = self._init_backend()
        self.stop_event = threading.Event()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def _init_backend(self) -> str:
        """Detect and initialise appropriate backend for OS"""
        try:
            import mss
            self.mss = mss
            return "mss"
        except ImportError:
            try:
                import PIL.ImageGrab
                self.pil_grab = PIL.ImageGrab
                return "pil"
            except ImportError:
                raise RuntimeError(
                    "No screenshot backend available. Install: pip install mss pillow"
                )

    def start(self, stop_event: threading.Event = None):
        """Start capturing screenshots at configured FPS"""
        self.debug("Screenshot Taker: Starting")
        
        # Use provided stop_event or internal one
        event = stop_event or self.stop_event
        interval = 1.0 / self.config.fps

        while not event.is_set():
            self.take_screenshot()
            time.sleep(interval)

        self.debug("Screenshot Taker: Stopped")

    def stop(self):
        """Stop taking screenshots"""
        self.debug("Screenshot Taker: Stop signal received")
        self.stop_event.set()

    def take_screenshot(self) -> Optional[Screenshot]:
        """Capture and save screenshot"""
        try:
            timestamp = time.time()
            counter = len(self.screenshots)

            # Capture
            if self._backend == "mss":
                img = self._capture_mss()
            else:
                img = self._capture_pil()

            if img is None:
                return None

            # Save raw image (minimal compression, fast)
            filepath = self._save_raw_image(img, counter)
            if filepath is None:
                return None

            screenshot = Screenshot(filepath=filepath, timestamp=timestamp)
            self.screenshots.append(screenshot)
            self.debug(f"Screenshot saved: {filepath}")

            return screenshot

        except Exception as e:
            self.debug(f"Error taking screenshot: {e}")
            return None

    def _capture_mss(self):
        """Capture using mss backend"""
        try:
            from PIL import Image
            with self.mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                return Image.frombytes(
                    'RGB',
                    (screenshot.width, screenshot.height),
                    screenshot.rgb
                )
        except Exception as e:
            self.error(f"mss capture failed: {e}")
            return None

    def _capture_pil(self):
        """Capture using PIL backend"""
        try:
            return self.pil_grab.grab()
        except Exception as e:
            self.error(f"PIL capture failed: {e}")
            return None

    def _save_raw_image(self, img, counter: int) -> Optional[Path]:
        """Save image as raw JPEG with minimal quality loss (for later processing)"""
        try:
            filename = f"{self.config.timestamp}_{int(counter)}.jpg"
            filepath = self.config.output_dir / filename
            
            # Save with high quality for later processing
            img.save(filepath, 'JPEG', quality=95)
            return filepath

        except Exception as e:
            self.error(f"Error saving screenshot: {e}")
            return None


    def _process_screenshot(self, filepath: Path) -> Path:
        """Process screenshot at the end: resize, crop to 16:9, compress"""
        try:
            img = Image.open(filepath)

            # Step 1: Resize to exact height if specified
            if self.config.output_image_height_px > 0:
                target_height = self.config.output_image_height_px
                ratio = target_height / img.height
                new_width = int(img.width * ratio)
                img = img.resize(
                    (new_width, target_height),
                    Image.Resampling.LANCZOS
                )

            # Step 2: Force 16:9 aspect ratio by cropping
            target_ratio = 16 / 9
            current_ratio = img.width / img.height

            if current_ratio > target_ratio:
                # Image too wide, crop sides
                new_width = int(img.height * target_ratio)
                crop = (img.width - new_width) // 2
                img = img.crop((crop, 0, crop + new_width, img.height))
            elif current_ratio < target_ratio:
                # Image too tall, crop top/bottom
                new_height = int(img.width / target_ratio)
                crop = (img.height - new_height) // 2
                img = img.crop((0, crop, img.width, crop + new_height))

            # Step 3: Resize to exact target height again (cropping may have changed it)
            if self.config.output_image_height_px > 0:
                target_height = self.config.output_image_height_px
                ratio = target_height / img.height
                new_width = int(img.width * ratio)
                img = img.resize(
                    (new_width, target_height),
                    Image.Resampling.LANCZOS
                )

            # Step 4: Save with compression, overwriting original
            img.save(filepath, 'JPEG', quality=75, optimize=True)

            self.debug(f"Processed: {filepath} ({img.width}×{img.height}px)")
            return filepath

        except Exception as e:
            self.error(f"Error processing screenshot: {e}")
            return filepath
        

    def get_output_screenshot(self) -> Optional[Path]:
        """Select and process screenshot for output"""
        if not self.screenshots:
            self.warning("No screenshots available")
            return None

        target_index = floor(len(self.screenshots) * self.config.screenshot_time)
        target_index = min(target_index, len(self.screenshots) - 1)

        self.debug(f"Chose screenshot {target_index} out of {len(self.screenshots)}")

        filepath = self.screenshots[target_index].filepath
        
        # Process the selected screenshot
        return self._process_screenshot(filepath)

    def get_screenshot_at_fraction(self, fraction: float) -> Optional[Screenshot]:
        """Get screenshot at time fraction"""
        if not self.screenshots:
            return None
        return self.screenshots[0] if fraction >= self.config.screenshot_time else None