#########################################################
# Displays effective delta power price (kr/h), power import (W), 
# import price, export price, daily usage (kr) and hourly usage (kr),
# from data read from AMS reader ams2mqtt2 in Kamstrup power reader.
#
# Time is read from dk.pool.ntp.org
# Power Prices read from energidataservice.dk
# Import- and export prices based on Vindstod charges.
#########################################################

from m5stack import *
import utime
import urequests
import ntptime

# Config
SSID_Name = 'your SSID'
SSID_password = 'Your wifi password'
url = 'http://<AMS reader IP>/' # IP address of AMS connected to Kamstrup

# Wifi connection
def do_connect():
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        sta_if.active(True)
        sta_if.connect(SSID_Name, SSID_password)
        lcd.print('Connecting to network '+SSID_Name)
        while not sta_if.isconnected():
            lcd.print('.')
            utime.sleep(1)
        lcd.print('\n')
            

class display_class:
    # coordinates of vars
    colDist = 160
    rowDist = 80
    varRowDist = 34 # dist between title and variable
    varIndent = 10

    Xcoordinates = [varIndent, colDist+varIndent]
    Ycoordinates = [varRowDist, rowDist+varRowDist, 2*rowDist+varRowDist]

    def __init__(self):

        self.arraydata = [[None, None, None], [None, None, None]] # outer is x, inner is y
        lcd.clear()
        lcd.font(lcd.FONT_DejaVu24)

        # 1st col 1st row
        lcd.print('Pris', 0, 0, 0xfefefe)

        # 2nd col 1st row
        lcd.print('Import', self.colDist, 0, 0xfefefe)

        # 1st col 2nd row
        lcd.print('IPris', 0, self.rowDist, 0xfefefe)
        
        # 2nd col 2nd row
        lcd.print('EPris', self.colDist, self.rowDist, 0xfefefe)

        # 1st col 3rd row
        lcd.print('F-dag', 0, self.rowDist*2, 0xfefefe)

        # 2nd col 3rd row
        lcd.print('F-time', self.colDist, self.rowDist*2, 0xfefefe)


    # If colorRed then red else green
    def writeXY(self, data, colorRed, x, y):

        if self.arraydata[x][y]!=None:
            lcd.textClear(self.Xcoordinates[x], self.Ycoordinates[y], self.arraydata[x][y])

        if colorRed:
            lcd.print(data, self.Xcoordinates[x], self.Ycoordinates[y], 0xff0000)
        else: # Green
            lcd.print(data, self.Xcoordinates[x], self.Ycoordinates[y])

        self.arraydata[x][y] = data


