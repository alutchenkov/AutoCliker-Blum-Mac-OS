import os
import time
import random
import math
import cv2
import pynput
import mss
import numpy as np
import warnings
import config
import Quartz
import AppKit

warnings.filterwarnings("ignore", category=UserWarning, module='pywinauto')

def get_window_list():
    window_list = []
    window_info_list = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
    for window_info in window_info_list:
        window_list.append(window_info)
    return window_list

def list_windows_by_title(title_keywords):
    all_windows = get_window_list()
    filtered_windows = []
    for window in all_windows:
        for keyword in title_keywords:
            if keyword.lower() in window.get('kCGWindowName', 'No Title').lower():
                filtered_windows.append((window.get('kCGWindowName', 'No Title'), window))
                break
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
    def __init__(self, window, target_colors_hex, nearby_colors_hex, threshold, target_percentage, collect_freeze):
        self.window = window
        self.target_colors_hex = target_colors_hex
        self.nearby_colors_hex = nearby_colors_hex
        self.threshold = threshold
        self.target_percentage = target_percentage
        self.collect_freeze = collect_freeze
        self.running = False
        self.clicked_points = []
        self.iteration_count = 0
        self.last_check_time = time.time()
        self.last_freeze_check_time = time.time()
        self.freeze_cooldown_time = 0
        self.game_start_time = None
        self.freeze_count = 0
        self.target_hsvs = [self.hex_to_hsv(color) for color in self.target_colors_hex]
        self.nearby_hsvs = [self.hex_to_hsv(color) for color in self.nearby_colors_hex]

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
                self.freeze_count = 0
                print('Script started. Looking for the Play button')
            else:
                print('Script stopped.')

    def is_near_color(self, hsv_img, center, target_hsvs, radius=8):
        x, y = center
        height, width = hsv_img.shape[:2]
        for i in range(max(0, x - radius), min(width, x + radius + 1)):
            for j in range(max(0, y - radius), min(height, y + radius + 1)):
                distance = math.sqrt((x - i) ** 2 + (y - j) ** 2)
                if distance <= radius:
                    pixel_hsv = hsv_img[j, i]
                    for target_hsv in target_hsvs:
                        if np.allclose(pixel_hsv, target_hsv, atol=[1, 50, 50]):
                            return True
        return False

    def check_and_click_play_button(self, sct, blumWindowBounds):
        current_time = time.time()
        if current_time - self.last_check_time >= random.uniform(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX):
            self.last_check_time = current_time
            templates = [
                cv2.imread(os.path.join("template_png", "template_play_button2.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button3.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button.png"), cv2.IMREAD_GRAYSCALE),
                cv2.imread(os.path.join("template_png", "template_play_button1.png"), cv2.IMREAD_GRAYSCALE)
            ]

            for template in templates:
                if template is None:
                    print("Unable to load template.")
                    continue

                template_height, template_width = template.shape

                img = np.array(sct.grab(blumWindowBounds))
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

                res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= self.threshold)

                matched_points = list(zip(*loc[::-1]))

                if matched_points:
                    pt_x, pt_y = matched_points[0]

                    cX = (pt_x + template_width // 2) // get_retina_scaling_factor() + blumWindowBounds["left"]
                    cY = (pt_y + template_height // 2) // get_retina_scaling_factor() + blumWindowBounds["top"]

                    self.click_at(cX, cY)
                    print(f'Button pressed: {cX} {cY}')
                    self.clicked_points.append((cX, cY))
                    self.game_start_time = time.time()
                    self.freeze_count = 0
                    break

    def click_color_areas(self):
        app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(self.window.get('kCGWindowOwnerPID'))
        if app:
            app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)

        active_window = get_active_window_by_pid(self.window.get('kCGWindowOwnerPID'))
        bounds = active_window.get('kCGWindowBounds')
        blumWindowBounds = {
            "top": int(bounds.get('Y')),
            "left": int(bounds.get('X')),
            "width": int(bounds.get('Width')),
            "height": int(bounds.get('Height'))
        }

        with mss.mss() as sct:
            pynput.keyboard.Listener(on_release=self.toggle_script).start()
            print(f'Press F6 to start/stop the script.')

            while True:
                if self.running:
                    img = np.array(sct.grab(blumWindowBounds))
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

                    if self.game_start_time is None:
                        # Scroll to Play button if needed
                        move_mouse(blumWindowBounds['left'] + (blumWindowBounds['width'] / 2), blumWindowBounds['top'] + (blumWindowBounds['height'] / 2))
                        scroll_window(-100, 0)
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
        game_duration = 30 + 5 + self.freeze_count * 3 # 5 seconds is added for cases when the game is loading slowly
        current_time = time.time()
        if self.game_start_time and current_time - self.game_start_time >= game_duration - 0.5:
            return True
        return False

    def click_on_targets(self, hsv, blumWindowBounds, sct):
        for target_hsv in self.target_hsvs:
            lower_bound = np.array([max(0, target_hsv[0] - 1), 30, 30])
            upper_bound = np.array([min(179, target_hsv[0] + 1), 255, 255])
            mask = cv2.inRange(hsv, lower_bound, upper_bound)
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            num_contours = len(contours)
            num_to_click = int(num_contours * self.target_percentage)
            contours_to_click = random.sample(contours, num_to_click)

            for contour in reversed(contours_to_click):
                if cv2.contourArea(contour) < 6:
                    continue

                M = cv2.moments(contour)
                if M["m00"] == 0:
                    continue
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])

                if not self.is_near_color(hsv, (cX, cY), self.nearby_hsvs):
                    continue

                cX = cX // get_retina_scaling_factor() + blumWindowBounds["left"]
                cY = cY // get_retina_scaling_factor() + blumWindowBounds["top"]

                if any(math.sqrt((cX - px) ** 2 + (cY - py) ** 2) < 35 for px, py in self.clicked_points):
                    continue
                #cY += 3
                self.click_at(cX, cY)
                #print(f'Pressed: {cX} {cY}')
                self.clicked_points.append((cX, cY))

        if self.collect_freeze:
            self.check_and_click_freeze_button(sct, blumWindowBounds)

        self.iteration_count += 1
        if self.iteration_count >= 5:
            self.clicked_points.clear()
            self.iteration_count = 0

    def check_and_click_freeze_button(self, sct, blumWindowBounds):
        freeze_hsvs = [self.hex_to_hsv(color) for color in config.FREEZE_COLORS_HEX]
        current_time = time.time()
        if current_time - self.last_freeze_check_time >= 1 and current_time >= self.freeze_cooldown_time:
            self.last_freeze_check_time = current_time
            img = np.array(sct.grab(blumWindowBounds))
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            for freeze_hsv in freeze_hsvs:
                lower_bound = np.array([max(0, freeze_hsv[0] - 1), 30, 30])
                upper_bound = np.array([min(179, freeze_hsv[0] + 1), 255, 255])
                mask = cv2.inRange(hsv, lower_bound, upper_bound)
                contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    if cv2.contourArea(contour) < 3:
                        continue

                    M = cv2.moments(contour)
                    if M["m00"] == 0:
                        continue
                    cX = int(M["m10"] / M["m00"]) // get_retina_scaling_factor() + blumWindowBounds["left"]
                    cY = int(M["m01"] / M["m00"]) // get_retina_scaling_factor() + blumWindowBounds["top"]

                    self.click_at(cX, cY)
                    print(f'Freezer pressed: {cX} {cY}')
                    self.freeze_cooldown_time = time.time() + 4  # Don't click freezers next 4 seconds
                    self.freeze_count += 1

                    # Check pixel color in 1s after freezer click
                    time.sleep(1)

                    img_check = np.array(sct.grab(blumWindowBounds))
                    img_bgr_check = cv2.cvtColor(img_check, cv2.COLOR_BGRA2BGR)
                    hsv_check = cv2.cvtColor(img_bgr_check, cv2.COLOR_BGR2HSV)

                    right_bottom_x = blumWindowBounds["width"] - config.OFFSET_X
                    right_bottom_y = blumWindowBounds["height"] - config.OFFSET_Y

                    if right_bottom_x >= img_check.shape[1] or right_bottom_y >= img_check.shape[0]:
                        print('Out of dimensions')
                        return

                    pixel_hsv = hsv_check[right_bottom_y, right_bottom_x]

                    # Check for black color
                    if np.array_equal(pixel_hsv, [0, 0, 0]):
                        self.freeze_count -= 1
                        print('Incorrect freezer click')

                    return

    def random_delay_before_restart(self):
        delay = random.uniform(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX)
        print(f'Restart delay: {delay:.2f}s')
        time.sleep(delay)


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)

    windows = list_windows_by_title(config.KEYWORDS)

    if not windows:
        print("No windows with Telegram text in their names")
        exit()

    print("Available windows:")
    for i, (title, window) in enumerate(windows):
        print(f"{i + 1}: {title}")

    choice = int(input("Start the Blum bot and choose its Telegram window here: ")) - 1
    if choice < 0 or choice >= len(windows):
        print("Incorrect choice.")
        exit()

    window = windows[choice][1]

    while True:
        try:
            target_percentage = input(
                "Type in a decimal value between 0 and 1 where 1 is clicking all leafs: ")
            target_percentage = target_percentage.replace(',', '.')
            target_percentage = float(target_percentage)
            if 0 <= target_percentage <= 1:
                break
            else:
                print("Please provide value between 0 and 1.")
        except ValueError:
            print("Please provide a number.")

    while True:
        try:
            collect_freeze = int(input("Click freezers? 1 - Yes, 2 - No: "))
            if collect_freeze in [1, 2]:
                collect_freeze = (collect_freeze == 1)
                break
            else:
                print("Please enter 1 or 2.")
        except ValueError:
            print("Incorrect choice. Only 1 or 2 are allowed.")

    print("This is a Mac OS port with minor updates of original script by [https://t.me/x_0xJohn]")

    auto_clicker = AutoClicker(window, config.TARGET_COLORS_HEX, config.NEARBY_COLORS_HEX, config.THRESHOLD, target_percentage, collect_freeze)

    auto_clicker.click_color_areas()
