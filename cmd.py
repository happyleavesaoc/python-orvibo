from orvibo.s20 import S20
import argparse

parser = argparse.ArgumentParser(description='Control the S20 switch.')
parser.add_argument('--server', dest='server', type=str, help='the IP address of the switch to control')
parser.add_argument('--switch', dest='operation', help='what to do (ON or OFF)')
parser.add_argument('--status', dest='status', help='the current switch state', action="store_true")

args = parser.parse_args()

s20 = S20(args.server)
if args.status:
    print("ON" if s20.on else "OFF")
else:
    if args.operation and args.operation.upper() == 'ON':
        s20.on = True
    elif args.operation and args.operation.upper() == 'OFF':
        s20.on = False
    else:
        print("unrecognised command")