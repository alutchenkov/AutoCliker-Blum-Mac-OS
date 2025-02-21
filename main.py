import os
import time
import random
import math
import cv2
import pynput
import pyautogui
import mss
import numpy as np
import config
import Quartz
import AppKit

def get_window_list():
    window_list = []
    window_info_list = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
    for window_info in window_info_list:
        window_list.append(window_info)
    return window_list

def get_window_by_title(title_keywords):
    all_windows = get_window_list()
    filtered_windows = []
    for window in all_windows:
        for keyword in title_keywords:
            if keyword.lower() in window.get('kCGWindowName', 'No Title').lower():
                filtered_windows.append(window)
    return filtered_windows

def get_active_window_by_pid(pid):
    # Get the list of all windows on the screen
    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)

    # Filter windows by owner PID
    windows_by_pid = [window for window in window_list if window['kCGWindowOwnerPID'] == pid]

    if not windows_by_pid:
        print(f"No windows found for PID {pid}")
        return None

    # Typically, the active window has the lowest layer value (usually 0 or 1)
    # Sort windows by layer (lower layer indicates a window closer to the foreground)
    active_window = min(windows_by_pid, key=lambda w: w['kCGWindowLayer'])

    return active_window

def scroll_window(scroll_y=0, scroll_x=0):
    # Create a scroll event
    scroll_event = Quartz.CGEventCreateScrollWheelEvent(
        None,                # No source
        Quartz.kCGScrollEventUnitPixel,  # Scroll by pixels
        2,                   # Number of dimensions (2D: x and y)
        scroll_y,            # Vertical scroll amount
        scroll_x             # Horizontal scroll amount
    )

    # Post the event to the system
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, scroll_event)

def move_mouse(x, y):
    # Create a mouse move event
    move_event = Quartz.CoreGraphics.CGEventCreateMouseEvent(
        None,                          # No source
        Quartz.CoreGraphics.kCGEventMouseMoved,         # Event type: mouse moved
        (x, y),                        # Destination (x, y) coordinates
        Quartz.CoreGraphics.kCGMouseButtonLeft          # Mouse button (left in this case)
    )

    # Post the event to the system
    Quartz.CoreGraphics.CGEventPost(Quartz.CoreGraphics.kCGHIDEventTap, move_event)

def send_global_click(x, y):
    # Create a mouse down event at the specified (x, y) coordinates
    mouse_down = Quartz.CoreGraphics.CGEventCreateMouseEvent(
        None,                             # No specific event source
        Quartz.CoreGraphics.kCGEventLeftMouseDown,         # Left mouse button down
        (x, y),                           # Position to click
        Quartz.CoreGraphics.kCGMouseButtonLeft             # Left mouse button
    )

    # Create a mouse up event at the same (x, y) coordinates
    mouse_up = Quartz.CoreGraphics.CGEventCreateMouseEvent(
        None,                             # No specific event source
        Quartz.CoreGraphics.kCGEventLeftMouseUp,           # Left mouse button up
        (x, y),                           # Position to release click
        Quartz.CoreGraphics.kCGMouseButtonLeft             # Left mouse button
    )

    # Post the events to the system (global click)
    Quartz.CoreGraphics.CGEventPost(Quartz.CoreGraphics.kCGHIDEventTap, mouse_down)
    Quartz.CoreGraphics.CGEventPost(Quartz.CoreGraphics.kCGHIDEventTap, mouse_up)


def get_retina_scaling_factor():
    return 2

