import time
import threading
from pysimverse.simulators.drone.drone import Drone
import zmq


class DroneManager:

    def __init__(self, drone_count, host="*", handshake_port=5555, dronecount_port=5556):
        """
        Initializes the Drone with a ZMQ publisher and subscriber.
        """
        self.host = host
        self.handshake_port = handshake_port
        self.dronecount_port = dronecount_port

        # ZMQ context for both publisher and subscriber
        self.context = zmq.Context.instance ()  # Use singleton context for efficiency

        # Command Publisher setup (PUB)
        self.drone_count_socket = self.context.socket (zmq.PUB)
        self.drone_count_socket.setsockopt (zmq.SNDHWM, 1)  # Prevent excessive buffering
        self.drone_count_socket.setsockopt (zmq.LINGER, 0)  # Prevent hang on shutdown
        self.drone_count_address = f"tcp://{host}:{dronecount_port}"

        # Handshake Subscriber setup (SUB)
        self.handshake_socket = self.context.socket (zmq.SUB)
        self.handshake_socket.setsockopt (zmq.RCVHWM, 1)  # Prevent excessive buffering
        self.handshake_socket.setsockopt (zmq.LINGER, 0)  # Ensure immediate disconnect
        self.handshake_socket.setsockopt_string (zmq.SUBSCRIBE, "")  # Subscribe to all topics
        self.handshake_address = f"tcp://localhost:{handshake_port}"

        # Use ZeroMQ Poller for efficient non-blocking reception
        self.poller = zmq.Poller ()
        self.poller.register (self.handshake_socket, zmq.POLLIN)

        self.drone_list = []
        self.port_list = []
        self.drone_count = drone_count

    def connect(self):
        self.drone_count_socket.bind (self.drone_count_address)
        self.handshake_socket.connect (self.handshake_address)

        for _ in range (5):  # Try up to 5 times to receive handshake
            socks = dict (self.poller.poll (200))  # Wait up to 200ms
            if self.handshake_socket in socks:
                message = self.handshake_socket.recv ()
                print (f"Handshake received: {message}")
                break

    def send_drone_count(self):

        try:
            data = {
                "dronecount": self.drone_count
                }

            self.drone_count_socket.send_json(data)
            print (f"Published Drone Count data: {data}")
        except Exception as e:
            print (f"Error publishing data: {e}")

    def create_drones(self):
        self.connect ()
        self.send_drone_count()
        self.get_portlist ()

        for port in self.port_list:
            drone = Drone(cmd_port=port)
            drone.connect()
            self.drone_list.append(drone)

    def get_portlist(self):
        try:
            # Receive a message from the publisher
            message = self.handshake_socket.recv_string ()
            print (f"Received Ports list: {message}%")

            # Remove unwanted characters and split the string into a list of integers
            clean_message = message.strip ('%')  # Remove the trailing '%'
            self.port_list = [int (port.strip ()) for port in clean_message.split (',')]

            time.sleep (1)

        except KeyboardInterrupt:
            print ("\nExiting...")

    def takeoff_all_drones(self, sorted_rows):
        """
        Take off all drones by row with assigned heights for each row.

        Args:
            sorted_rows: List of lists, where each inner list contains drones for one row
        """

        # Create a mapping from drone position to actual drone object
        drone_idx = 0
        threads = []

        # For each row in sorted_rows
        for row_idx, row_drones in enumerate (sorted_rows):
            # Take off all drones in this row concurrently with the same height
            row_threads = []
            for _ in row_drones:
                if drone_idx < len (self.drone_list):
                    drone = self.drone_list[drone_idx]
                    thread = threading.Thread (target=drone.take_off, args=(300,))
                    thread.start ()
                    row_threads.append (thread)
                    threads.append (thread)
                    drone_idx += 1

        # Wait for all drones to complete takeoff
        for thread in threads:
            thread.join ()
