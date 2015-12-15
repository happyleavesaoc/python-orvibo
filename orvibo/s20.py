""" Orbivo S20. """

import binascii
import logging
import socket
import threading
import time

_LOGGER = logging.getLogger(__name__)

# S20 UDP port
PORT = 10000

# UDP best-effort.
RETRIES = 3
TIMEOUT = 1.0
DISCOVERY_TIMEOUT = 1.0

# Timeout after which to renew device subscriptions
SUBSCRIPTION_TIMEOUT = 60

# Packet constants.
MAGIC = b'\x68\x64'
DISCOVERY = b'\x00\x06\x71\x61'
DISCOVERY_RESP = b'\x00\x2a\x71\x61'
SUBSCRIBE = b'\x00\x1e\x63\x6c'
SUBSCRIBE_RESP = b'\x00\x18\x63\x6c'
CONTROL = b'\x00\x17\x64\x63'
CONTROL_RESP = b'\x00\x17\x73\x66'
PADDING_1 = b'\x20\x20\x20\x20\x20\x20'
PADDING_2 = b'\x00\x00\x00\x00'
ON = b'\x01'
OFF = b'\x00'

# Socket
_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Buffer
_BUFFER = {}


def _listen():
    """ Listen on socket. """
    while True:
        data, addr = _SOCKET.recvfrom(1024)
        _BUFFER[addr[0]] = data


def _setup():
    """ Set up module.

    Open a UDP socket, and listen in a thread.
    """
    for opt in [socket.SO_BROADCAST, socket.SO_REUSEADDR, socket.SO_REUSEPORT]:
        _SOCKET.setsockopt(socket.SOL_SOCKET, opt, 1)
    _SOCKET.bind(('', PORT))
    udp = threading.Thread(target=_listen, daemon=True)
    udp.start()


def discover(timeout=DISCOVERY_TIMEOUT):
    """ Discover devices on the local network.

    :param timeout: Optional timeout in seconds.
    :returns: Set of discovered host addresses.
    """
    hosts = set()
    payload = MAGIC + DISCOVERY
    for _ in range(RETRIES):
        _SOCKET.sendto(bytearray(payload), ('255.255.255.255', PORT))
        start = time.time()
        while time.time() < start + timeout:
            for host, data in _BUFFER.copy().items():
                if _is_discovery_response(data):
                    if host not in hosts:
                        _LOGGER.debug("Discovered device at %s", host)
                    hosts.add(host)
    return hosts


def _is_discovery_response(data):
    """ Is this a discovery response?

    :param data: Payload.
    """
    return data[0:6] == (MAGIC + DISCOVERY_RESP)


def _is_subscribe_response(data):
    """ Is this a subscribe response?

    :param data: Payload.
    """
    return data[0:6] == (MAGIC + SUBSCRIBE_RESP)


def _is_control_response(data):
    """ Is this a control response?

    :param data: Payload.
    """
    return data[0:6] == (MAGIC + CONTROL_RESP)


class S20Exception(Exception):
    """ S20 exception. """
    pass


