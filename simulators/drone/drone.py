import zmq
import cv2
import numpy as np
import time
import socket


class Drone:
    stream_on = False

    def __init__(self, host="*", cmd_port=5550, state_port=5556, video_port=5557, speed=300, rotation_speed=15):
        """
        Initializes the Drone with a ZMQ publisher and subscriber.
        """
        self.host = host
        self.cmd_port = cmd_port
        self.state_port = state_port
        self.video_port = video_port

        # ZMQ context for both publisher and subscriber
        self.context = zmq.Context()

        # Command Publisher setup
        self.command_socket = self.context.socket(zmq.PUB)
        self.command_address = f"tcp://{host}:{cmd_port}"

        # State Subscriber setup
        self.state_socket = self.context.socket(zmq.SUB)
        self.state_address = f"tcp://localhost:{state_port}"

        # Video Subscriber setup
        self.video_socket = self.context.socket(zmq.SUB)
        self.video_address = f"tcp://localhost:{video_port}"

        self.poller = zmq.Poller()  # Initialize ZeroMQ Poller
        self.poller.register(self.video_socket, zmq.POLLIN)  # Register the video socket for polling

        self.speed = speed
        self.rotation_speed = rotation_speed
        self.is_flying = False


    def connect(self):
        """
        Set up ZeroMQ with three distinct ports:
        - Command port for sending commands.
        - State port for receiving telemetry/state data.
        - Video port for receiving video data or other additional subscriptions.
        """
        # Command Publisher setup
        self.command_socket.bind(self.command_address)

        self.state_socket.connect(self.state_address)
        self.state_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all telemetry/state messages

        self.video_socket.connect(self.video_address)
        self.video_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all video messages
        print("Response: Connected")

        time.sleep(0.25)  # Give some time for the subscriber to establish

    def is_port_available(port):
        """Check if a TCP port is available. Returns True if available, False otherwise."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse
            try:
                s.bind(("localhost", port))  # Try to bind to localhost:{port}
                return True  # Port is available
            except OSError:
                return False  # Port is in use

    def send_rc_control(self, left_right, forward_backward, up_down, yaw, camera_angle=0, streamon=None, red=None,
                        green=None, blue=None):
        """
        Publishes RC control values as a JSON object to the publisher socket.
        """
        try:
            data = {
                "left_right": left_right,
                "forward_backward": forward_backward,
                "up_down": up_down,
                "yaw": yaw,
                "cameraangle": camera_angle,
                "streamon": streamon,
                "color": {
                    "red": red,  # Red component (0-255)
                    "green": green,  # Green component (0-255)
                    "blue": blue  # Blue component (0-255)
                }
            }
            self.command_socket.send_json(data)
            print(f"Published RC control data: {data}")
        except Exception as e:
            print(f"Error publishing data: {e}")

    def streamon(self):
        self.stream_on = True
        self.send_rc_control(None, None, None, None, None, self.stream_on)

    def streamoff(self):
        self.stream_on = False
        self.send_rc_control(None, None, None, None, None, self.stream_on)

    def get_frame(self):
        """
        Receives and decodes frames from the publisher using ZeroMQ Poller, skipping any backlog.
        """
        is_success = False
        frame = None

        try:
            while True:
                # Poll the socket with a timeout to avoid blocking
                socks = dict(self.poller.poll(timeout=10))  # Timeout of 10 ms
                if self.video_socket in socks and socks[self.video_socket] == zmq.POLLIN:
                    # Receive and discard all older frames to process the most recent one
                    frame_bytes = self.video_socket.recv(zmq.DONTWAIT)  # Non-blocking
                    # Decode the most recent frame
                    frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                else:
                    break  # Exit the loop if no more frames are in the queue

            # Add FPS overlay
            if frame is not None:
                is_success = True
                fps, frame = self.fpsReader.update(
                    frame, pos=(20, 50),
                    bgColor=(255, 0, 255), textColor=(255, 255, 255),
                    scale=3, thickness=3
                )
            else:
                print("Failed to decode frame.")

        except zmq.Again:
            print("No new frames available.")
        except Exception as e:
            print(f"Error receiving frame: {e}")

        return frame, is_success

    def shutdown(self):
        """
        Cleans up resources and shuts down the server.
        """
        self.command_socket.close()
        self.state_socket.close()
        self.video_socket.close()
        self.context.term()
        cv2.destroyAllWindows()
        print("Drone server has been terminated.")

    def get_battery(self):
        try:
            # Receive a message from the publisher (battery percentage)
            message = self.state_socket.recv_string()
            print(f"Received Battery Data: {message}%")

            # Optional: You could do further processing with the data here
            battery_percentage = float(message)

            time.sleep(1)

        except KeyboardInterrupt:
            print("\nExiting...")

    def move_forward(self, distance):
        if self.is_flying:
            self.send_rc_control(0, self.speed, 0, 0, 0)
            delay = distance / self.speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def move_backward(self, distance):
        if self.is_flying:
            self.send_rc_control(0, -self.speed, 0, 0, 0)
            delay = distance / self.speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def move_right(self, distance):
        if self.is_flying:
            self.send_rc_control(self.speed, 0, 0, 0, 0)
            delay = distance / self.speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def move_left(self, distance):
        if self.is_flying:
            self.send_rc_control(-self.speed, 0, 0, 0, 0)
            delay = distance / self.speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def move_up(self, distance):
        if self.is_flying:
            self.send_rc_control(0, 0, self.speed, 0, 0)
            delay = distance / self.speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def move_down(self, distance):
        if self.is_flying:
            self.send_rc_control(0, 0, -self.speed, 0, 0)
            delay = distance / self.speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def take_off(self, takeoff_height=200, takeoff_speed=200):
        if not self.is_flying:
            self.is_flying = True
            self.send_rc_control(0, 0, takeoff_speed, 0, 0)
            delay = takeoff_height / takeoff_speed
            time.sleep(delay)
            self.send_rc_control(0, 0, 0, 0, 0)
            print("Drone has taken off.")
        else:
            print("Drone is already flying.")

    def land(self, landing_speed=100):
        if self.is_flying:
            self.send_rc_control(0, 0, -landing_speed, 0, 0)
            time.sleep(3)
            self.send_rc_control(0, 0, 0, 0, 0)
            self.is_flying = False
            print("Drone has landed.")
        else:
            print("Drone is already on the ground.")

    def rotate(self, angle):
        if self.is_flying:
            if angle < 0:
                self.send_rc_control(0, 0, 0, -self.rotation_speed / 70, 0)
            else:
                self.send_rc_control(0, 0, 0, self.rotation_speed / 70, 0)

            time.sleep(abs(angle / 60))
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def rotate_camera(self, angle):
        if self.is_flying:
            self.send_rc_control(0, 0, 0, 0, angle)
            time.sleep(abs(angle / 40))
            self.send_rc_control(0, 0, 0, 0, 0)
        else:
            print("Take off the drone first.")

    def set_speed(self, speed):
        self.speed = speed

    def set_rotation_speed(self, rotation_speed):
        self.rotation_speed = rotation_speed
