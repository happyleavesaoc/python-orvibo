# python-orvibo

Control Orvibo devices with Python 3. Currently supports the S20 WiFi Smart Switch.

## Usage

```python
from orvibo.s20 import S20, discover

hosts = discover() # Discover devices on your local network.
s20 = S20("x.x.x.x") # Use a discovered host, or supply a known host.
print(s20.on) # Current state (True = ON, False = OFF).
s20.on = True # Turn it on.
s20.on = False # Turn it off.
```

There is also a command line version to achieve the same, e.g.

```
python cmd.py --server 1.2.3.4 --switch off
python cmd.py --server 1.2.3.4 --switch on
python cmd.py --server 1.2.3.4 --status
```

There is also a HTTP Server version .
```
python3 OrviboHTTPServer.py <ip to bind to> <port to listen to>
```
Commands can then be given through HTTP GET requests in the openHAB http binding using the following IP Address and path:
```
<ip to bind to>:<port to listen to>/STATUS/<ip of plug>
<ip to bind to>:<port to listen to>/ON/<ip of plug>
<ip to bind to>:<port to listen to>/OFF/<ip of plug>
```

## Contributions

Pull requests are welcome. Possible areas for improvement:

* Additional Orvibo devices.
* Expand S20 functions: Timers, configuration, etc

## Disclaimer

Not affiliated with Shenzhen Orvibo Electronics Co., Ltd.
