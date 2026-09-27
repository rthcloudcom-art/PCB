"""AgriNode MC-1 — main controller board, design source.

Run `python3 build.py` in hardware/main-controller to regenerate the KiCad
schematic, netlist check, BOM and PCB from this file.

Nets are strings. GND/+3V3/+5V are drawn as power symbols; every other net is
a label (global when it crosses sheets).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "kigen"))

from circuit import NC, Circuit  # noqa: E402

# ---------------------------------------------------------------- footprints
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
SMA = "Diode_SMD:D_SMA"
SMB = "Diode_SMD:D_SMB"
SMC = "Diode_SMD:D_SMC"
SOD323 = "Diode_SMD:D_SOD-323"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT23_5 = "Package_TO_SOT_SMD:SOT-23-5"
PTC1206 = "Fuse:Fuse_1206_3216Metric"
PTC2920 = "Fuse:Fuse_2920_7451Metric"
BTN = "Button_Switch_SMD:SW_SPST_PTS645"
JMP_HDR = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
SJ_BRIDGED = "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm"


def mstb(n):
    """Phoenix MSTBA 5.08 mm pluggable terminal header (fits MSTB 2,5/n-ST plug)."""
    return "Connector_Phoenix_MSTB:PhoenixContact_MSTBA_2,5_%d-G-5,08_1x%02d_P5.08mm_Horizontal" % (n, n)


c = Circuit("agrinode_mc", "AgriNode MC-1 Main Controller", rev="A", company="AgriNode", date="2026-09-27")


# ------------------------------------------------------------------ helpers
def R(s, value, a, b, fp=R0603):
    return s.part("Device:R", "R", value, fp).c({"1": a, "2": b})


def C(s, value, a, b="GND", fp=C0603):
    return s.part("Device:C", "C", value, fp).c({"1": a, "2": b})


def CP(s, value, a, b="GND", fp="Capacitor_SMD:CP_Elec_10x10.5"):
    return s.part("Device:C_Polarized", "C", value, fp).c({"1": a, "2": b})


def LED(s, color, anode, cathode):
    return s.part("Device:LED", "D", "LED " + color, LED0603).c(A=anode, K=cathode)


def decouple(s, net, *values):
    for v in values:
        C(s, v, net, "GND", C0805 if v.startswith(("10u", "22u", "4.7u")) else C0603)


def terminal(s, name, nets):
    n = len(nets)
    j = s.part("Connector:Screw_Terminal_01x%02d" % n, "J", name, mstb(n))
    j.c({str(i + 1): net for i, net in enumerate(nets)})
    return j


# ========================================================================
# Sheet: power
# ========================================================================
pw = c.sheet("power", "Power Supply")

pw.block("DC inputs: main 12/24 V + backup battery (diode-OR)",
         "9-32 V DC; each input fused; diode-OR also gives reverse-polarity protection")
terminal(pw, "MAIN IN 9-32V", ["VIN_MAIN_RAW", "GND"])
terminal(pw, "BATTERY IN 9-32V", ["VIN_BAT_RAW", "GND"])
pw.part("Device:Fuse", "F", "PTC 2.5A/60V 2920", PTC2920).c({"1": "VIN_MAIN_RAW", "2": "VIN_MAIN_F"})
pw.part("Device:Fuse", "F", "PTC 2.5A/60V 2920", PTC2920).c({"1": "VIN_BAT_RAW", "2": "VIN_BAT_F"})
pw.part("Device:D_Schottky", "D", "SS510 100V/5A", SMC).c(A="VIN_MAIN_F", K="VSYS")
pw.part("Device:D_Schottky", "D", "SS510 100V/5A", SMC).c(A="VIN_BAT_F", K="VSYS")
pw.part("Device:D_TVS", "D", "SMBJ33CA", SMB).c(A1="VSYS", A2="GND")
CP(pw, "100u/50V", "VSYS")
C(pw, "2.2u/100V", "VSYS", fp=C1210)
pw.pwr_flag("VSYS")
pw.pwr_flag("GND")

pw.block("Field supply outputs (sensors, loads, RS-485 bus power)")
pw.part("Device:Polyfuse", "F", "PTC 3A/60V 2920", PTC2920).c({"1": "VSYS", "2": "VFIELD"})
pw.part("Device:Polyfuse", "F", "PTC 0.5A/60V 1812", "Fuse:Fuse_1812_4532Metric").c({"1": "VSYS", "2": "VSENS"})
C(pw, "1u/50V", "VFIELD", fp=C1206)
C(pw, "1u/50V", "VSENS", fp=C1206)
pw.pwr_flag("VFIELD")
pw.pwr_flag("VSENS")

pw.block("Mains-fail and battery monitoring (ADC1)", "150k/10k: 32 V -> 2.0 V")
for src, sense in (("VIN_MAIN_F", "VIN_MAIN_SENSE"), ("VIN_BAT_F", "VIN_BAT_SENSE")):
    R(pw, "150k 1%", src, sense)
    R(pw, "10k 1%", sense, "GND")
    C(pw, "100n", sense)

pw.block("5 V / 3.5 A buck (TPS54360, 60 V in)", "fsw 400 kHz, UVLO on 8.5 V / off 7.5 V")
u = pw.part("Regulator_Switching:TPS54360DDA", "U", "TPS54360DDA")
u.c(VIN="VSYS", EN="BUCK5_EN", BOOT="BUCK5_BOOT", FB="BUCK5_FB", COMP="BUCK5_COMP", SW="BUCK5_SW",
    GND="GND", GNDPAD="GND")
u.c({"RT/CLK": "BUCK5_RT"})
C(pw, "2.2u/100V", "VSYS", fp=C1210)
C(pw, "2.2u/100V", "VSYS", fp=C1210)
C(pw, "100n/100V", "VSYS", fp=C0805)
R(pw, "294k 1%", "VSYS", "BUCK5_EN")
R(pw, "46.4k 1%", "BUCK5_EN", "GND")
R(pw, "243k 1%", "BUCK5_RT", "GND")
C(pw, "100n", "BUCK5_BOOT", "BUCK5_SW")
pw.part("Device:D_Schottky", "D", "B560C 60V/5A", SMC).c(K="BUCK5_SW", A="GND")
pw.part("Device:L", "L", "10uH 6A SRP1245A-100M", "Inductor_SMD:L_Bourns_SRP1245A").c({"1": "BUCK5_SW", "2": "+5V"})
R(pw, "53.6k 1%", "+5V", "BUCK5_FB")
R(pw, "10.2k 1%", "BUCK5_FB", "GND")
R(pw, "16.9k", "BUCK5_COMP", "BUCK5_CC")
C(pw, "6.8n", "BUCK5_CC")
C(pw, "33p", "BUCK5_COMP")
C(pw, "47u/10V", "+5V", fp=C1210)
C(pw, "47u/10V", "+5V", fp=C1210)
C(pw, "100n", "+5V")
pw.pwr_flag("+5V")

pw.block("3.3 V / 3 A buck (TPS563200)", "Vout = 0.768 x (1 + 33.2k/10k) = 3.32 V")
u = pw.part("Regulator_Switching:TPS563200", "U", "TPS563200")
u.c(VIN="+5V", EN="BUCK3_EN", VBST="BUCK3_BST", SW="BUCK3_SW", VFB="BUCK3_FB", GND="GND")
R(pw, "100k", "+5V", "BUCK3_EN")
C(pw, "10u/10V", "+5V", fp=C0805)
C(pw, "100n", "+5V")
C(pw, "100n", "BUCK3_BST", "BUCK3_SW")
pw.part("Device:L", "L", "2.2uH 4A NR5040", "Inductor_SMD:L_Taiyo-Yuden_NR-50xx").c({"1": "BUCK3_SW", "2": "+3V3"})
R(pw, "33.2k 1%", "+3V3", "BUCK3_FB")
R(pw, "10k 1%", "BUCK3_FB", "GND")
C(pw, "22u/10V", "+3V3", fp=C1206)
C(pw, "22u/10V", "+3V3", fp=C1206)
LED(pw, "green PWR", "PWR_LED_A", "GND")
R(pw, "1k", "+3V3", "PWR_LED_A")
pw.pwr_flag("+3V3")

pw.block("USB bench power", "USB 5 V can power logic for programming (relays need main supply)")
pw.part("Device:D_Schottky", "D", "SS34", SMA).c(A="VBUS_USB", K="+5V")

pw.block("Mounting holes (M3, bonded to GND)")
for _ in range(4):
    pw.part("Mechanical:MountingHole_Pad", "H", "M3", "MountingHole:MountingHole_3.2mm_M3_Pad_Via").c({"1": "GND"})


# ========================================================================
# Sheet: mcu
# ========================================================================
mc = c.sheet("mcu", "MCU, USB, Watchdog, RTC, UI")

mc.block("ESP32-S3-WROOM-1 (N16R2: 16 MB flash, 2 MB quad PSRAM -> IO35..37 free)")
esp = mc.part("RF_Module:ESP32-S3-WROOM-1", "U", "ESP32-S3-WROOM-1-N16R2")
esp.c({"3V3": "+3V3", "GND": "GND", "EN": "ESP_EN",
       "IO0": "BOOT_BTN", "IO1": "VIN_MAIN_SENSE", "IO2": "VIN_BAT_SENSE", "IO3": "OUT3_CTL",
       "IO4": "I2C_SDA", "IO5": "I2C_SCL", "IO6": "EXP_INT", "IO7": "DI1", "IO8": "DI2",
       "IO9": "SPI_SCK", "IO10": "SPI_MOSI", "IO11": "SPI_MISO", "IO12": "ETH_CS", "IO13": "ETH_INT",
       "IO14": "WDT_DONE", "IO15": "LORA_CS", "IO16": "LORA_DIO0", "IO17": "SD_CS", "IO18": "ONEWIRE",
       "IO19": "USB_DN", "IO20": "USB_DP", "IO21": "OUT1_CTL",
       "IO35": "WDT_WAKE", "IO36": "MODEM_RI", "IO37": "BUZZER_CTL",
       "IO38": "RS485A_TX", "IO39": "RS485A_RX", "IO40": "RS485A_DE",
       "IO41": "RS485B_TX", "IO42": "RS485B_RX", "TXD0": "MODEM_TXD", "RXD0": "MODEM_RXD",
       "IO45": "OUT4_CTL", "IO46": "LED_STATUS", "IO47": "RS485B_DE", "IO48": "OUT2_CTL"})
decouple(mc, "+3V3", "22u/10V", "10u/10V", "100n")
R(mc, "10k", "+3V3", "ESP_EN")
C(mc, "1u", "ESP_EN")
mc.part("Switch:SW_Push", "SW", "RESET", BTN).c({"1": "ESP_EN", "2": "GND"})
R(mc, "10k", "+3V3", "BOOT_BTN")
mc.part("Switch:SW_Push", "SW", "BOOT / OK", BTN).c({"1": "BOOT_BTN", "2": "GND"})
R(mc, "10k", "+3V3", "I2C_SDA")
R(mc, "10k", "+3V3", "I2C_SCL")

mc.block("USB-C (native USB: flashing + console)")
j = mc.part("Connector:USB_C_Receptacle_USB2.0_16P", "J", "USB-C", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12")
j.c({"VBUS": "VBUS_USB", "GND": "GND", "SHIELD": "GND", "CC1": "USB_CC1", "CC2": "USB_CC2",
     "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN", "SBU1": NC, "SBU2": NC})
R(mc, "5.1k", "USB_CC1", "GND")
R(mc, "5.1k", "USB_CC2", "GND")
mc.part("Power_Protection:USBLC6-2SC6", "U", "USBLC6-2SC6").c(
    {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "VBUS": "VBUS_USB", "GND": "GND"})
C(mc, "1u/16V", "VBUS_USB")

mc.block("External watchdog (TPL5010)", "WAKE every ~60 s, firmware must pulse DONE; open SJ to disable")
u = mc.part("Timer:TPL5010", "U", "TPL5010")
u.c(VDD="+3V3", GND="GND", DONE="WDT_DONE", WAKE="WDT_WAKE", RST="WDT_RST")
u.c({"DELAY/M_RST": "WDT_DELAY"})
R(mc, "57.6k 1%", "WDT_DELAY", "GND")
C(mc, "100n", "+3V3")
mc.part("Jumper:SolderJumper_2_Bridged", "JP", "WDT_EN", SJ_BRIDGED).c(A="WDT_RST", B="ESP_EN")

mc.block("RTC (DS3231M) + secure element (ATECC608B)")
u = mc.part("Timer_RTC:DS3231MZ", "U", "DS3231MZ")
u.c(VCC="+3V3", GND="GND", VBAT="RTC_VBAT", SDA="I2C_SDA", SCL="I2C_SCL")
u.c({"~{INT}/SQW": "RTC_INT", "32KHZ": NC, "~{RST}": NC})
R(mc, "10k", "+3V3", "RTC_INT")
C(mc, "100n", "+3V3")
mc.part("Device:Battery_Cell", "BT", "CR2032", "Battery:BatteryHolder_MPD_BC2003_1x2032").c(
    {"+": "RTC_VBAT", "-": "GND"})
u = mc.part("Security:ATECC608B-SSHDA", "U", "ATECC608B-TNGTLS (I2C 0x35)")
u.c(VCC="+3V3", GND="GND", SDA="I2C_SDA", SCL="I2C_SCL")
C(mc, "100n", "+3V3")

mc.block("I/O expander #2 (PCA9555 @0x21): housekeeping")
u = mc.part("Interface_Expansion:PCA9555D", "U", "PCA9555D")
u.c(VDD="+3V3", VSS="GND", SDA="I2C_SDA", SCL="I2C_SCL", A0="+3V3", A1="GND", A2="GND")
u.c({"~{INT}": "EXP_INT",
     "IO0_0": "ETH_RST", "IO0_1": "LORA_RST", "IO0_2": "MODEM_PWRKEY", "IO0_3": "MODEM_RST",
     "IO0_4": "LED_NET", "IO0_5": "LED_ALARM", "IO0_6": "SD_CD", "IO0_7": "MODEM_STATUS",
     "IO1_0": "BTN_UP", "IO1_1": "BTN_DOWN", "IO1_2": "BTN_BACK", "IO1_3": "RTC_INT",
     "IO1_4": "LORA_DIO1", "IO1_5": "EXP_IO5", "IO1_6": "EXP_IO6", "IO1_7": "EXP_IO7"})
C(mc, "100n", "+3V3")
R(mc, "10k", "+3V3", "EXP_INT")
terminal_hdr = mc.part("Connector_Generic:Conn_01x05", "J", "SPARE IO", "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
terminal_hdr.c({"1": "+3V3", "2": "EXP_IO5", "3": "EXP_IO6", "4": "EXP_IO7", "5": "GND"})

mc.block("Front panel: buttons, LEDs, buzzer, OLED")
for net, label in (("BTN_UP", "UP"), ("BTN_DOWN", "DOWN"), ("BTN_BACK", "BACK")):
    R(mc, "10k", "+3V3", net)
    mc.part("Switch:SW_Push", "SW", label, BTN).c({"1": net, "2": "GND"})
LED(mc, "blue STATUS", "LED_STATUS_A", "GND")
R(mc, "1k", "LED_STATUS", "LED_STATUS_A")
for net, color in (("LED_NET", "green NET"), ("LED_ALARM", "red ALARM")):
    LED(mc, color, net + "_A", net)
    R(mc, "1k", "+3V3", net + "_A")
R(mc, "1k", "BUZZER_CTL", "BUZ_B")
R(mc, "10k", "BUZ_B", "GND")
mc.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="BUZ_B", E="GND", C="BUZ_K")
mc.part("Device:Buzzer", "BZ", "5V magnetic buzzer", "Buzzer_Beeper:Buzzer_12x9.5RM7.6").c(
    {"+": "+5V", "-": "BUZ_K"})
mc.part("Device:D", "D", "1N4148W", "Diode_SMD:D_SOD-123").c(A="BUZ_K", K="+5V")
j = mc.part("Connector_Generic:Conn_01x04", "J", "OLED I2C", "Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical")
j.c({"1": "GND", "2": "+3V3", "3": "I2C_SCL", "4": "I2C_SDA"})


# ========================================================================
# Sheet: comms
# ========================================================================
cm = c.sheet("comms", "Ethernet, LoRa, microSD, Cellular slot")

cm.block("Ethernet (W5500 + HR911105A MagJack)", "check against WIZnet W5500 reference design")
u = cm.part("Interface_Ethernet:W5500", "U", "W5500")
u.c({"VDD": "+3V3", "GND": "GND", "AVDD": "+3V3A", "AGND": "GND",
     "~{SCS}": "ETH_CS", "SCLK": "SPI_SCK", "MISO": "SPI_MISO", "MOSI": "SPI_MOSI",
     "~{INT}": "ETH_INT", "~{RST}": "ETH_RST",
     "XI/CLKIN": "ETH_XI", "XO": "ETH_XO",
     "PMODE0": "+3V3", "PMODE1": "+3V3", "PMODE2": "+3V3", "RSVD": "GND",
     "EXRES1": "ETH_EXRES", "VBG": NC, "TOCAP": "ETH_TOCAP", "1V2O": "ETH_1V2",
     "TXP": "ETH_TXP", "TXN": "ETH_TXN", "RXP": "ETH_RXP", "RXN": "ETH_RXN",
     "LINKLED": "ETH_LINK", "ACTLED": "ETH_ACT", "SPDLED": NC, "DUPLED": NC})
cm.part("Device:FerriteBead_Small", "FB", "600R@100MHz", "Inductor_SMD:L_0603_1608Metric").c(
    {"1": "+3V3", "2": "+3V3A"})
C(cm, "10u/10V", "+3V3A", fp=C0805)
for _ in range(3):
    C(cm, "100n", "+3V3A")
C(cm, "100n", "+3V3")
R(cm, "12.4k 1%", "ETH_EXRES", "GND")
C(cm, "4.7u", "ETH_TOCAP", fp=C0805)
C(cm, "10n", "ETH_1V2")
cm.part("Device:Crystal_GND24", "Y", "25MHz 18pF", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm").c(
    {"1": "ETH_XI", "3": "ETH_XO", "2": "GND", "4": "GND"})
C(cm, "18p", "ETH_XI")
C(cm, "18p", "ETH_XO")
R(cm, "10k", "+3V3", "ETH_RST")
R(cm, "10k", "+3V3", "ETH_INT")
for a in ("ETH_TXP", "ETH_TXN"):
    R(cm, "49.9 1%", a, "+3V3A")
for a in ("ETH_RXP", "ETH_RXN"):
    R(cm, "49.9 1%", a, "ETH_RXBIAS")
C(cm, "6.8n", "ETH_RXBIAS")
j = cm.part("Connector:RJ45_Hanrun_HR911105A_Horizontal", "J", "ETHERNET")
j.c({"TD+": "ETH_TXP", "TD-": "ETH_TXN", "RD+": "ETH_RXP", "RD-": "ETH_RXN",
     "TCT": "+3V3A", "RCT": "ETH_RCT", "8": "GND", "SH": "GND",
     "9": "ETH_LEDG_A", "10": "ETH_LINK", "12": "ETH_LEDY_A", "11": "ETH_ACT"})
C(cm, "10n", "ETH_RCT")
C(cm, "100n", "+3V3A")
R(cm, "330", "+3V3", "ETH_LEDG_A")
R(cm, "330", "+3V3", "ETH_LEDY_A")

cm.block("LoRa 433 MHz (Ai-Thinker Ra-02 / SX1278, IPEX antenna)")
u = cm.part("RF_Module:Ai-Thinker-Ra-02", "U", "Ra-02 SX1278 433MHz", "RF_Module:Ai-Thinker-Ra-01-LoRa")
u.c({"VDD": "+3V3", "GND": "GND", "~{RESET}": "LORA_RST", "~{NSS}": "LORA_CS", "SCK": "SPI_SCK",
     "MOSI": "SPI_MOSI", "MISO": "SPI_MISO", "DIO0": "LORA_DIO0", "DIO1": "LORA_DIO1",
     "DIO2": NC, "DIO3": NC, "DIO4": NC, "DIO5": NC})
C(cm, "10u/10V", "+3V3", fp=C0805)
C(cm, "100n", "+3V3")
R(cm, "10k", "+3V3", "LORA_CS")

cm.block("microSD (SPI mode) - local data logging")
j = cm.part("Connector:Micro_SD_Card_Det_Hirose_DM3AT", "J", "microSD", "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5")
j.c({"DAT3/CD": "SD_CS", "CMD": "SPI_MOSI", "CLK": "SPI_SCK", "DAT0": "SPI_MISO",
     "DAT1": "SD_DAT1", "DAT2": "SD_DAT2", "VDD": "+3V3", "VSS": "GND",
     "DET_A": "SD_CD", "DET_B": "GND", "SHIELD": "GND"})
for n in ("SD_CS", "SPI_MISO", "SD_DAT1", "SD_DAT2", "SD_CD"):
    R(cm, "10k", "+3V3", n)
C(cm, "10u/10V", "+3V3", fp=C0805)
C(cm, "100n", "+3V3")

cm.block("Cellular modem slot (4G Cat-1 / 2G daughter card: A7670E, SIM800C, EC200U...)",
         "3.3 V logic; card makes its own 3.8-4.2 V from +5V")
j = cm.part("Connector_Generic:Conn_02x08_Odd_Even", "J", "MODEM SLOT",
            "Connector_PinSocket_2.54mm:PinSocket_2x08_P2.54mm_Vertical")
j.c({"1": "+5V", "2": "+5V", "3": "GND", "4": "GND", "5": "MODEM_TXD", "6": "MODEM_RXD",
     "7": "MODEM_PWRKEY", "8": "MODEM_RST", "9": "MODEM_STATUS", "10": "MODEM_RI",
     "11": "+3V3", "12": "GND", "13": "I2C_SDA", "14": "I2C_SCL", "15": "GND", "16": "+5V"})
CP(cm, "470u/10V", "+5V", fp="Capacitor_SMD:CP_Elec_8x10.5")
C(cm, "100n", "+5V")
R(cm, "10k", "MODEM_STATUS", "GND")
R(cm, "10k", "+3V3", "MODEM_RI")


# ========================================================================
# Sheet: relays_di
# ========================================================================
rd = c.sheet("relays_di", "Relay outputs and isolated digital inputs")

rd.block("I/O expander #1 (PCA9555 @0x20): relays + digital inputs")
u = rd.part("Interface_Expansion:PCA9555D", "U", "PCA9555D")
u.c(VDD="+3V3", VSS="GND", SDA="I2C_SDA", SCL="I2C_SCL", A0="GND", A1="GND", A2="GND")
u.c({"~{INT}": "EXP_INT"})
u.c({"IO0_%d" % i: "RLY%d_CTL" % (i + 1) for i in range(8)})
u.c({"IO1_%d" % i: "DI%d" % (i + 1) for i in range(8)})
C(rd, "100n", "+3V3")
u = rd.part("Transistor_Array:ULN2803A", "U", "ULN2803A", "Package_SO:SOIC-18W_7.5x11.6mm_P1.27mm")
u.c({"I%d" % i: "RLY%d_CTL" % i for i in range(1, 9)})
u.c({"O%d" % i: "RLY%d_COIL" % i for i in range(1, 9)})
u.c(GND="GND", COM="+5V")
C(rd, "10u/10V", "+5V", fp=C0805)

for i in range(1, 9):
    rd.block("Relay output %d (10 A 250 VAC, dry contact)" % i)
    k = rd.part("Relay:SANYOU_SRD_Form_C", "K", "SRD-05VDC-SL-C")
    k.c({"2": "+5V", "5": "RLY%d_COIL" % i, "1": "RLY%d_COM" % i, "3": "RLY%d_NO" % i, "4": "RLY%d_NC" % i})
    LED(rd, "red K%d" % i, "RLY%d_LED" % i, "RLY%d_COIL" % i)
    R(rd, "2.2k", "+5V", "RLY%d_LED" % i)
    terminal(rd, "RELAY %d" % i, ["RLY%d_NO" % i, "RLY%d_COM" % i, "RLY%d_NC" % i])

for g in range(2):
    rd.block("Digital inputs %d-%d (opto-isolated, 10-32 V AC/DC, sink or source)" % (4 * g + 1, 4 * g + 4))
    com = "DI_COM%d" % (g + 1)
    opto = rd.part("Isolator:TLP290-4", "U", "TLP290-4")
    for ch in range(4):
        n = 4 * g + ch + 1
        led_a, led_k, col, emi = [(1, 2, 16, 15), (3, 4, 14, 13), (5, 6, 12, 11), (7, 8, 10, 9)][ch]
        opto.c({str(led_a): "DI%d_R" % n, str(led_k): com, str(col): "DI%d" % n, str(emi): "GND"})
        R(rd, "4.7k 1206", "DI%d_IN" % n, "DI%d_R" % n, fp=R1206)
        R(rd, "10k", "+3V3", "DI%d" % n)
        C(rd, "1n", "DI%d" % n)
    terminal(rd, "DI %d-%d" % (4 * g + 1, 4 * g + 4), ["DI%d_IN" % (4 * g + k + 1) for k in range(4)] + [com])


# ========================================================================
# Sheet: analog_io
# ========================================================================
an = c.sheet("analog_io", "Analog IO, MOSFET outputs, 1-Wire, ext. I2C")

an.block("16-bit ADC (ADS1115 @0x48)")
u = an.part("Analog_ADC:ADS1115IDGS", "U", "ADS1115IDGS")
u.c(VDD="+3V3", GND="GND", SDA="I2C_SDA", SCL="I2C_SCL", ADDR="GND", AIN0="AI1_ADC", AIN1="AI2_ADC",
    AIN2="AI3_ADC", AIN3="AI4_ADC")
u.c({"ALERT/RDY": NC})
C(an, "100n", "+3V3")

for i in range(1, 5):
    an.block("Analog input %d: 0-10 V or 4-20 mA (jumper)" % i, "V: 10V->2.5V  I: 20mA x 150R = 3V -> 0.75V")
    an.part("Device:Polyfuse", "F", "PTC 50mA/30V", PTC1206).c({"1": "AI%d_T" % i, "2": "AI%d_IN" % i})
    an.part("Device:D_TVS", "D", "SMAJ12CA", SMA).c(A1="AI%d_IN" % i, A2="GND")
    an.part("Jumper:Jumper_2_Open", "JP", "4-20mA", JMP_HDR).c(A="AI%d_IN" % i, B="AI%d_SH" % i)
    R(an, "150 0.1%", "AI%d_SH" % i, "GND", fp=R0805)
    R(an, "30k 0.1%", "AI%d_IN" % i, "AI%d_ADC" % i)
    R(an, "10k 0.1%", "AI%d_ADC" % i, "GND")
    C(an, "100n", "AI%d_ADC" % i)
    an.part("Diode:BAT54S", "D", "BAT54S").c(A="GND", K="+3V3", COM="AI%d_ADC" % i)

an.block("Analog input terminals (VSENS = loop power for 2-wire transmitters)")
terminal(an, "AI 1-2", ["VSENS", "AI1_T", "AI2_T", "GND"])
terminal(an, "AI 3-4", ["VSENS", "AI3_T", "AI4_T", "GND"])

an.block("Analog outputs 0-10 V (MCP4728 + OPA2196, gain 4.9)", "needs VSYS >= 12 V for full 10 V")
u = an.part("Analog_DAC:MCP4728", "U", "MCP4728")
u.c(VDD="+3V3", VSS="GND", SCL="I2C_SCL", SDA="I2C_SDA", VOUTA="AO1_DAC", VOUTB="AO2_DAC",
    VOUTC=NC, VOUTD=NC)
u.c({"~{LDAC}": "GND", "RDY/~{BSY}": NC})
C(an, "100n", "+3V3")
C(an, "10u/10V", "+3V3", fp=C0805)
op = an.part("Amplifier_Operational:OPA2196xD", "U", "OPA2196xD")
op.c({"3": "AO1_DAC", "2": "AO1_FB", "1": "AO1_OUT", "5": "AO2_DAC", "6": "AO2_FB", "7": "AO2_OUT",
      "V+": "VFIELD", "V-": "GND"})
C(an, "100n/50V", "VFIELD")
for i in (1, 2):
    R(an, "39k 1%", "AO%d_OUT" % i, "AO%d_FB" % i)
    R(an, "10k 1%", "AO%d_FB" % i, "GND")
    R(an, "100", "AO%d_OUT" % i, "AO%d_T" % i)
    an.part("Device:D_TVS", "D", "SMAJ12CA", SMA).c(A1="AO%d_T" % i, A2="GND")
terminal(an, "AO 1-2", ["AO1_T", "AO2_T", "GND"])

for i in range(1, 5):
    an.block("MOSFET output %d (low side, PWM, up to 2 A)" % i)
    b = an.part("74xGxx:74AHCT1G125", "U", "74AHCT1G125", SOT23_5)
    b.c({"1": "GND", "2": "OUT%d_CTL" % i, "4": "OUT%d_DRV" % i, "VCC": "+5V", "GND": "GND"})
    C(an, "100n", "+5V")
    R(an, "100k", "OUT%d_CTL" % i, "GND")
    R(an, "22", "OUT%d_DRV" % i, "OUT%d_G" % i)
    R(an, "100k", "OUT%d_G" % i, "GND")
    an.part("Device:Q_NMOS_GDS", "Q", "IRLR2905", "Package_TO_SOT_SMD:TO-252-2").c(
        G="OUT%d_G" % i, D="OUT%d" % i, S="GND")
    an.part("Device:D_Schottky", "D", "SS26 60V/2A", SMA).c(A="OUT%d" % i, K="VFIELD")

an.block("MOSFET output terminals (load between VFIELD and OUTx)")
terminal(an, "OUT 1-2", ["VFIELD", "OUT1", "OUT2"])
terminal(an, "OUT 3-4", ["VFIELD", "OUT3", "OUT4"])

an.block("1-Wire bus (DS18B20 probes)")
R(an, "4.7k", "+3V3", "ONEWIRE")
R(an, "22", "ONEWIRE", "ONEWIRE_T")
an.part("Device:D_TVS", "D", "PESD5V0S1BL", SOD323).c(A1="ONEWIRE_T", A2="GND")
an.part("Device:Polyfuse", "F", "PTC 100mA", "Fuse:Fuse_0805_2012Metric").c({"1": "+3V3", "2": "V_1W"})
terminal(an, "1-WIRE", ["V_1W", "ONEWIRE_T", "GND"])

an.block("External I2C sensor port (SHT4x, SCD41, BH1750 ...; short cables)")
an.part("Device:Polyfuse", "F", "PTC 100mA", "Fuse:Fuse_0805_2012Metric").c({"1": "+3V3", "2": "V_I2C"})
an.part("Power_Protection:USBLC6-2SC6", "U", "USBLC6-2SC6").c(
    {"1": "I2C_SDA", "6": "I2C_SDA", "3": "I2C_SCL", "4": "I2C_SCL", "VBUS": "+3V3", "GND": "GND"})
terminal(an, "I2C EXT", ["V_I2C", "I2C_SDA", "I2C_SCL", "GND"])


# ========================================================================
# Sheet: fieldbus
# ========================================================================
fb = c.sheet("fieldbus", "RS-485 buses")

fb.block("RS-485 A: expansion-module bus (Modbus RTU, powered, non-isolated)")
u = fb.part("Interface_UART:THVD1420D", "U", "THVD1420D")
u.c(RO="RS485A_RX", DI="RS485A_TX", DE="RS485A_DE", VCC="+3V3", GND="GND", A="RS485A_A", B="RS485A_B")
u.c({"~{RE}": "RS485A_DE"})
C(fb, "100n", "+3V3")
R(fb, "10k", "RS485A_DE", "GND")
fb.part("Diode:SM712_SOT23", "D", "SM712").c(A1="RS485A_A", A2="RS485A_B", common="GND")
fb.part("Jumper:Jumper_2_Open", "JP", "TERM A", JMP_HDR).c(A="RS485A_A", B="RS485A_TERM")
R(fb, "120", "RS485A_TERM", "RS485A_B", fp=R0805)
R(fb, "680", "+3V3", "RS485A_A")
R(fb, "680", "RS485A_B", "GND")
terminal(fb, "RS485-A EXP BUS", ["VFIELD", "RS485A_A", "RS485A_B", "GND"])

fb.block("RS-485 B: field sensor bus (Modbus RTU, 2.5 kV isolated, ADM2587E)")
u = fb.part("Interface_UART:ADM2587E", "U", "ADM2587E")
u.c(VCC="+3V3", GND1="GND", RxD="RS485B_RX", DE="RS485B_DE", TxD="RS485B_TX",
    GND2="GND_ISO", Visoout="VISO", Visoin="VISO", Y="RS485B_A", A="RS485B_A", Z="RS485B_B", B="RS485B_B")
u.c({"~{RE}": "RS485B_DE"})
R(fb, "10k", "RS485B_DE", "GND")
C(fb, "10u/10V", "+3V3", fp=C0805)
C(fb, "100n", "+3V3")
C(fb, "100n", "+3V3")
C(fb, "10u/10V", "VISO", "GND_ISO", fp=C0805)
C(fb, "100n", "VISO", "GND_ISO")
C(fb, "100n", "VISO", "GND_ISO")
fb.part("Diode:SM712_SOT23", "D", "SM712").c(A1="RS485B_A", A2="RS485B_B", common="GND_ISO")
fb.part("Jumper:Jumper_2_Open", "JP", "TERM B", JMP_HDR).c(A="RS485B_A", B="RS485B_TERM")
R(fb, "120", "RS485B_TERM", "RS485B_B", fp=R0805)
R(fb, "680", "VISO", "RS485B_A")
R(fb, "680", "RS485B_B", "GND_ISO")
terminal(fb, "RS485-B FIELD", ["RS485B_A", "RS485B_B", "GND_ISO"])
fb.pwr_flag("GND_ISO")
