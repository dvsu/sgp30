from sgp30 import SGP30

sensor = SGP30(1)

info = sensor.get_sensor_info()
print(info)

while True:
    try:
        data = sensor.get_measurement(as_dict=True)
        print(data)

    except KeyboardInterrupt:
        break

sensor.close()
