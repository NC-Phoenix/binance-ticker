import sys
import cursor
import websocket
import json

from os import system, name, get_terminal_size
from time import strftime, localtime
from colorama import init, Fore

isDebugMode = False
sWsSend = ""
sTickerWs = ""
sTickerType = ""
prevEventTime = 0
prevTerminalSize = ""
lSymbol = []
lTicker = []
lTickerWs = []
dPattern = {}
dPrice = {}
dPrevPrice = {}

class PatternType():
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    DATA = "DATA"

class TickerType():
    AGG_TRADE = "@aggTrade"
    TICKER = "@ticker" 

class PriceColor():
    HEADER = "YELLOW"
    UNCHANGED = "WHITE"
    UP = "GREEN"
    DOWN = "RED"

class Config():
    COLUMN_WIDTH = 15
    COLUMN_PADDING_LEFT = 1
    COLUMN_PADDING_RIGHT = COLUMN_WIDTH-COLUMN_PADDING_LEFT
    DEFAULT_TICKER = "USDT"
    DEFAULT_TICKER_SEPARATOR_WS = ""
    DEFAULT_TICKER_SEPARATOR_DISP = "/"
    PRICE_COLOR = "YELLOW CYAN WHITE GREEN RED"
    LAST_PRICE_COLOR_CHANGE_MODE = 1
    USE_THOUSAND_SPERATOR = "F"
    THOUSAND_SPERATOR_SYMBOL = ","
    DECIMAL_SPERATOR_SYMBOL = "."
    EVENT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    TICKER_LIST = ""
    TICKER_TYPE = "TICKER"
    TICKER_STRING_CASE = "L" # L = Lowercase, U = Uppercase

def setPriceColor():
    lPcConf = Config.PRICE_COLOR
    lPc = lPcConf
    lPc[0] = getattr(Fore, lPcConf[0])
    setattr(PriceColor, "HEADER", lPc[0])
    lPc[1] = getattr(Fore, lPcConf[1])
    setattr(PriceColor, "FOOTER", lPc[1])
    lPc[2] = getattr(Fore, lPcConf[2])
    setattr(PriceColor, "UNCHANGED", lPc[2])
    lPc[3] = getattr(Fore, lPcConf[3])
    setattr(PriceColor, "UP", lPc[3])
    lPc[4] = getattr(Fore, lPcConf[4])
    setattr(PriceColor, "DOWN", lPc[4])

def printConfigFileError(fileName):
    print("Config file \"" + fileName + "\" not found")
    sys.exit()

def printConfigError(name):
    print("Config \"" + name + "\" is not vaild.")
    sys.exit()

def readAndSetConfig():
    sFileName = "binance_ticker.conf"
    try: sFileName = sys.argv[1]
    except IndexError: pass
    try:
        file = open(sFileName, "r")
    except FileNotFoundError:
        printConfigFileError(sFileName)

    lLine = file.readlines()
    for line in lLine:
        line = line.strip()
        if(line.find("#", 0, 1)==-1): # skip commented lines
            if(line.strip()):
                lConf = line.split("=")
                try:
                    name = lConf[0]
                    nameU = name.upper()
                    confValOld = getattr(Config, nameU) # Check attribute in config class is exist
                    confValNew = ""
                    if(nameU=="EVENT_TIME_FORMAT"):
                        confValNew = lConf[1]
                    else:
                        confValNew = int(lConf[1]) if lConf[1].isdigit() else lConf[1].upper() # Convert value to int if value is number
                    if(confValNew!=""): # Check value is not empty
                        if(type(confValOld)!=type(confValNew)):
                            printConfigError(name)
                        else:
                            setattr(Config, nameU, confValNew)
                    else:
                        printConfigError(name)
                except IndexError: # If value is empty, Print error
                    printConfigError(name)
                except AttributeError: # If attribute not exist, skip it.
                    pass
    setattr(Config, "COLUMN_PADDING_RIGHT", Config.COLUMN_WIDTH-Config.COLUMN_PADDING_LEFT)
    setattr(Config, "TICKER_LIST", Config.TICKER_LIST.upper().split(" "))
    setattr(Config, "PRICE_COLOR", Config.PRICE_COLOR.upper().split(" "))
    setPriceColor()

def moveCursorPos(line, column):
    # Move console cursor position
    # String format: "\033[<line>;<column>f"
    print("\033[" + str(line) + ";" + str(column) + "f", end="", flush=True)