# Read actual power prices and calculate import and export prices
class powerCostApi_class:

    baseUrl = "http://api.energidataservice.dk/dataset/Elspotprices?"

    def __init__(self, pollingTime, ntp, displayClass : display_class):
        self.pollingTime = pollingTime
        self.call_cnt = 0
        self.oldPrices = [] # list of touples (hour, price)
        self.display = displayClass
        self.ntp = ntp
        self.lastPriceUpdate = None


    def getSpotPrice(self):
        # lcd.print('getSpotPrice\n')
        res = self.oldPrices # Reuse old in case of network error

        now = utime.localtime()  # (y, m, d, h, m, s, wd, yd)

        start_string = str(now[0])+"-"+"{:02d}".format(now[1])+"-"+"{:02d}".format(now[2])

        now_s = utime.mktime(now) # seconds
        endDay_s = now_s+60*60*24*2 # 2 days after now
        endDate = utime.localtime(endDay_s) # (y, m, d, h, m, s, wd, yd)

        end_string = str(endDate[0])+"-"+"{:02d}".format(endDate[1])+"-"+"{:02d}".format(endDate[2])

        url = self.baseUrl+'start='+start_string+'&end='+end_string+'&filter={"PriceArea":"DK2"}'
        try:
            resp = urequests.get(url)
            # lcd.print(resp.text+'\n')

            if resp.reason!=b'OK':
                self.display.writeXY('Error getSpotPrice',1,0,0)
            else:
                tmp = (resp.json())['records']
                for item in tmp:
                    date_time_str = item['HourDK']
                    myDay = int((date_time_str.split('-')[2]).split('T')[0])
                    deltaDay = myDay - now[2] # only != is used, so subtract is ok even though wrap

                    myHour = int((date_time_str.split(':')[0]).split('T')[1])
                    price = item['SpotPriceDKK']/10
                    if (deltaDay and myHour < self.ntp.hour()) or (not deltaDay and myHour >= self.ntp.hour()):
                        res.append((myHour, price))

                self.oldPrices = res
        except:
            self.display.writeXY('Error getSpotPrice exception', 1, 0, 0)

        return res


    # Input struct
    def calcPrices(self, spotPrices):
        res = []

        for time, spotPrice in spotPrices:

            # https://www.vindstoed.dk/tilmelding-solcelle
            energinetEntranceTarif = 0.375 # øre/kWh
            energinetBalanceTarif = 0.0875 # øre/kWh
            vindstodBalanceTarif = 1 # øre/kWh
            sellingPrice = max((spotPrice-energinetEntranceTarif-energinetBalanceTarif-vindstodBalanceTarif), 0.0) # øre/kWh

            # https://www.vindstoed.dk/se-hvad-du-kan-spare-og-tilmeld
            vindstodSpotPris = spotPrice*1.25 + 0.63

            # https://www.tv2lorry.dk/energikrise/selskab-fordobler-stroemprisen-om-aftenen-her-er-forklaringen
            if time >= 17 and time < 21:
                tarifPris = 76.51*1.25 + vindstodSpotPris
            else:
                tarifPris = 30.03*1.25 + vindstodSpotPris

            # https://skat.dk/data.aspx?oid=2234584
            afgift = 76.3 * 1.25 # 95.4

            # https://energinet.dk/El/Elmarkedet/Tariffer/Aktuelle-tariffer
            energinet = (4.9+6.1+0.229) * 1.25 # Transmissionsnettarif, Systemtarif, Balancetarif for forbrug
            buyingPrice = tarifPris + energinet + afgift

            if 0: # time == 11:
                print("Tid, salgspris, købspris")
                print("{0}-{1} {2} {3}".format(time, time+1, round(sellingPrice), round(buyingPrice)))
                print("---------------------------")

            # print("{0}-{1} {2:.0f} {3:.0f}".format(time, time+1, round(sellingPrice), round(buyingPrice)))
            res.append((time, (buyingPrice, sellingPrice)))

        return res


    def lookUpCurrentPrices(self):

        now = utime.localtime()  # (y, m, d, h, m, s, wd, yd)
        for elem in self.priceList:
            if elem[0] == now[3]:
                self.currentImportPrice, self.currentExportPrice = elem[1]
                return
        # if now.hour not in self.prices:
        self.display.writeXY("Error: lookUpCurrentPrices, element (hour) "+str(now[3]), 1, 0, 1)

    def getCurrentPrices(self):
        return self.currentImportPrice, self.currentExportPrice;

    # Downsample and update prices
    def __call__(self):

        if self.call_cnt == 0:
            self.call_cnt = 60/self.pollingTime # 1 min
            now = utime.localtime()  # (y, m, d, h, m, s, wd, yd)
            if self.lastPriceUpdate != now[3]: # hour
                self.lastPriceUpdate = now[3]
                spotPriceList = self.getSpotPrice()
                self.priceList = self.calcPrices(spotPriceList)
                self.lookUpCurrentPrices()
                self.display.writeXY("{:.02f}".format(self.currentImportPrice/100), 0, 0, 1)
                self.display.writeXY("{:.02f}".format(self.currentExportPrice/100), 0, 1, 1)
        else:
            self.call_cnt -= 1

# end powerCostApi_class