class AutoClicker:
    def __init__(self, window, target_colors_hex, threshold):
        self.window = window
        self.target_colors_hex = target_colors_hex
        self.threshold = threshold
        self.running = False
        self.clicked_points = []
        self.iteration_count = 0
        self.last_check_time = time.time()
        self.game_start_time = None
        self.target_hsvs = [self.hex_to_hsv(color) for color in self.target_colors_hex]

    @staticmethod
    def hex_to_hsv(hex_color):
        hex_color = hex_color.lstrip('#')
        h_len = len(hex_color)
        rgb = tuple(int(hex_color[i:i + h_len // 3], 16) for i in range(0, h_len, h_len // 3))
        rgb_normalized = np.array([[rgb]], dtype=np.uint8)
        hsv = cv2.cvtColor(rgb_normalized, cv2.COLOR_RGB2HSV)
        return hsv[0][0]

    @staticmethod
    def click_at(x, y):
        try:
            send_global_click(x, y)
        except Exception as e:
            print(f"Exception while clicking: {e}")

    def toggle_script(self, key):
        if key == pynput.keyboard.Key.f6:
            self.running = not self.running
            if self.running:
                self.game_start_time = None
                print('Script started. Looking for the Play button')
            else:
                print('Script stopped.')

    def check_and_click_play_button(self, sct, blumWindowBounds):
        current_time = time.time()
        if current_time - self.last_check_time >= random.uniform(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX):
            self.last_check_time = current_time
            
            img = np.array(sct.grab(blumWindowBounds))
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

            templates = [
                cv2.imread(os.path.join("template_png", "template_play_button5.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button2.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button4.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button3.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button1.png"), cv2.IMREAD_GRAYSCALE)
            ]

            for template in templates:
                if template is None:
                    print("Unable to load template.")
                    continue

                template_height, template_width = template.shape

                res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= self.threshold)

                matched_points = list(zip(*loc[::-1]))

                if matched_points:
                    pt_x, pt_y = matched_points[0]

                    cX = (pt_x + template_width // 2) // get_retina_scaling_factor() + blumWindowBounds["left"]
                    cY = (pt_y + template_height // 2) // get_retina_scaling_factor() + blumWindowBounds["top"]

                    move_mouse(cX, cY)
                    self.click_at(cX, cY)
                    print(f'Button pressed: {cX} {cY}')
                    self.clicked_points.append((cX, cY))
                    self.game_start_time = time.time()
                    break

    def click_color_areas(self):
        app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(self.window.get('kCGWindowOwnerPID'))
        if app:
            app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)

        #active_window = get_active_window_by_pid(self.window.get('kCGWindowOwnerPID'))
        #bounds = active_window.get('kCGWindowBounds')
        
        bounds = self.window.get('kCGWindowBounds')
        
        blumWindowBounds = {
            "top": int(bounds.get('Y')),
            "left": int(bounds.get('X')),
            "width": int(bounds.get('Width')),
            "height": int(bounds.get('Height'))
        }

        with mss.mss() as sct:
            pynput.keyboard.Listener(on_release=self.toggle_script).start()
            print(f'Press F6 (or Fn+F6 on Apple keyboards) to start/stop the script.')

            while True:
                if self.running:
                    img = np.array(sct.grab(blumWindowBounds))
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

                    if self.game_start_time is None:
                        # Scroll to Play button if needed
                        move_x = blumWindowBounds['left'] + (blumWindowBounds['width'] // 2)
                        move_y = blumWindowBounds['top'] + (blumWindowBounds['height'] // 2)
                        print(f"Window center: {move_x}, {move_y}")
                        pyautogui.moveTo(move_x, move_y)
                        scroll_window(-200, 0)
                        # Wait for and click the Play button
                        self.check_and_click_play_button(sct, blumWindowBounds)
                    elif self.is_game_over():
                        print('Game over.')
                        self.random_delay_before_restart()
                        self.game_start_time = None
                    else:
                        self.click_on_targets(hsv, blumWindowBounds, sct)
                time.sleep(0.1)

    def is_game_over(self):
        game_duration = 30 + 10 + 1 # 12 seconds for accidental freeze clicks plus 1 second is added for cases when the game is loading slowly
        current_time = time.time()
        if self.game_start_time and current_time - self.game_start_time >= game_duration - 0.5:
            return True
        return False

    def click_on_targets(self, hsv, blumWindowBounds, sct):
        for target_hsv in self.target_hsvs:
            lower_bound = np.array([target_hsv[0], 30, 30])
            upper_bound = np.array([target_hsv[0], 255, 255])
            mask = cv2.inRange(hsv, lower_bound, upper_bound)
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            num_contours = len(contours)
            contours_to_click = random.sample(contours, num_contours)

            for contour in reversed(contours_to_click):
                if cv2.contourArea(contour) < 12:
                    continue

                M = cv2.moments(contour)
                if M["m00"] == 0:
                    continue
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])

                cX = cX // get_retina_scaling_factor() + blumWindowBounds["left"]
                cY = cY // get_retina_scaling_factor() + blumWindowBounds["top"]

                if any(math.sqrt((cX - px) ** 2 + (cY - py) ** 2) < 35 for px, py in self.clicked_points):
                    continue
                # on slow computers, you may need to uncomment and find best value for cY adjustment below. On Macbook Pro with Apple Silicon this offset increase isn't required at all
                # cY += 5
                self.click_at(cX, cY)
                self.clicked_points.append((cX, cY))

        self.iteration_count += 1
        if self.iteration_count >= 5:
            self.clicked_points.clear()
            self.iteration_count = 0

    def random_delay_before_restart(self):
        delay = random.uniform(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX)
        print(f'Restart delay: {delay:.2f}s')
        time.sleep(delay)


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)

    windows = get_window_by_title(config.KEYWORDS)

    if len(windows) < 1:
        print(f"No windows found containing text in their name: {config.KEYWORDS}")
        exit()

    if len(windows) > 1:
        print(f"Too many windows with one of the following in their names: {config.KEYWORDS}. Please close all Blum windows except the one you want to click through")
        exit()

    print("Blum window found")

    window = windows[0]

    print("This is a simplified Mac OS port of original Windows-only script by [https://t.me/x_0xJohn]. Tested on Telegram Desktop at Macbook M1 with external 4k thunderbolt-connected display. Telegram window must be in the middle of the screen (but not full screen), while Blum window must be right in the middle of the Telegram window.")

    auto_clicker = AutoClicker(window, config.TARGET_COLORS_HEX, config.THRESHOLD)

    auto_clicker.click_color_areas()