def floatFormat(num, addPlusSign=False):
    if(type(num)==int or type(num)==float):
        # Check config and add plus sign and thoundsand sperator
        # Use "{:f}" format to suppress scientific notation
        # Use rstrip function to cut trailing zeros from decimal and symbol if no any decimal place remaining
        s = ""
        if(Config.USE_THOUSAND_SPERATOR=="T"):
            s = (("{:,f}", "{:+,f}") [addPlusSign]).format(num).rstrip("0").rstrip('.')
        else:
            s = (("{:f}", "{:+f}") [addPlusSign]).format(num).rstrip("0").rstrip('.')
        # Replace space word to real space
        ds = Config.DECIMAL_SPERATOR_SYMBOL
        ts = Config.THOUSAND_SPERATOR_SYMBOL
        ds = ds.replace("SPACE", " ")
        ts = ts.replace("SPACE", " ")
        # replace thoundsand and decimal sperator symbol with symbol from config
        s = s.replace(".", "*DS*")
        s = s.replace(",", "*TS*")
        s = s.replace("*DS*", ds)
        s = s.replace("*TS*", ts)
        return s
    else:
        # Return value if value type is not number (prevent format type error)
        return num

def clearScreen():
    # for windows
    if(name=="nt"):
        _ = system("cls")
    # for mac and linux(here, os.name is 'posix')
    else:
        _ = system("clear")

def ckStrCase(s):
    # Covert string to uppercase or lowercase
    if(Config.TICKER_STRING_CASE=="H"):
        return s.upper()
    elif(Config.TICKER_STRING_CASE=="L"):
        return s.lower()

def fcPattern(s, fc=Fore.WHITE):
    # Make foreground color pattern
    # Create color first. Then text. Finally reset color
    return fc + str(s) + Fore.RESET

def ckNumFcPattern(n):
    # check foreground color pattern for positive, negative, zero number
    if(n>0):
        return PriceColor.UP
    else:
        return (PriceColor.UNCHANGED, PriceColor.DOWN) [n<0]

def ckNumDiffFcPattern(n1, n2, fcMode3=""):
    # check foreground color pattern for different between previous and current number
    mode = Config.LAST_PRICE_COLOR_CHANGE_MODE
    # Use price unchanged color only in mode 4
    if(mode==4):
        return PriceColor.UNCHANGED
    # Set color same as price change in mode 3
    elif(mode==3):
        return fcMode3
    # Set color to unchanged in mode 1 only
    elif(n1=="" or n2=="" or (mode==1 and n1==n2)):
        return PriceColor.UNCHANGED
    # Set color when last price change in mode 1 and 2 
    elif((mode==1 or mode==2) and n1>n2):
        return PriceColor.UP
    elif((mode==1 or mode==2) and n1<n2):
        return PriceColor.DOWN

def fillSpace(s=""):
    # Fill space to right of the string
    return ("{: <"+str(Config.COLUMN_PADDING_RIGHT)+"}").format(s)

def getTickerFormat():
    # Define ticker format from ticker type
    if(sTickerType==TickerType.AGG_TRADE):
        return [
            fillSpace("Symbol"),
            fillSpace("Last Price")
        ]
    if(sTickerType==TickerType.TICKER):
        return [
            fillSpace("Symbol"),
            fillSpace("Last Price"),
            fillSpace("24h Change"),
            fillSpace("24h Change %")
        ]

def setTickerType():
    # Check ticker type from second input arguments
    # Using value from class TickerType
    global sTickerType
    sTickerType = getattr(TickerType, Config.TICKER_TYPE)

def symbolCreate():
    global lSymbol
    lSymbol = Config.TICKER_LIST
    for i in range(0, len(lSymbol)):
        s = lSymbol[i]
        if(s.find(Config.DEFAULT_TICKER_SEPARATOR_DISP)==-1):
            s = s + Config.DEFAULT_TICKER_SEPARATOR_DISP + Config.DEFAULT_TICKER
        lSymbol[i] = s.upper()

def tickerCreate():
    global sTickerWs
    global lTicker
    global lTickerWs
    for s in lSymbol:
        st = ""
        if(s.find(Config.DEFAULT_TICKER_SEPARATOR_DISP)!=-1):
            st = s.replace(Config.DEFAULT_TICKER_SEPARATOR_DISP, Config.DEFAULT_TICKER_SEPARATOR_WS)
        st = ckStrCase(st)
        lTicker.append(st)
    lTickerWs = ["\"" + s + sTickerType + "\"" for s in lTicker]
    sTickerWs = ",".join(lTickerWs)