class radiusApi_class():

    # url = 'http://ams-cf58.local/' # mDNS not supported

    def __init__(self, pollingTime, displayClass : display_class):
        self.display = displayClass
        self.earningsTotal = 0.0
        self.earningsYesterday = -0.0
        self.earningsToday = 0.0
        self.pollingTime = pollingTime
        self.call_cnt = 0
        self.old = 0, 0
        self.lastEarningsUpdate = None


    def getRadiusData(self):
        jsonUrl = url+'data.json'
        try:
            resp = urequests.get(jsonUrl)
            if resp.reason!=b'OK':
                self.display.writeXY("Error getRadiusData", 1, 0, 0)
            tmp = resp.json()
            activeImport = tmp['i']
            activeExport = tmp['e']
            if activeExport: 
                self.display.writeXY(str(-activeExport), 0, 1, 0)
            else:
                self.display.writeXY(str(activeImport), 1, 1, 0)
        except:
            return self.old
        self.old = activeImport, activeExport
        return self.old


    # Correct from increment 
    def myCorrectEarningScale(self, x):
        return x / 1000 / 100 / (60*60/self.pollingTime)


    def UpdateEarnings(self, powerImportExport):
        powerImport, powerExport = powerImportExport
        tmp = powerExport*self.exportPrice - powerImport*self.importPrice # øre/time * 1000
        self.earningsToday += tmp
        res = tmp/1000/100 # kr/h. W->kW, øre->kr

        if powerExport:
            effPrice = self.exportPrice/100
        else:
            effPrice = self.importPrice/100
        self.display.writeXY("{:.02f}".format(effPrice), powerExport==0, 0, 0)
        self.display.writeXY("{:.02f}".format(-res), res<0, 1, 2)
        forbrugDag = self.myCorrectEarningScale(-self.earningsToday)
        self.display.writeXY("{:.02f}".format(forbrugDag), forbrugDag>0, 0, 2)


    def __call__(self, prices):
        self.importPrice, self.exportPrice = prices
        self.importExport = self.getRadiusData()
        self.UpdateEarnings(self.importExport)

        if self.call_cnt == 0: 
            self.call_cnt = 60/self.pollingTime # 1 min
            now = utime.localtime()  # (y, m, d, h, m, s, wd, yd)
            if self.lastEarningsUpdate != now[2]: # day
                self.lastEarningsUpdate = now[2]
                self.earningsYesterday = self.earningsToday
                self.earningsToday = 0
        else:
            self.call_cnt -= 1

# end radiusApi_class


def main():

    screen = M5Screen()
    screen.clean_screen()
    screen.set_screen_bg_color(0x000000)
    screen.set_screen_brightness(60)

    do_connect() # WiFi

    ntp = ntptime.client(host='dk.pool.ntp.org', timezone=2)
    ntp.getTimestamp()

    pollingTime = 10 # seconds

    # Init classes
    displayClass = display_class()
    powerCostApi = powerCostApi_class(pollingTime, ntp, displayClass)
    radiusApi = radiusApi_class(pollingTime, displayClass)

    while True:
    # for x in range(10):
    # if 1: # once

        t1 = int(utime.ticks_ms()/1000)

        powerCostApi()
        radiusApi(powerCostApi.getCurrentPrices())

        t2 = int(utime.ticks_ms()/1000)

        # tmp = t2-t1
        # displayClass.writeXY("N {}".format(tmp), 1, 1, 1)
        # displayClass.writeXY("X {}".format(x), 1, 1, 2)

        utime.sleep(max(pollingTime-(t2-t1), 0))


# For misc debug
def main1():

    screen = M5Screen()
    screen.clean_screen()
    screen.set_screen_bg_color(0x000000)
    screen.set_screen_brightness(50)
    lcd.font(lcd.FONT_DejaVu24)
    lcd.print("Top:\n", 0, 0)

    lcd.print(str(dir(screen)[10:]))
    lcd.print('\n')

    # lcd.writecommand(ILI9341_DISPOFF)
    # lcd.setBrightness(0)


main()
