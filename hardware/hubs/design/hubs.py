"""AgriNode hub family — one small board per hub type, sharing a common core.

    HUB-W   Wi-Fi hub                          core only
    HUB-L   hub with LoRa uplink               core + Ra-02 (SX1278 433 MHz)
    HUB-C   hub with 4G uplink                 core + header for an LTE carrier board (A7670E / EC200U)
    GW-LAN  LoRa receiver -> LAN gateway       core + Ra-02 + ENC28J60 + RJ45

Core: ESP32-WROOM-32E, 12 V jack/terminal + solar 6-24 V + USB-B inputs, 18650 cell with
TP4056 charger and power path, 3.3 V LDO, DS3231M RTC with CR2032, USB programming port
(CH340C + auto-reset) and 6-pin PROG header, RESET and BOOT/PAIR buttons, WS2813 LED-strip
header, buzzer, I2C header, optional RS-485 (Modbus).

Fabrication rules: 2-layer board (the single-sided trial needed ~50 wire jumpers), 0.5 mm tracks /
0.5 mm clearance, 0.6/1.2 mm vias, only 1206 / SOT-23 / SOT-223 / SOIC / TO-263 SMD parts, all on top.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "kigen"))

import symlib  # noqa: E402

symlib.add_lib_dir(os.path.join(HERE, "..", "..", "lib"))

from circuit import NC, Circuit  # noqa: E402

VARIANTS = {
    "hub-w": ("AgriNode HUB-W (Wi-Fi hub)", set()),
    "hub-l": ("AgriNode HUB-L (LoRa hub)", {"LORA"}),
    "hub-c": ("AgriNode HUB-C (4G hub)", {"LTE"}),
    "gw-lan": ("AgriNode GW-LAN (LoRa to Ethernet gateway)", {"LORA", "ETH"}),
}

R1206 = "Resistor_SMD:R_1206_3216Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
L1206 = "Inductor_SMD:L_1206_3216Metric"
SMA = "Diode_SMD:D_SMA"
SMB = "Diode_SMD:D_SMB"
SMC = "Diode_SMD:D_SMC"
SOD123 = "Diode_SMD:D_SOD-123"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
CP8 = "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm"
CP10 = "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"
PTC1812 = "Fuse:Fuse_1812_4532Metric"
BTN = "Button_Switch_THT:SW_PUSH_6mm"


def term(n):
    return "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-%d-5.08_1x%02d_P5.08mm_Horizontal" % (n, n)


def header(n):
    return "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical" % n


def make(variant):
    title, opts = VARIANTS[variant]
    c = Circuit("agrinode_" + variant.replace("-", "_"), title, rev="A", company="AgriNode", date="2026-09-27")

    def R(s, value, a, b):
        return s.part("Device:R", "R", value, R1206).c({"1": a, "2": b})

    def C(s, value, a, b="GND", fp=C1206):
        return s.part("Device:C", "C", value, fp).c({"1": a, "2": b})

    def CP(s, value, a, b="GND", fp=CP8):
        return s.part("Device:C_Polarized", "C", value, fp).c({"1": a, "2": b})

    def JMP(s, value, a, b):
        return s.part("Device:R", "JP", value, R1206).c({"1": a, "2": b})

    def terminal(s, name, nets):
        n = len(nets)
        j = s.part("Connector:Screw_Terminal_01x%02d" % n, "J", name, term(n))
        j.c({str(i + 1): net for i, net in enumerate(nets)})
        return j

    # ==================================================================== power
    pw = c.sheet("power", "Power - 12V, solar and USB inputs, 18650 charger, rails")

    pw.block("Inputs: 12 V adapter (jack + terminal), solar 6-24 V, USB 5 V",
             "each input fused and reverse-polarity protected; any combination may be connected")
    pw.part("Connector:Barrel_Jack_Switch", "J", "DC 12V 5.5/2.1", "Connector_BarrelJack:BarrelJack_Horizontal").c(
        {"1": "VDC_RAW", "2": "GND", "3": "GND"})
    terminal(pw, "DC IN 7-24V", ["VDC_RAW", "GND"])
    terminal(pw, "SOLAR 6-24V", ["VSOL_RAW", "GND"])
    pw.part("Connector:USB_B", "J", "USB 5V / PROG", "agrinode:USB_B_THT_Coarse").c(
        {"VBUS": "VUSB_RAW", "GND": "GND", "Shield": "GND", "D+": "USB_DP", "D-": "USB_DN"})
    pw.part("Device:Polyfuse", "F", "PTC 1.5A/30V", PTC1812).c({"1": "VDC_RAW", "2": "VDC_F"})
    pw.part("Device:Polyfuse", "F", "PTC 1.5A/30V", PTC1812).c({"1": "VSOL_RAW", "2": "VSOL_F"})
    pw.part("Device:Polyfuse", "F", "PTC 1.5A/8V", PTC1812).c({"1": "VUSB_RAW", "2": "VUSB_F"})
    pw.part("Device:D_Schottky", "D", "SS54 40V/5A", SMC).c(A="VDC_F", K="VIN_BUCK")
    pw.part("Device:D_Schottky", "D", "SS54 40V/5A", SMC).c(A="VSOL_F", K="VIN_BUCK")
    pw.part("Device:D_TVS", "D", "SMBJ24CA", SMB).c(A1="VIN_BUCK", A2="GND")
    pw.part("Device:D_TVS", "D", "SMBJ6.0CA", SMB).c(A1="VUSB_F", A2="GND")
    pw.pwr_flag("GND")

    pw.block("5 V buck (LM2596S-5, 7-40 V in, 3 A)")
    u = pw.part("Regulator_Switching:LM2596S-5", "U", "LM2596S-5.0")
    u.c({"VIN": "VIN_BUCK", "~{ON}/OFF": "GND", "GND": "GND", "OUT": "BUCK_SW", "FB": "V5_BUCK"})
    CP(pw, "220u/35V", "VIN_BUCK")
    C(pw, "1u/50V", "VIN_BUCK")
    pw.part("Device:D_Schottky", "D", "SS54 40V/5A", SMC).c(K="BUCK_SW", A="GND")
    pw.part("Device:L", "L", "33uH 3A", "Inductor_SMD:L_12x12mm_H6mm").c({"1": "BUCK_SW", "2": "V5_BUCK"})
    CP(pw, "220u/10V", "V5_BUCK")
    C(pw, "1u", "V5_BUCK")
    pw.pwr_flag("VIN_BUCK")

    pw.block("5 V bus (diode-OR of buck and USB)")
    pw.part("Device:D_Schottky", "D", "SS34", SMA).c(A="V5_BUCK", K="V5")
    pw.part("Device:D_Schottky", "D", "SS34", SMA).c(A="VUSB_F", K="V5")
    C(pw, "10u", "V5")
    pw.pwr_flag("V5")

    pw.block("18650 charger (TP4056, 1 A) with battery temperature guard",
             "NTC 10k B3950 on the cell: charge only 0..45 C. No NTC: fit JP_NTC (TEMP to GND)")
    u = pw.part("agrinode:TP4056", "U", "TP4056")
    u.c({"VCC": "V5", "CE": "V5", "TEMP": "CHG_TEMP", "PROG": "CHG_PROG", "BAT": "VBAT",
         "~{CHRG}": "CHRG_N", "~{STDBY}": NC, "GND": "GND"})
    C(pw, "10u", "V5")
    R(pw, "1.2k", "CHG_PROG", "GND")
    R(pw, "5.6k", "V5", "CHG_TEMP")
    R(pw, "75k", "CHG_TEMP", "GND")
    pw.part("Connector_Generic:Conn_01x02", "J", "BAT NTC 10k", header(2)).c({"1": "CHG_TEMP", "2": "GND"})
    JMP(pw, "0R JP_NTC (fit if no NTC)", "CHG_TEMP", "GND")
    C(pw, "10u", "VBAT")

    pw.block("18650 cell: holder, fuse, reverse-insertion protection")
    pw.part("Device:Battery_Cell", "BT", "18650 Li-ion (protected)", "Battery:BatteryHolder_MPD_BH-18650-PC2").c(
        {"+": "BATT_CELL", "-": "GND"})
    pw.part("Device:Polyfuse", "F", "PTC 3A/16V", PTC1812).c({"1": "BATT_CELL", "2": "BATT_P"})
    pw.part("Transistor_FET:AO3401A", "Q", "AO3401A").c(D="BATT_P", S="VBAT", G="BATT_G")
    R(pw, "1k", "BATT_G", "GND")

    pw.block("Power path: 5 V bus when present, battery otherwise (no gap)")
    pw.part("Device:D_Schottky", "D", "SS34", SMA).c(A="V5", K="VSYS")
    pw.part("Transistor_FET:AO3401A", "Q", "AO3401A").c(D="VBAT", S="VSYS", G="V5")
    R(pw, "100k", "V5", "GND")
    CP(pw, "220u/10V", "VSYS")
    pw.pwr_flag("VSYS")

    pw.block("3.3 V rail (MIC29302, low dropout, 3 A)", "Vout = 1.24 x (1 + 16.5k/10k) = 3.29 V")
    u = pw.part("Regulator_Linear:MIC29302WU", "U", "MIC29302WU")
    u.c(VIN="VSYS", EN="LDO3_EN", GND="GND", VOUT="+3V3", ADJ="LDO3_ADJ")
    R(pw, "47k", "VSYS", "LDO3_EN")
    R(pw, "16.5k 1%", "+3V3", "LDO3_ADJ")
    R(pw, "10k 1%", "LDO3_ADJ", "GND")
    C(pw, "10u", "VSYS")
    CP(pw, "100u/10V", "+3V3")
    C(pw, "1u", "+3V3")

    pw.block("Supply monitoring (ADC1)", "VBAT: 100k/100k   VIN: 330k/47k (24 V -> 3.0 V)")
    R(pw, "100k 1%", "VBAT", "VBAT_ADC")
    R(pw, "100k 1%", "VBAT_ADC", "GND")
    C(pw, "100n", "VBAT_ADC")
    R(pw, "330k 1%", "VIN_BUCK", "VIN_ADC")
    R(pw, "47k 1%", "VIN_ADC", "GND")
    C(pw, "100n", "VIN_ADC")

    pw.block("Mounting holes (M3)")
    for _ in range(4):
        pw.part("Mechanical:MountingHole", "H", "M3", "MountingHole:MountingHole_3.2mm_M3")

    # ====================================================================== mcu
    mc = c.sheet("mcu", "ESP32, programming, buttons, RTC, LED strip, buzzer")
    used = {"LORA": "LORA" in opts, "ETH": "ETH" in opts, "LTE": "LTE" in opts}

    mc.block("ESP32-WROOM-32E")
    # GPIOs are chosen by where the parts sit: the module's right column faces the RS-485 / uplink
    # blocks, its left column the power and front-panel side, its bottom row the charger.
    pins = {"VDD": "+3V3", "GND": "GND", "EN": "ESP_EN", "IO0": "BOOT_BTN", "TXD0/IO1": "ESP_TXD0",
            "RXD0/IO3": "ESP_RXD0", "IO2": "BUZZER_CTL", "IO13": "CHRG_N",
            "IO33": "I2C_SDA", "IO32": "I2C_SCL", "IO27": "LED_DATA",
            "IO34": "VBAT_ADC", "IO35": "VIN_ADC",
            "IO17": "RS485_TX", "IO16": "RS485_RX", "IO4": "RS485_DE"}
    for io in ("IO5", "IO12", "IO14", "IO15", "IO18", "IO19", "IO21", "IO22", "IO23", "IO25", "IO26",
               "SENSOR_VP", "SENSOR_VN"):
        pins[io] = NC
    if used["LORA"] or used["ETH"]:
        pins.update({"IO18": "SPI_SCK", "IO19": "SPI_MISO", "IO23": "SPI_MOSI"})
    if used["LORA"]:
        pins.update({"IO5": "LORA_CS", "IO21": "LORA_DIO0"})
        pins["IO14" if used["ETH"] else "IO22"] = "LORA_RST"
    if used["ETH"]:
        pins.update({"IO22": "ETH_CS", "SENSOR_VP": "ETH_INT"})
    if used["LTE"]:
        pins.update({"IO19": "MODEM_RXD", "IO23": "MODEM_TXD", "IO21": "MODEM_PWRKEY_CTL",
                     "IO22": "MODEM_EN", "IO18": "MODEM_STATUS"})
    mc.part("RF_Module:ESP32-WROOM-32E", "U", "ESP32-WROOM-32E-N8", "agrinode:ESP32-WROOM-32E_Coarse").c(pins)
    C(mc, "22u", "+3V3")
    C(mc, "100n", "+3V3")
    C(mc, "100n", "+3V3")

    mc.block("Reset and boot/pair buttons")
    R(mc, "10k", "+3V3", "ESP_EN")
    C(mc, "1u", "ESP_EN")
    mc.part("Switch:SW_Push", "SW", "RESET", BTN).c({"1": "ESP_EN", "2": "GND"})
    R(mc, "10k", "+3V3", "BOOT_BTN")
    mc.part("Switch:SW_Push", "SW", "BOOT / PAIR", BTN).c({"1": "BOOT_BTN", "2": "GND"})

    mc.block("USB programming port (CH340C on the USB-B jack, auto-reset) + PROG header",
             "PROG: 1 GND  2 TXD0  3 RXD0  4 3V3  5 EN  6 IO0")
    u = mc.part("Interface_USB:CH340C", "U", "CH340C")
    u.c({"VCC": "+3V3", "V3": "+3V3", "GND": "GND", "UD+": "USB_DP_C", "UD-": "USB_DN_C", "R232": "GND",
         "TXD": "CH_TXD", "RXD": "CH_RXD", "~{DTR}": "CH_DTR", "~{RTS}": "CH_RTS",
         "~{OUT}/~{DTR}": NC, "~{CTS}": NC, "~{DSR}": NC, "~{RI}": NC, "~{DCD}": NC})
    C(mc, "100n", "+3V3")
    R(mc, "22", "USB_DP", "USB_DP_C")
    R(mc, "22", "USB_DN", "USB_DN_C")
    R(mc, "1k", "CH_TXD", "ESP_RXD0")      # header can override: series resistors from CH340C
    R(mc, "1k", "CH_RXD", "ESP_TXD0")
    # classic ESP32 auto-reset: DTR/RTS cross-coupled NPN pair
    R(mc, "10k", "CH_DTR", "AR_B1")
    R(mc, "10k", "CH_RTS", "AR_B2")
    mc.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="AR_B1", E="CH_RTS", C="ESP_EN")
    mc.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="AR_B2", E="CH_DTR", C="BOOT_BTN")
    mc.part("Connector_Generic:Conn_01x06", "J", "PROG", header(6)).c(
        {"1": "GND", "2": "ESP_TXD0", "3": "ESP_RXD0", "4": "+3V3", "5": "ESP_EN", "6": "BOOT_BTN"})

    mc.block("RTC with backup cell (DS3231M) + I2C header (OLED / sensors)")
    u = mc.part("Timer_RTC:DS3231MZ", "U", "DS3231MZ")
    u.c(VCC="+3V3", GND="GND", VBAT="RTC_VBAT", SDA="I2C_SDA", SCL="I2C_SCL")
    u.c({"~{INT}/SQW": NC, "32KHZ": NC, "~{RST}": NC})
    C(mc, "100n", "+3V3")
    mc.part("Device:Battery_Cell", "BT", "CR2032", "Battery:BatteryHolder_Keystone_500").c(
        {"+": "RTC_VBAT", "-": "GND"})
    R(mc, "4.7k", "+3V3", "I2C_SDA")
    R(mc, "4.7k", "+3V3", "I2C_SCL")
    mc.part("Connector_Generic:Conn_01x04", "J", "I2C", header(4)).c(
        {"1": "GND", "2": "+3V3", "3": "I2C_SCL", "4": "I2C_SDA"})

    mc.block("WS2813 LED strip header (status LEDs on the enclosure front)",
             "strip order: 1 power/battery 2 Wi-Fi/nodes 3 uplink 4 LoRa/LAN 5 alarm 6 system")
    R(mc, "4.7k", "+3V3", "LED_DATA")
    mc.part("Transistor_FET:BSS138", "Q", "BSS138").c(G="+3V3", S="LED_DATA", D="LED_DIN5")
    R(mc, "2.2k", "VLED", "LED_DIN5")
    R(mc, "330", "LED_DIN5", "LED_DIN")
    mc.part("Device:Polyfuse", "F", "PTC 0.75A/16V", PTC1812).c({"1": "VSYS", "2": "VLED"})
    C(mc, "22u", "VLED")
    mc.part("Connector_Generic:Conn_01x04", "J", "LED STRIP WS2813", header(4)).c(
        {"1": "VLED", "2": "LED_DIN", "3": "GND", "4": "GND"})

    mc.block("Buzzer (alarm)")
    R(mc, "1k", "BUZZER_CTL", "BUZ_B")
    R(mc, "10k", "BUZ_B", "GND")
    mc.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="BUZ_B", E="GND", C="BUZ_K")
    mc.part("Device:Buzzer", "BZ", "5V magnetic buzzer", "Buzzer_Beeper:Buzzer_12x9.5RM7.6").c(
        {"+": "VSYS", "-": "BUZ_K"})
    mc.part("Device:D", "D", "1N4148W", SOD123).c(A="BUZ_K", K="VSYS")

    # ==================================================================== comms
    cm = c.sheet("comms", "RS-485 and uplink")

    cm.block("RS-485 / Modbus RTU (wired industrial sensors, up to 1 km)", option="RS485")
    u = cm.part("Interface_UART:MAX3485", "U", "MAX3485ESA", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    u.c(RO="RS485_RX", DI="RS485_TX", DE="RS485_DE", VCC="+3V3", GND="GND", A="RS485_A", B="RS485_B")
    u.c({"~{RE}": "RS485_DE"})
    C(cm, "100n", "+3V3")
    R(cm, "10k", "RS485_DE", "GND")
    cm.part("Diode:SM712_SOT23", "D", "SM712").c(A1="RS485_A", A2="RS485_B", common="GND")
    JMP(cm, "0R TERM (end of line)", "RS485_A", "RS485_TERM")
    R(cm, "120", "RS485_TERM", "RS485_B")
    R(cm, "680", "+3V3", "RS485_A")
    R(cm, "680", "RS485_B", "GND")
    terminal(cm, "RS-485", ["RS485_A", "RS485_B", "GND"])

    if used["LORA"]:
        cm.block("LoRa 433 MHz (Ai-Thinker Ra-02, IPEX antenna)")
        u = cm.part("RF_Module:Ai-Thinker-Ra-02", "U", "Ra-02 SX1278 433MHz", "agrinode:Ai-Thinker-Ra-02_Coarse")
        u.c({"VDD": "+3V3", "GND": "GND", "~{RESET}": "LORA_RST", "~{NSS}": "LORA_CS", "SCK": "SPI_SCK",
             "MOSI": "SPI_MOSI", "MISO": "SPI_MISO", "DIO0": "LORA_DIO0",
             "DIO1": NC, "DIO2": NC, "DIO3": NC, "DIO4": NC, "DIO5": NC})
        C(cm, "10u", "+3V3")
        C(cm, "100n", "+3V3")
        R(cm, "10k", "+3V3", "LORA_CS")

    if used["ETH"]:
        cm.block("Ethernet 10BASE-T (ENC28J60 + HR911105A MagJack)")
        u = cm.part("Interface_Ethernet:ENC28J60x-SO", "U", "ENC28J60-I/SO")
        u.c({"VDD": "+3V3", "VDDOSC": "+3V3", "VDDPLL": "+3V3", "VDDRX": "+3V3", "VDDTX": "+3V3",
             "VSS": "GND", "VSSOSC": "GND", "VSSPLL": "GND", "VSSRX": "GND", "VSSTX": "GND",
             "VCAP": "ETH_VCAP", "RBIAS": "ETH_RBIAS", "OSC1": "ETH_OSC1", "OSC2": "ETH_OSC2",
             "~{CS}": "ETH_CS", "SCK": "SPI_SCK", "SI": "SPI_MOSI", "SO": "SPI_MISO", "~{INT}": "ETH_INT",
             "~{RESET}": "ESP_EN", "CLKOUT": NC, "~{WOL}": NC,
             "TPOUT+": "ETH_TXP", "TPOUT-": "ETH_TXN", "TPIN+": "ETH_RXP", "TPIN-": "ETH_RXN",
             "LEDA": "ETH_LEDA", "LEDB": "ETH_LEDB"})
        C(cm, "10u", "ETH_VCAP")
        R(cm, "2.32k 1%", "ETH_RBIAS", "GND")
        cm.part("Device:Crystal", "Y", "25MHz", "Crystal:Crystal_HC49-4H_Vertical").c({"1": "ETH_OSC1", "2": "ETH_OSC2"})
        C(cm, "18p", "ETH_OSC1")
        C(cm, "18p", "ETH_OSC2")
        C(cm, "10u", "+3V3")
        C(cm, "100n", "+3V3")
        C(cm, "100n", "+3V3")
        R(cm, "10k", "+3V3", "ETH_INT")
        R(cm, "10k", "+3V3", "ETH_CS")
        for n in ("ETH_TXP", "ETH_TXN"):
            R(cm, "49.9 1%", n, "ETH_TCT")
        for n in ("ETH_RXP", "ETH_RXN"):
            R(cm, "49.9 1%", n, "ETH_RCT")
        cm.part("Device:FerriteBead_Small", "FB", "600R@100MHz", L1206).c({"1": "+3V3", "2": "ETH_TCT"})
        C(cm, "100n", "ETH_TCT")
        C(cm, "100n", "ETH_RCT")
        j = cm.part("Connector:RJ45_Hanrun_HR911105A_Horizontal", "J", "LAN")
        j.c({"TD+": "ETH_TXP", "TD-": "ETH_TXN", "RD+": "ETH_RXP", "RD-": "ETH_RXN",
             "TCT": "ETH_TCT", "RCT": "ETH_RCT", "8": "GND", "SH": "GND",
             "9": "ETH_LEDG_A", "10": "ETH_LEDA", "12": "ETH_LEDY_A", "11": "ETH_LEDB"})
        R(cm, "330", "+3V3", "ETH_LEDG_A")
        R(cm, "330", "+3V3", "ETH_LEDY_A")

    if used["LTE"]:
        cm.block("4G LTE carrier-board slot (SIMCom A7670E / Quectel EC200U module board)",
                 "switched supply for power-cycling the modem; 3.3 V UART")
        u = cm.part("Regulator_Linear:MIC29302WU", "U", "MIC29302WU")
        u.c(VIN="VSYS", EN="MODEM_EN", GND="GND", VOUT="VMOD_4V", ADJ="LDO4_ADJ")
        R(cm, "100k", "MODEM_EN", "GND")
        R(cm, "22k 1%", "VMOD_4V", "LDO4_ADJ")
        R(cm, "10k 1%", "LDO4_ADJ", "GND")
        CP(cm, "1000u/6.3V low ESR", "VMOD_4V", fp=CP10)
        C(cm, "100n", "VMOD_4V")
        # 5 V feed for module boards with their own regulator (switched, needs external power)
        cm.part("Transistor_FET:AO3401A", "Q", "AO3401A").c(S="V5", D="VMOD_5V", G="MOD5_G")
        R(cm, "10k", "V5", "MOD5_G")
        cm.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="MOD5_B", E="GND", C="MOD5_G")
        R(cm, "4.7k", "MODEM_EN", "MOD5_B")
        CP(cm, "220u/10V", "VMOD_5V")
        R(cm, "4.7k", "MODEM_PWRKEY_CTL", "PWRKEY_B")
        R(cm, "47k", "PWRKEY_B", "GND")
        cm.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="PWRKEY_B", E="GND", C="MOD_PWRKEY")
        R(cm, "1k", "MOD_TXD", "MODEM_RXD")
        R(cm, "1k", "MODEM_TXD", "MOD_RXD")
        R(cm, "1k", "MOD_STATUS", "MODEM_STATUS")
        cm.part("Connector_Generic:Conn_01x08", "J", "LTE MODULE", header(8)).c(
            {"1": "VMOD_5V", "2": "VMOD_4V", "3": "GND", "4": "GND", "5": "MOD_TXD", "6": "MOD_RXD",
             "7": "MOD_PWRKEY", "8": "MOD_STATUS"})
    return c