def wsSendMsgCreate():
    global sWsSend
    sWsSend = "{ \
        \"method\": \"SUBSCRIBE\", \
        \"params\": [ " + \
        sTickerWs + \
        "], \
        \"id\": 1 \
    }"

def dPatternInsertRow(pType=PatternType.DATA, text=""):
    # Insert Row Pattern
    global dPattern
    if(pType==PatternType.FOOTER):
        dPattern.update([(pType, text)])
    else:
        lTickerFormat = getTickerFormat()
        s = "|L{}"
        s = len(lTickerFormat)*s
        s = s.replace("L", " "*Config.COLUMN_PADDING_LEFT)
        if(pType==PatternType.HEADER):
            s = s.replace("|", " ")
            s = s.format(*lTickerFormat)
        dPattern.update([(pType, s)])

def dPrevPriceUpdateData(idx):
    global dPrevPrice
    price = ""
    if(idx in dPrevPrice):
        if(sTickerType==TickerType.AGG_TRADE):
            price = dPrice[idx]["p"]
        elif(sTickerType==TickerType.TICKER):
            price = dPrice[idx]["c"]
    dPrevPrice.update([(idx, price)])
    
def prevEventTimeUpdateData(time):
    global prevEventTime
    prevEventTime = time

def printHeader():
    # Print header with space and color
    print(fcPattern(dPattern[PatternType.HEADER], PriceColor.HEADER))

def dPriceUpdateData(idx, dData={}):
    # If any data and index, update data. Else, create new data
    global dPrice
    if(len(dData)>0 and idx in dPrice):
        if(sTickerType==TickerType.AGG_TRADE):
            dPrice[idx]["p"] = float(dData["lastPrice"])
            dPrice[idx]["E"] = float(dData["eventTime"])
            dPrice[idx]["p_fc"] = ckNumDiffFcPattern(dPrice[idx]["p"], dPrevPrice[idx])
        elif(sTickerType==TickerType.TICKER):
            dPrice[idx]["p"] = float(dData["priceChange"])
            dPrice[idx]["P"] = float(dData["priceChangePercent"])
            dPrice[idx]["c"] = float(dData["lastPrice"])
            dPrice[idx]["E"] = float(dData["eventTime"])
            dPrice[idx]["p_fc"] = ckNumFcPattern(dPrice[idx]["p"])
            dPrice[idx]["P_fc"] = ckNumFcPattern(dPrice[idx]["p"])
            dPrice[idx]["c_fc"] = ckNumDiffFcPattern(dPrice[idx]["c"], dPrevPrice[idx], dPrice[idx]["P_fc"])
    else:
        dPrice.update([(idx, {})])
        dPrice[idx]["s"] = idx
        dPrice[idx]["s_disp"] = lSymbol[lTicker.index(idx.lower())]
        if(sTickerType==TickerType.AGG_TRADE):
            dPrice[idx]["p"] = "x"
            dPrice[idx]["E"] = "x"
            dPrice[idx]["p_fc"] = Fore.WHITE
        elif(sTickerType==TickerType.TICKER):
            dPrice[idx]["p"] = "x"
            dPrice[idx]["P"] = "x"
            dPrice[idx]["c"] = "x"
            dPrice[idx]["E"] = "x"
            dPrice[idx]["p_fc"] = Fore.WHITE
            dPrice[idx]["P_fc"] = Fore.WHITE
            dPrice[idx]["c_fc"] = Fore.WHITE

def printPriceData(idx):
    # Move cursor (Line = dPattern index + 1, Column = 1)
    moveCursorPos(list(dPattern).index(idx)+1, 1)
    # Print price data with space and color
    if(sTickerType==TickerType.AGG_TRADE):
        print(dPattern[idx].format(
            fcPattern(fillSpace(dPrice[idx]["s_disp"])),
            fcPattern(fillSpace(floatFormat(dPrice[idx]["p"])), dPrice[idx]["p_fc"])
        ))
    elif(sTickerType==TickerType.TICKER):
        print(dPattern[idx].format(
            fcPattern(fillSpace(dPrice[idx]["s_disp"])),
            fcPattern(fillSpace(floatFormat(dPrice[idx]["c"])), dPrice[idx]["c_fc"]),
            fcPattern(fillSpace(floatFormat(dPrice[idx]["p"], True)), dPrice[idx]["p_fc"]),
            fcPattern(fillSpace(floatFormat(dPrice[idx]["P"], True)), dPrice[idx]["P_fc"])
        ))