class S20(object):
    """ Controls an Orbivo S20 WiFi Smart Socket.

    http://www.orvibo.com/en_products_view.asp?mid=15&pid=4&id=234

    Protocol documentation: http://pastebin.com/LfUhsbcS
    """
    def __init__(self, host):
        """ Initialize S20 object.

        :param host: IP or hostname of device.
        """
        self.host = host
        (self._mac, self._mac_reversed) = self._discover_mac()
        self._subscribe()

    @property
    def on(self):
        """ State property.

        :returns: State of device (on/off).
        """
        return self._subscribe()

    @on.setter
    def on(self, state):
        """ Change device state.

        :param state: True (on) or False (off).
        """
        if state:
            self._turn_on()
        else:
            self._turn_off()

    def _discover_mac(self):
        """ Discovers MAC address of device.

        Discovery is done by sending a UDP broadcast.
        All configured devices reply. The response contains
        the MAC address in both needed formats.

        Discovery of multiple switches must be done synchronously.

        :returns: Tuple of MAC address and reversed MAC address.
        """
        mac = None
        mac_reversed = None
        cmd = MAGIC + DISCOVERY
        resp = self._udp_transact(cmd, self._discovery_resp,
                                  broadcast=True,
                                  timeout=DISCOVERY_TIMEOUT)
        if resp:
            (mac, mac_reversed) = resp
        if mac is None:
            raise S20Exception("Couldn't discover {}".format(self.host))
        return (mac, mac_reversed)

    def _subscribe(self):
        """ Subscribe to the device.

        A subscription serves two purposes:
        - Returns state (on/off).
        - Enables state changes on the device
          for a short period of time.
        """
        cmd = MAGIC + SUBSCRIBE + self._mac \
            + PADDING_1 + self._mac_reversed + PADDING_1
        status = self._udp_transact(cmd, self._subscribe_resp)
        if status is not None:
            self.last_subscribed = time.time()
            return status == ON
        else:
            raise S20Exception(
                "No status could be found for {}".format(self.host))

    def _subscription_is_recent(self):
        """ Check if subscription occurred recently.

        :returns: Yes (True) or no (False)
        """
        return self.last_subscribed > time.time() - SUBSCRIPTION_TIMEOUT

    def _control(self, state):
        """ Control device state.

        Possible states are ON or OFF.

        :param state: Switch to this state.
        """

        # Renew subscription if necessary
        if not self._subscription_is_recent():
            self._subscribe()

        cmd = MAGIC + CONTROL + self._mac + PADDING_1 + PADDING_2 + state
        _LOGGER.debug("Sending new state to %s: %s", self.host, ord(state))
        ack_state = self._udp_transact(cmd, self._control_resp, state)
        if ack_state is None:
            raise S20Exception(
                "Device didn't acknowledge control request: {}".format(
                    self.host))

    def _discovery_resp(self, data):
        """ Handle a discovery response.

        :param data: Payload.
        :param addr: Address tuple.
        :returns: MAC and reversed MAC.
        """
        if _is_discovery_response(data):
            _LOGGER.debug("Discovered MAC of %s: %s", self.host,
                          binascii.hexlify(data[7:13]).decode())
            return (data[7:13], data[19:25])

    def _subscribe_resp(self, data):
        """ Handle a subscribe response.

        :param data: Payload.
        :returns: State (ON/OFF)
        """
        if _is_subscribe_response(data):
            status = bytes([data[23]])
            _LOGGER.debug("Successfully subscribed to %s, state: %s",
                          self.host, ord(status))
            return status

    def _control_resp(self, data, state):
        """ Handle a control response.

        :param data: Payload.
        :param state: Requested state.
        :returns: Acknowledged state.
        """
        if _is_control_response(data):
            ack_state = bytes([data[22]])
            if state == ack_state:
                _LOGGER.debug("Received state ack from %s, state: %s",
                              self.host, ord(ack_state))
                return ack_state

    def _udp_transact(self, payload, handler, *args,
                      broadcast=False, timeout=TIMEOUT):
        """ Complete a UDP transaction.

        UDP is stateless and not guaranteed, so we have to
        take some mitigation steps:
        - Send payload multiple times.
        - Wait for awhile to receive response.

        :param payload: Payload to send.
        :param handler: Response handler.
        :param args: Arguments to pass to response handler.
        :param broadcast: Send a broadcast instead.
        :param timeout: Timeout in seconds.
        """
        if self.host in _BUFFER:
            del _BUFFER[self.host]
        host = self.host
        if broadcast:
            host = '255.255.255.255'
        retval = None
        for _ in range(RETRIES):
            _SOCKET.sendto(bytearray(payload), (host, PORT))
            start = time.time()
            while time.time() < start + timeout:
                data = _BUFFER.get(self.host, None)
                if data:
                    retval = handler(data, *args)
                # Return as soon as a response is received
                if retval:
                    return retval

    def _turn_on(self):
        """ Turn on the device. """
        self._control(ON)

    def _turn_off(self):
        """ Turn off the device. """
        self._control(OFF)


_setup()
