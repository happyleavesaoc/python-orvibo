""" Orbivo S20. """

import logging
import socket

_LOGGER = logging.getLogger(__name__)

# S20 UDP port
PORT = 10000

# UDP best-effort.
RETRIES = 3
TIMEOUT = 0.5

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
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.bind(('', PORT))
        (self._mac, self._mac_reversed) = self._discover_mac()

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

        :returns: Tuple of MAC address and reversed MAC address.
        """
        mac = None
        mac_reversed = None
        cmd = MAGIC + DISCOVERY
        resp = self._udp_transact(cmd, self._discovery_resp,
                                  broadcast=True, timeout=1.0)
        if resp:
            (mac, mac_reversed) = resp
        if not mac:
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
            return status == ON
        else:
            raise S20Exception(
                "No status could be found for {}".format(self.host))

    def _control(self, state):
        """ Control device state.

        Possible states are ON or OFF.

        :param state: Switch to this state.
        """
        cmd = MAGIC + CONTROL + self._mac + PADDING_1 + PADDING_2 + state
        _LOGGER.debug("Sending new state to %s: %s", self.host, ord(state))
        ack_state = self._udp_transact(cmd, self._control_resp, state)
        if ack_state is None:
            raise S20Exception(
                "Device didn't acknowledge control request: {}".format(
                    self.host))

    def _discovery_resp(self, data, addr):
        """ Handle a discovery response.

        :param data: Payload.
        :param addr: Address tuple.
        :returns: MAC address tuple.
        """
        if self._is_discovery_response(data, addr):
            _LOGGER.debug("Discovered MAC of %s", self.host)
            return (data[7:13], data[19:25])
        return (None, None)

    def _subscribe_resp(self, data, addr):
        """ Handle a subscribe response.

        :param data: Payload.
        :param addr: Address tuple.
        :returns: State (ON/OFF)
        """
        if self._is_subscribe_response(data, addr):
            status = bytes([data[23]])
            _LOGGER.debug("Successfully subscribed to %s, state: %s",
                          self.host, ord(status))
            return status

    def _control_resp(self, data, addr, state):
        """ Handle a control response.

        :param data: Payload.
        :param addr: Address tuple.
        :param state: Acknowledged state.
        """
        if self._is_control_response(data, addr):
            ack_state = bytes([data[22]])
            if state == ack_state:
                _LOGGER.debug("Received state ack from %s, state: %s",
                              self.host, ord(ack_state))
                return ack_state

    def _is_discovery_response(self, data, addr):
        """ Is this a discovery response?

        :param data: Payload.
        :param addr: Address tuple.
        """
        return data[0:6] == (MAGIC + DISCOVERY_RESP) and addr[0] == self.host

    def _is_subscribe_response(self, data, addr):
        """ Is this a subscribe response?

        :param data: Payload.
        :param addr: Address tuple.
        """
        return data[0:6] == (MAGIC + SUBSCRIBE_RESP) and addr[0] == self.host

    def _is_control_response(self, data, addr):
        """ Is this a control response?

        :param data: Payload.
        :param addr: Address tuple.
        """
        return data[0:6] == (MAGIC + CONTROL_RESP) and addr[0] == self.host

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
        host = self.host
        if broadcast:
            host = '255.255.255.255'
        retval = None
        self._socket.settimeout(timeout)
        for _ in range(RETRIES):
            self._socket.sendto(bytearray(payload), (host, PORT))
            while True:
                try:
                    data, addr = self._socket.recvfrom(1024)
                    retval = handler(data, addr, *args)
                except socket.timeout:
                    break
            if retval:
                break
        return retval

    def _turn_on(self):
        """ Turn on the device. """
        if not self._subscribe():
            self._control(ON)

    def _turn_off(self):
        """ Turn off the device. """
        if self._subscribe():
            self._control(OFF)