def printFooterData(idx, lData=[]):
    # Move cursor (Line = dPattern index + 1, Column = 1)
    moveCursorPos(list(dPattern).index(idx)+1, 1)
    # Print footer with space and color
    print(fcPattern(dPattern[idx].format(*lData), PriceColor.FOOTER))

def printAllData(lFooterData=[]):
    # Force print all data
    for p in dPattern:
        if(p==PatternType.HEADER):
            printHeader()
        elif(p==PatternType.FOOTER):
            printFooterData(p, lFooterData)
        else:
            printPriceData(p)

def ckTerminalSize(lFooterData=[]):
    # If terminal size changed, clear screen and force print all data
    global prevTerminalSize
    size = get_terminal_size()
    if(prevTerminalSize!="" and size!=prevTerminalSize):
        clearScreen()
        printAllData(lFooterData)
    prevTerminalSize = size

def msgToData(msg):
    # Convert WebSocket message to data
    dData = {}
    dMsg = json.loads(msg)
    if(sTickerType==TickerType.AGG_TRADE):
        dData["symbol"] = dMsg["s"]
        dData["lastPrice"] = dMsg["p"]
        dData["eventTime"] = dMsg["E"]
    elif(sTickerType==TickerType.TICKER):
        dData["symbol"] = dMsg["s"]
        dData["priceChange"] = dMsg["p"]
        dData["priceChangePercent"] = dMsg["P"]
        dData["lastPrice"] = dMsg["c"]
        dData["eventTime"] = dMsg["E"]
    return dData

def printData(dData):
    lFooterData = []
    for p in dPattern:
        if(p==dData["symbol"]):
            # Update price
            dPriceUpdateData(p, dData)
            # Print price
            printPriceData(p)
            # Update previous price
            dPrevPriceUpdateData(p)
        elif(p==PatternType.FOOTER):
            # Remove Milliseconds
            eventTime = float(dData["eventTime"] / 1000)
            # Update time if time is more than previous time
            if(eventTime>prevEventTime):
                # Convert epoch to formatted time
                sEventTime = strftime(Config.EVENT_TIME_FORMAT, localtime(eventTime))
                lFooterData = [sEventTime]
                # Print time
                printFooterData(p, lFooterData)
                # Update previous time
                prevEventTimeUpdateData(eventTime)
    ckTerminalSize(lFooterData)

def initVar():
    readAndSetConfig()
    setTickerType()
    symbolCreate()
    tickerCreate()
    wsSendMsgCreate()
    dPatternInsertRow(PatternType.HEADER)
    printHeader()
    for t in lTicker:
        tu = t.upper()
        dPatternInsertRow(tu)
        dPriceUpdateData(tu)
        printPriceData(tu)
        dPrevPriceUpdateData(tu)
    dPatternInsertRow(PatternType.FOOTER, "Last Event Time: {}\nPress Ctrl+C to exit.")
    printFooterData(PatternType.FOOTER, ["x"])

def on_open(wsApp):
    wsApp.send(sWsSend)

def on_message(wsApp, msg):
    if(isDebugMode):
        print(msg)
    else:
        dData = msgToData(msg)
        printData(dData)

def on_ping(wsApp, msg):
    if(isDebugMode):
        print("Got a ping! A pong reply has already been automatically sent.")
    else:
        pass

def on_pong(wsApp, msg):
    if(isDebugMode):
        print("Got a pong! No need to respond")
    else:
        pass

def runWsApp():
    global wsApp
    wsApp = websocket.WebSocketApp(
        "wss://stream.binance.com:9443/ws",
        on_open = on_open,
        on_message = on_message,
        on_ping = on_ping,
        on_pong = on_pong
    )
    wsApp.run_forever(reconnect=5)

# Init Colorama module
init()

# Clear console screen first
clearScreen()

# Init Variable
initVar()

# Hide cursor before run WebSocket
cursor.hide()

# Then, Run WebSocket
runWsApp()

# Finally, Clear console screen and show cursor again when exit WebSocket
clearScreen()
cursor.show()
