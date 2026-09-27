"""AgriNode HUB-1 — universal gateway hub, design source.

One single-sided PCB for every hub type; the assembly option decides the variant:

    HUB-W   Wi-Fi hub               CORE only
    HUB-L   LoRa uplink hub          CORE + LORA
    HUB-C   cellular hub (SIM800C)   CORE + CELL
    GW-LAN  LoRa -> LAN gateway      CORE + LORA + ETH
    BUZ (alarm buzzer) is optional on every variant; IO25/32/33 are left free (spare).

Fabrication rules (see docs/02-architecture.md): single copper layer (bottom), 0.6 mm tracks,
0.5 mm clearance, only 1206 / SOT-23 / SOT-223 / SOIC / TO-263 SMD parts, SMD on the copper
side, THT on top. Modules use the narrowed-pad footprints from hardware/lib.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "tools", "kigen"))

import symlib  # noqa: E402

symlib.add_lib_dir(os.path.join(HERE, "..", "..", "..", "lib"))

from circuit import NC, Circuit  # noqa: E402

# ---------------------------------------------------------------- footprints
R1206 = "Resistor_SMD:R_1206_3216Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
L1206 = "Inductor_SMD:L_1206_3216Metric"
LED1206 = "LED_SMD:LED_1206_3216Metric"
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


c = Circuit("agrinode_hub", "AgriNode HUB-1 Gateway", rev="A", company="AgriNode", date="2026-09-27")


def R(s, value, a, b):
    return s.part("Device:R", "R", value, R1206).c({"1": a, "2": b})


def C(s, value, a, b="GND", fp=C1206):
    return s.part("Device:C", "C", value, fp).c({"1": a, "2": b})


def CP(s, value, a, b="GND", fp=CP8):
    return s.part("Device:C_Polarized", "C", value, fp).c({"1": a, "2": b})


def JMP(s, value, a, b):
    """0R 1206 link used as an assembly option / jumper."""
    return s.part("Device:R", "JP", value, R1206).c({"1": a, "2": b})


def terminal(s, name, nets):
    n = len(nets)
    j = s.part("Connector:Screw_Terminal_01x%02d" % n, "J", name, term(n))
    j.c({str(i + 1): net for i, net in enumerate(nets)})
    return j


# ========================================================================
# Sheet: power
# ========================================================================
pw = c.sheet("power", "Power - 12V, solar and USB inputs, 18650 charger, rails")

pw.block("Inputs: 12 V adapter (jack + terminal), solar 6-24 V, USB 5 V",
         "each input fused and reverse-polarity protected; any combination may be connected")
pw.part("Connector:Barrel_Jack_Switch", "J", "DC 12V 5.5/2.1", "Connector_BarrelJack:BarrelJack_Horizontal").c(
    {"1": "VDC_RAW", "2": "GND", "3": "GND"})
terminal(pw, "DC IN 7-24V", ["VDC_RAW", "GND"])
terminal(pw, "SOLAR 6-24V", ["VSOL_RAW", "GND"])
pw.part("Connector:USB_B", "J", "USB 5V", "agrinode:USB_B_THT_Coarse").c(
    {"VBUS": "VUSB_RAW", "GND": "GND", "Shield": "GND", "D+": NC, "D-": NC})
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


# ========================================================================
# Sheet: mcu
# ========================================================================
mc = c.sheet("mcu", "ESP32, buttons, status LEDs, buzzer, I2C")

mc.block("ESP32-WROOM-32E (8/16 MB)")
esp = mc.part("RF_Module:ESP32-WROOM-32E", "U", "ESP32-WROOM-32E-N8", "agrinode:ESP32-WROOM-32E_Coarse")
esp.c({"VDD": "+3V3", "GND": "GND", "EN": "ESP_EN",
       "IO0": "BOOT_BTN", "TXD0/IO1": "PROG_TX", "RXD0/IO3": "PROG_RX", "IO2": "BUZZER_CTL",
       "IO4": "ETH_CS", "IO5": "LORA_CS", "IO12": "CHRG_N", "IO13": "MODEM_PWRKEY_CTL",
       "IO14": "LORA_RST", "IO15": "MODEM_EN", "IO16": "MODEM_RXD", "IO17": "MODEM_TXD",
       "IO18": "SPI_SCK", "IO19": "SPI_MISO", "IO23": "SPI_MOSI", "IO21": "I2C_SDA", "IO22": "I2C_SCL",
       "IO25": NC, "IO26": "LORA_DIO0", "IO27": "LED_DATA", "IO32": NC, "IO33": NC,
       "IO34": "VBAT_ADC", "IO35": "VIN_ADC", "SENSOR_VP": "ETH_INT", "SENSOR_VN": "MODEM_STATUS"})
C(mc, "22u", "+3V3")
C(mc, "100n", "+3V3")
C(mc, "100n", "+3V3")

mc.block("Reset, boot/pair buttons and programming header",
         "PROG: 1 GND  2 TXD0  3 RXD0  4 3V3  5 EN  6 IO0 (USB-UART adapter)")
R(mc, "10k", "+3V3", "ESP_EN")
C(mc, "1u", "ESP_EN")
mc.part("Switch:SW_Push", "SW", "RESET", BTN).c({"1": "ESP_EN", "2": "GND"})
R(mc, "10k", "+3V3", "BOOT_BTN")
mc.part("Switch:SW_Push", "SW", "BOOT / PAIR", BTN).c({"1": "BOOT_BTN", "2": "GND"})
mc.part("Connector_Generic:Conn_01x06", "J", "PROG", header(6)).c(
    {"1": "GND", "2": "PROG_TX", "3": "PROG_RX", "4": "+3V3", "5": "ESP_EN", "6": "BOOT_BTN"})

mc.block("Addressable RGB status LEDs (6x PL9823 5 mm THT)",
         "1 power/battery  2 Wi-Fi/nodes  3 LoRa  4 cellular  5 LAN/RS-485  6 system/alarm")
R(mc, "4.7k", "+3V3", "LED_DATA")
mc.part("Transistor_FET:BSS138", "Q", "BSS138").c(G="+3V3", S="LED_DATA", D="LED_DIN")
R(mc, "2.2k", "VSYS", "LED_DIN")
chain = ["LED_DIN"] + ["LED_D%d" % i for i in range(1, 6)] + [NC]
for i in range(6):
    mc.part("agrinode:PL9823", "D", "PL9823-F5 #%d" % (i + 1)).c(
        {"DIN": chain[i], "DOUT": chain[i + 1], "VDD": "VSYS", "GND": "GND"})
    C(mc, "100n", "VSYS")
C(mc, "22u", "VSYS")

mc.block("Buzzer (alarm)", option="BUZ")
R(mc, "1k", "BUZZER_CTL", "BUZ_B")
R(mc, "10k", "BUZ_B", "GND")
mc.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="BUZ_B", E="GND", C="BUZ_K")
mc.part("Device:Buzzer", "BZ", "5V magnetic buzzer", "Buzzer_Beeper:Buzzer_12x9.5RM7.6").c({"+": "VSYS", "-": "BUZ_K"})
mc.part("Device:D", "D", "1N4148W", SOD123).c(A="BUZ_K", K="VSYS")

mc.block("I2C expansion header (optional OLED / RTC / sensor modules)")
R(mc, "4.7k", "+3V3", "I2C_SDA")
R(mc, "4.7k", "+3V3", "I2C_SCL")
mc.part("Connector_Generic:Conn_01x04", "J", "I2C", header(4)).c(
    {"1": "GND", "2": "+3V3", "3": "I2C_SCL", "4": "I2C_SDA"})


# ========================================================================
# Sheet: comms
# ========================================================================
cm = c.sheet("comms", "LoRa, Ethernet, cellular (all optional)")

cm.block("LoRa 433 MHz (Ai-Thinker Ra-02, IPEX antenna)", option="LORA")
u = cm.part("RF_Module:Ai-Thinker-Ra-02", "U", "Ra-02 SX1278 433MHz", "agrinode:Ai-Thinker-Ra-02_Coarse")
u.c({"VDD": "+3V3", "GND": "GND", "~{RESET}": "LORA_RST", "~{NSS}": "LORA_CS", "SCK": "SPI_SCK",
     "MOSI": "SPI_MOSI", "MISO": "SPI_MISO", "DIO0": "LORA_DIO0",
     "DIO1": NC, "DIO2": NC, "DIO3": NC, "DIO4": NC, "DIO5": NC})
C(cm, "10u", "+3V3")
C(cm, "100n", "+3V3")
R(cm, "10k", "+3V3", "LORA_CS")

cm.block("Ethernet 10BASE-T (ENC28J60 + HR911105A MagJack)", option="ETH")
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

cm.block("Cellular 2G (SIM800C): GPRS, SMS, voice alarm calls", option="CELL")
u = cm.part("Regulator_Linear:MIC29302WU", "U", "MIC29302WU")
u.c(VIN="VSYS", EN="MODEM_EN", GND="GND", VOUT="VMODEM", ADJ="LDO4_ADJ")
R(cm, "100k", "MODEM_EN", "GND")
R(cm, "22k 1%", "VMODEM", "LDO4_ADJ")
R(cm, "10k 1%", "LDO4_ADJ", "GND")
CP(cm, "1000u/6.3V low ESR", "VMODEM", fp=CP10)
C(cm, "100n", "VMODEM")
C(cm, "33p", "VMODEM")
m = cm.part("RF_GSM:SIM800C", "U", "SIM800C", "agrinode:SIMCom_SIM800C_Coarse")
m.c({"VBAT": "VMODEM", "GND": "GND",
     "UART1_TXD": "SIM_TXD", "UART1_RXD": "SIM_RXD", "~{PWRKEY}": "SIM_PWRKEY", "STATUS": "SIM_STATUS",
     "SIM_VDD": "SIMC_VCC", "SIM_DATA": "SIMC_IO_M", "SIM_CLK": "SIMC_CLK_M", "SIM_RST": "SIMC_RST_M",
     "GSM_ANT": "GSM_ANT",
     "UART1_RTS": NC, "UART1_CTS": NC, "UART1_DCD": NC, "UART1_DTR": NC, "UART1_RI": NC,
     "MICP": NC, "MICN": NC, "SPKP": NC, "SPKN": NC, "SIM_DET": NC, "BT_ANT": NC,
     "UART2_TXD": NC, "UART2_RXD": NC, "USB_VBUS": NC, "USB_DP": NC, "USB_DM": NC,
     "VRTC": NC, "RF_SYNC": NC, "ADC": NC, "VDD_EXT": NC, "NETLIGHT": NC})
R(cm, "1k", "SIM_TXD", "MODEM_RXD")
R(cm, "1k", "MODEM_TXD", "SIM_RXD")
R(cm, "4.7k", "SIM_RXD", "GND")
R(cm, "1k", "SIM_STATUS", "MODEM_STATUS")
R(cm, "4.7k", "MODEM_PWRKEY_CTL", "PWRKEY_B")
R(cm, "47k", "PWRKEY_B", "GND")
cm.part("Device:Q_NPN_BEC", "Q", "MMBT3904", SOT23).c(B="PWRKEY_B", E="GND", C="SIM_PWRKEY")
s = cm.part("Connector:SIM_Card", "J", "micro SIM", "Connector_Card:microSIM_JAE_SF53S006VCBR2000")
s.c({"VCC": "SIMC_VCC", "RST": "SIMC_RST", "CLK": "SIMC_CLK", "I/O": "SIMC_IO", "GND": "GND", "VPP": NC})
R(cm, "22", "SIMC_RST_M", "SIMC_RST")
R(cm, "22", "SIMC_CLK_M", "SIMC_CLK")
R(cm, "22", "SIMC_IO_M", "SIMC_IO")
C(cm, "100n", "SIMC_VCC")
for n in ("SIMC_RST", "SIMC_CLK", "SIMC_IO"):
    C(cm, "22p", n)
R(cm, "0R RF", "GSM_ANT", "GSM_ANT_C")
cm.part("Connector:Conn_Coaxial", "J", "GSM ANT SMA", "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount").c(
    {"In": "GSM_ANT_C", "Ext": "GND"})
