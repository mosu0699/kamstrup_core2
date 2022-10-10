# Stand alone power reader based on M5Stack core2.
The hardware used, is the [M5Stack Core2](https://www.elfadistrelec.dk/da/esp32-m5core2-udviklingsmodul-m5stack-k010/p/30181494).
It reads data from the brilliant [AmsToMqttBridge](https://github.com/gskjold/AmsToMqttBridge) bridge made by [gskjold](https://github.com/gskjold).

Displays:
1. Effective power price (kr/h) (+/-). The color is red when importing and green when exporting. This is the price for the next used kWh.
2. Power import (W) (+/-). The color is red when importing and green when exporting.
3. Current import price this hour.
4. Current export price this hour.
5. Daily usage (kr).
6. Hourly usage (kr).

The time is read from dk.pool.ntp.org.

The power prices are read from energidataservice.dk.

The import- and export prices are based on Vindstød (Danish) charges.

![IMG_0842](https://user-images.githubusercontent.com/113230479/194697393-0e024e24-e7ae-4c61-90d2-625a0adc09f2.jpeg)

## Instructions
1. Modify section "config" at the top of main.py.
2. Install visual studio code (VSC)
3. install VSC extension: vscode-m5stack-mpy
4. Connect by "Add M5Stack" in bottom left corner of VSC
5. Upload main.py
6. Setup m5stack to execute main.py at startup
7. Done!

