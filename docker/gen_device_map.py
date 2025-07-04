import json
from rocm_smi import getBus, initializeRsmi, listDevices


def generateDeviceMap():
    initializeRsmi()
    deviceMap = {}
    for index in listDevices():
        deviceMap[index] = getBus(index).lower()

    with open('/data/devices.json', 'w+') as f:
        f.write(json.dumps(deviceMap))


if __name__ == "__main__":
     generateDeviceMap()
