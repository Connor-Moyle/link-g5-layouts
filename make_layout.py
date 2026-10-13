"""Generate the Full Tuning Layout for PCLink (.llf5).

    python make_layout.py TUNE.pclx OUT.llf5 [--force]

TUNE is any tune from the ECU you are laying out for; it is only used to check the layout.

Sized for a 1920x1080 screen with the ECU Settings panel pinned open, which leaves a
1700 x 964 page (measured from the real PCLink window). Every menu and runtime value is
checked against the tune, and panels are checked for overlap, before anything is written.
"""
import copy, os, sys, uuid
import xml.etree.ElementTree as ET

# pclink.py comes from https://github.com/Connor-Moyle/open-source-link-g5 - point PCLINK_TOOLS at a checkout of it
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.environ.get('PCLINK_TOOLS', ''), os.path.join(HERE, '..', 'open-source-link-g5'),
                os.path.join(HERE, '..', 'Link ECU Tunning software remade')]
import pclink

W, H = 1696, 960
LAYOUTS = os.path.join(pclink.PCLINK_DIR, 'Layouts')
BIG, TUNING = '1920 x1080.llf5', 'New Tuning Layout 1920x1080.llf5'
t = pclink.Tune(sys.argv[1])
lang = pclink.load_strings()

# ---- menu name -> string id: ids Link's own layouts use first, then the ECU definition file
shipped = {}
for f in (BIG, TUNING, 'DefaultLayout.llf5', 'Default 1366 x 768.llf5', 'New Tuning Layout 1366x768.llf5'):
    for v in ET.parse(os.path.join(LAYOUTS, f)).getroot().iter('View'):
        if v.get('BaseCaption'):
            shipped.setdefault(lang.get(v.get('BaseCaption')), v.get('BaseCaption'))
with open(os.path.join(pclink.PCLINK_DIR, 'ECU.cfgr'), 'rb') as f:
    cfg = ET.fromstring(pclink.decode(f.read())[0])
raw = {p.get('DataId'): {x.get('Name'): x.get('Value') for x in p.iter('Property')} for p in cfg.find('Parameters')}


def prop(i, name, seen=()):
    p = raw[i]
    if name in p:
        return p[name]
    b = p.get('CopyFromID')
    return prop(b, name, seen + (i,)) if b in raw and b not in seen else None


from_cfg = {}  # name -> set of string ids (more than one = ambiguous menu name)
for i in t.map:
    for alt in (prop(i, 'Parent') or '').split('\\&'):
        for s in alt.split('\\_'):
            from_cfg.setdefault(lang.get(s), set()).add(s)
    if t.map[i].get('Type') == '1':
        from_cfg.setdefault(t.defs[i]['caption'], set()).add(prop(i, 'Caption'))

problems, notes = [], []


def sid(names):
    for name in [names] if isinstance(names, str) else names:
        if name in shipped and name in from_cfg:
            return shipped[name]
        if name in from_cfg:
            if len(from_cfg[name]) > 1:
                notes.append(f'menu "{name}" has {len(from_cfg[name])} ids - check that panel in PCLink')
            return sorted(from_cfg[name], key=int)[0]
    # Tables PCLink allocates at runtime (anti-lag, idle, limit, wastegate tables) are not in the definition
    # file under their menu name; their string id is still what a layout refers to.
    for name in [names] if isinstance(names, str) else names:
        ids = [k for k, v in lang.items() if v == name]
        if name in shipped or len(ids) == 1:
            notes.append(f'menu "{name}" could not be confirmed against the tune - check that panel in PCLink')
            return shipped.get(name) or ids[0]
    problems.append(f'menu {names!r} does not exist in this tune')
    return '0'


def guid():
    return '{' + str(uuid.uuid4()).upper() + '}'


def base(kind, x, y, w, h, **attrs):
    return ET.Element('View', dict(Type=kind, Left=str(x), Top=str(y), Width=str(w), Height=str(h), Locked='true',
                                   FontSize='0', Guid=guid(), **attrs))


def settings(name, x, y, w, h, locked=True, gradient=False, graph=False):
    return base('Auto Settings', x, y, w, h, BaseCaption=sid(name), MenuLocked=str(locked).lower(), SnakeTrail='true',
                GhostBox='false', ColourGradient=str(gradient).lower(), GraphDisplay=str(graph).lower(), KeyRotation='false',
                HingedAxis=str(graph).lower(), TableLockedToFocused=str(graph).lower())


def table(name, x, y, w, h):
    return settings(name, x, y, w, h, gradient=True)


def values(caption, ids, x, y, w, h, cols=1, check=True):
    ids = [str(i) for i in ids]
    if check:
        problems.extend(f'{caption}: DataId {i} not in tune' for i in ids if i not in t.map)
        need = 22 + 17 * -(-len(ids) // cols)  # PCLink: 22px title + 17px per row
        if need > h:
            notes.append(f'list "{caption}" shows {(h - 22) // 17 * cols} of {len(ids)} rows without scrolling')
    v = base('Runtime Value List', x, y, w, h, ColumnsCount=str(cols), Caption=caption, CaptionStrId='0', SortMode='0', BoldFont='true')
    ET.SubElement(ET.SubElement(v, 'DataIDGroups'), 'RuntimeViewDataIDGroup', GroupID='0', DataIDs=','.join(ids))
    return v


def digital(ids, x, y, w, h):
    v = base('Digital Gauge', x, y, w, h)
    problems.extend(f'gauge: DataId {i} not in tune' for i in ids if str(i) not in t.map)
    ET.SubElement(ET.SubElement(v, 'DataIDGroups'), 'RuntimeViewDataIDGroup', GroupID='0', DataIDs=','.join(str(i) for i in ids))
    return v


def borrow(layout, page, kind, x, y, w, h, nth=0, caption=None):
    """Copy a complex view (plot, dial, mixture map) from one of Link's layouts so its inner setup is what PCLink wrote."""
    root = ET.parse(os.path.join(LAYOUTS, layout)).getroot()
    pg = [p for p in root.iter('Page') if p.get('Name') == page][0]
    vs = [v for v in pg.iter('View') if v.get('Type') == kind and (caption is None or v.get('ViewCaption') == caption)]
    v = copy.deepcopy(vs[nth])
    v.attrib.update(Left=str(x), Top=str(y), Width=str(w), Height=str(h), Guid=guid())
    return v


def plot(page, x, y, w, h):
    return borrow(TUNING, page, 'Time Plot', x, y, w, h)


def dial(caption, x, y, w, h):
    return borrow(BIG, 'Configuration', 'Dial Gauge', x, y, w, h, caption=caption)


def rid(caption):
    """DataId of the runtime value with this exact caption."""
    m = [i for i, e in t.map.items() if e.get('ReadOnly') == 'true' and t.defs[i]['caption'] == caption]
    if not m:
        problems.append(f'runtime "{caption}" not found')
        return '0'
    return m[0]


RPM, MAP, MGP, TPS, ECT, IAT, LAM, IGN, BATT, DUTY, ETH = 1000, 1001, 1091, 1078, 1004, 1011, 3040, 1064, 1081, 1007, 2397
TARGET = rid('AFR/Lambda Target')


def link_list(caption):
    """DataIds of one of the stock lists on Link's own Configuration page (ids the ECU lacks are shown as gaps)."""
    pg = [p for p in ET.parse(os.path.join(LAYOUTS, BIG)).getroot().iter('Page') if p.get('Name') == 'Configuration'][0]
    v = [v for v in pg.iter('View') if v.get('Caption') == caption][0]
    return v.find('.//RuntimeViewDataIDGroup').get('DataIDs').split(',')


r = lambda a, b: list(range(a, b + 1))
pages = {}

# ---------------------------------------------------------------- Basics: engine setup + health at a glance
pages['Basics'] = (-1, [
    settings('Configuration', 2, 2, 338, 258, locked=False),
    settings('Ignition Main', 2, 262, 338, 178),
    settings('Trigger Setup', 2, 442, 338, 90),
    settings('Fuel Main', 342, 2, 338, 530),
    settings('RPM Limit', 682, 2, 338, 380),
    digital([ECT, IAT], 682, 384, 338, 148),
    values('Engine', [RPM, MAP, MGP, TPS, ECT, IAT, LAM, TARGET, IGN, DUTY, rid('Injection Actual PW'), rid('Dwell Time'),
                      BATT, rid('Fuel Pressure'), rid('Oil Pressure'), rid('Oil Temperature'), ETH, rid('Gear'),
                      rid('ECU Temperature')], 1022, 2, 298, 348),
    digital([LAM, TARGET], 1022, 352, 298, 180),
    values('Status', [rid('Fault Codes'), rid('Fault Code Count'), rid('Trigger 1 State'), rid('Trig1 Err Counter'),
                      rid('RPM Limit'), rid('MAP Limit'), rid('Anti-Lag Status'), rid('Boost Status'), rid('Idle Status'),
                      rid('CL Lambda Status 1'), rid('Lambda 1 Status'), rid('Ethanol Sensor Status'),
                      rid('Overrun Fuel Cut Status')], 1322, 2, 372, 248),
    values('Limits and Trims', [rid('WGate DC'), rid('Boost Target'), rid('Idle Target'), rid('Idle Position'),
                                rid('Warm Up Enrichment'), rid('Accel Fuel'), rid('IAT Fuel Corr.'), rid('ECT Ignition Trim'),
                                rid('IAT Ignition Trim'), rid('Anti-Lag Ignition Trim'), rid('Launch Ignition Trim'),
                                rid('Max Eng Speed'), rid('Max MAP'), rid('Max IAT')], 1322, 252, 372, 280),
    dial('RPM', 2, 536, 298, 298), dial('Lambda/AFR', 302, 536, 298, 298), dial('Boost/Vac', 602, 536, 298, 298),
    digital([BATT, TPS], 2, 836, 448, 122),
    digital([IGN, DUTY], 452, 836, 448, 122),
    plot('Trigger Setup', 902, 536, 792, 422),
])

# ---------------------------------------------------------------- Config: inputs, outputs, sensors
pages['Config'] = (-1, [
    values('Outputs', link_list('Auxiliary'), 2, 2, 498, 348, cols=2, check=False),
    values('Analog Inputs', link_list('Analog'), 2, 352, 498, 230, cols=2, check=False),
    settings('MAP', 502, 2, 396, 130), settings('ECT', 502, 134, 396, 130), settings('IAT', 502, 266, 396, 130),
    settings('Throttle Position Sensor', 502, 398, 396, 184),
    settings('Lambda 1', 900, 2, 396, 130), settings('Ethanol Sensor', 900, 134, 396, 130),
    settings('Fuel Pressure', 900, 266, 396, 130), settings('Oil Pressure', 900, 398, 396, 184),
    settings('Injector Setup', 1298, 2, 396, 172),
    settings('Fuel Pump Control', 1298, 176, 396, 406),
    table('Injector Dead Time Table', 2, 586, 596, 150),
    table('Firing Order Table', 2, 738, 596, 100),
    table('Injector Short Pulse Width Adder Table', 2, 840, 596, 118),
    settings('Tacho', 600, 586, 366, 190),
    values('Digital Inputs', link_list('Digital'), 600, 778, 366, 180, cols=2, check=False),
    settings('Injector Test', 968, 586, 362, 110),
    settings('Ignition Test', 968, 698, 362, 80),
    values('ECU', [BATT, rid('ECU Temperature'), rid('Fault Codes'), rid('Fault Code Count'), rid('Trig1 Signal'),
                   rid('Trig2 Signal'), rid('Trig1 Arming'), rid('Trig2 Arming'), rid('CPU Idle Percent')], 968, 780, 362, 178),
    settings('Engine Fan', 1332, 586, 362, 372),
])

# ---------------------------------------------------------------- Ignition Tune
pages['Ignition Tune'] = (2366, [
    table('Ignition Table 1', 2, 2, 1078, 520),
    settings('Ignition Table 1', 1082, 2, 406, 520, graph=True),
    digital([RPM, MGP, IGN, LAM, ECT, IAT], 1490, 2, 204, 520),
    table(['ECT Ignition Trim Table', 'ECT Ignition Trim 3D Table'], 2, 524, 430, 216),
    table(['IAT Ignition Trim Table', 'IAT Ignition Trim 3D Table'], 2, 742, 430, 216),
    values('Ignition', [IGN, rid('Ignition Table1'), rid('ECT Ignition Trim'), rid('IAT Ignition Trim'),
                        rid('Anti-Lag Ignition Trim'), rid('Launch Ignition Trim'), rid('Limit Ignition Trim'),
                        rid('Transient Ignition Trim'), rid('Overrun Ignition Trim'), rid('Idle Ignition Angle'),
                        rid('Max Ignition'), rid('Dwell Time'), rid('Knock Level Detected'), RPM, MAP, MGP, TPS],
           434, 524, 248, 434),
    plot('Ignition', 684, 524, 1010, 434),
])

# ---------------------------------------------------------------- Fuel Tune
pages['Fuel Tune'] = (2365, [
    table('Fuel Table 1', 2, 2, 1078, 520),
    settings('Fuel Table 1', 1082, 2, 406, 300, graph=True),
    table('Injector Dead Time Table', 1082, 304, 406, 218),
    digital([LAM, TARGET, RPM, MGP, DUTY, ETH], 1490, 2, 204, 520),
    settings('Accel Enrichment', 2, 524, 340, 216),
    settings('Overrun Fuel Cut', 2, 742, 340, 216),
    table('Warm Up Enrichment Table', 344, 524, 400, 216),
    table('IAT Fuel Trim Table', 344, 742, 400, 216),
    values('Fuel', [LAM, TARGET, rid('CL Lambda Status 1'), rid('Injection Effective PW'), rid('Injection Actual PW'), DUTY,
                    rid('Injection Timing'), rid('Warm Up Enrichment'), rid('Post Start Enrich'), rid('Crank Enrich'),
                    rid('Accel Fuel'), rid('IAT Fuel Corr.'), rid('Charge Temperature'), rid('Fuel Pressure'), ETH,
                    rid('Overrun Fuel Cut Status'), RPM, MAP, MGP, TPS], 746, 524, 248, 434),
    plot('Main Fuel Tuning', 996, 524, 698, 434),
])

# ---------------------------------------------------------------- Timing: triggers, base timing, dwell
pages['Timing'] = (-1, [
    settings('Trigger Setup', 2, 2, 398, 100), settings('Trigger 1', 2, 104, 398, 220), settings('Trigger 2', 2, 326, 398, 180),
    settings('Calibrate', 402, 2, 398, 100), settings('Ignition Main', 402, 104, 398, 180),
    table('Firing Order Table', 402, 286, 398, 100),
    digital([RPM, IGN], 402, 388, 398, 118),
    table('Dwell Control Table', 802, 2, 596, 280),
    table('Trigger 1 Arming Threshold Table', 802, 284, 596, 110),
    table('Trigger 2 Arming Threshold Table', 802, 396, 596, 110),
    values('Triggers', [RPM, rid('Trigger 1 State'), rid('Trig1 Err Counter'), rid('Trig1 Signal'), rid('Trig2 Signal'),
                        rid('Trig1 Arming'), rid('Trig2 Arming'), rid('Rotation Direction'), rid('Engine Speed ROC'),
                        rid('Engine Cycle Count'), rid('Engine Running Time'), IGN, rid('Ignition Table1'),
                        rid('Dwell Time'), BATT, rid('Injection Timing')], 1400, 2, 294, 504),
    plot('Trigger Setup', 2, 510, 1692, 448),
])

# ---------------------------------------------------------------- CAN Bus
pdm = [i for i, e in t.map.items() if t.defs[i]['path'] == 'CAN > PDM 1' and e.get('ReadOnly') == 'true']
buttons = [settings(f'Simple Button {n}', x, y, w, h) for n, (x, y, w, h) in enumerate(
    [(1102, 2, 296, 108), (1400, 2, 294, 108), (1102, 112, 296, 108), (1400, 112, 294, 108), (1102, 222, 296, 108),
     (1400, 222, 294, 108)] + [(402 + 216 * k, 660, 214 if k < 5 else 212, 148) for k in range(6)], start=1)]
pages['CAN Bus'] = (-1, [
    settings('CAN', 2, 2, 398, 300, locked=False),
    settings('CAN Keypad 1', 2, 304, 398, 654),
    values('CAN Digital Inputs', r(1488, 1495) + r(839, 846), 402, 2, 238, 296),
    values('CAN Frequency Inputs', r(350, 357), 402, 300, 238, 160),
    values('CAN Thermocouples', r(1429, 1436), 402, 462, 238, 194),
    values('CAN Analog Inputs', r(1421, 1428) + r(1979, 1986), 642, 2, 238, 296),
    values('CAN Lambda', [LAM, rid('Lambda 1 Temperature.'), rid('Lambda 1 Status'), rid('Lambda 1 Error'), TARGET,
                          rid('CL Lambda Status 1')], 642, 300, 238, 126),
    values('CAN 1 Bus Status', r(3771, 3782), 642, 428, 238, 228),
    values('CAN Aux Outputs', r(200, 215), 882, 2, 218, 296),
    values('Keypad / Switch Functions', [rid('Anti-Lag Status'), rid('Boost Status'), rid('Active Boost Table'),
                                         rid('Fuel Table 1'), rid('Ignition Table1'), rid('Speed Limit Switch'),
                                         rid('Gear')], 882, 300, 218, 144),
    values('PDM 1', pdm, 882, 446, 218, 210),
    values('CAN Aux Frequency / Duty', r(216, 231) + r(232, 247), 1102, 332, 592, 324, cols=2),
    *buttons,
    settings('Up/Down Button 1', 402, 810, 320, 148),
    table('Up/Down Button 1 LED States', 724, 810, 320, 148),
    settings('Up/Down Button 2', 1046, 810, 320, 148),
    values('ECU', [BATT, rid('ECU Temperature'), rid('Fault Codes'), rid('Fault Code Count'), RPM], 1368, 810, 326, 148),
])

# ---------------------------------------------------------------- Boost (open loop wastegate control)
pages['Boost'] = (-1, [
    settings('Boost Setup', 2, 2, 398, 420),
    settings('MAP Limit', 2, 424, 398, 534),
    table('Wastegate %DC 1', 402, 2, 560, 262),
    table('Boost IAT Wastegate Trim Table', 402, 266, 560, 86),
    table('Boost ECT Wastegate Trim Table', 402, 354, 560, 86),
    table('Boost Gear Wastegate Trim Table', 402, 442, 560, 86),
    values('Boost', [MGP, MAP, rid('WGate DC'), rid('Boost Base DC'), rid('Boost Target'), rid('Boost Target Error'),
                     rid('Boost Status'), rid('Active Boost Table'), rid('ECT WGate Trim'), rid('IAT WGate Trim'),
                     rid('Gear WGate Trim'), rid('GP WGate Trim'), rid('MAP Limit'), rid('Max MAP'), RPM, TPS, IAT, ECT],
           964, 2, 248, 526),
    dial('Boost/Vac', 1214, 2, 480, 300),
    digital([MGP, rid('WGate DC')], 1214, 304, 480, 224),
    plot('Open Loop Boost control', 402, 532, 1292, 426),
])

# ---------------------------------------------------------------- Idle
pages['Idle'] = (-1, [
    settings('Idle Speed Control Setup', 2, 2, 398, 300),
    settings('Idle Actuator', 2, 304, 398, 654),
    settings('Idle Ignition Control', 402, 2, 398, 160),
    table('Idle Ignition Table', 402, 164, 398, 200),
    table('Startup Offset Table', 402, 366, 398, 140),
    table('AC Offset Table', 402, 508, 398, 142),
    values('Idle', [RPM, rid('Idle Target'), rid('Idle Target Error'), rid('Idle Position'), rid('Idle Base Position'),
                    rid('Idle Status'), rid('Idle Ignition Angle'), rid('Ignition Idle Status'), IGN, TPS, MAP, ECT, BATT,
                    LAM, rid('Cyclic Idle Limit')], 802, 2, 248, 300),
    digital([RPM, rid('Idle Target')], 802, 304, 248, 346),
    plot('Idle Control ', 1052, 2, 642, 648),
    table('Idle Target RPM Table', 402, 652, 646, 150),
    table('Idle Base Position Table', 402, 804, 646, 154),
    settings('Idle Load Trims', 1050, 652, 644, 306),
])

# ---------------------------------------------------------------- Cold Start
pages['Cold Start'] = (-1, [
    table('Crank Enrichment Table', 2, 2, 846, 180),
    table('Post Start Enrichment Table', 2, 184, 846, 150),
    table('Warm Up Enrichment Table', 2, 336, 846, 150),
    table('Crank Hold Time Table', 850, 2, 560, 120),
    table('Post Start Hold Time Table', 850, 124, 560, 120),
    table('Post Start Decay Time Table', 850, 246, 560, 120),
    settings('Pre-Crank Prime', 850, 368, 560, 118),
    values('Cold Start', [RPM, ECT, IAT, rid('Crank Enrich'), rid('Post Start Enrich'), rid('Warm Up Enrichment'),
                          rid('IAT Fuel Corr.'), rid('Injection Actual PW'), LAM, TARGET, rid('Idle Position'),
                          rid('Idle Target'), BATT, IGN], 1412, 2, 282, 484),
    plot('Cranking Fuel', 2, 490, 1408, 468),
    digital([ECT, LAM], 1412, 490, 282, 468),
])

# ---------------------------------------------------------------- MotorSport: anti-lag and launch
pages['MotorSport'] = (-1, [
    settings('Anti-Lag', 2, 2, 420, 480),
    settings('Launch Control', 2, 484, 420, 474),
    table('Anti-Lag Ignition Trim Table', 424, 2, 560, 236),
    table('Anti-Lag Fuel Trim Table', 424, 240, 560, 236),
    table('Anti-Lag Ignition Cut Table', 424, 478, 560, 238),
    table('Anti-Lag Fuel Cut Table', 424, 718, 560, 240),
    settings('Launch Limiting', 986, 2, 360, 260),
    settings('Launch Ignition', 986, 264, 360, 160),
    values('Anti-Lag / Launch', [rid('Anti-Lag Status'), rid('AL Cyclic Limit'), rid('Anti-lag Cut'),
                                 rid('Anti-Lag Ignition Trim'), rid('Anti-lag Fuel Trim'), rid('AL Active Ignition Table'),
                                 rid('AL Active Fuel Table'), rid('AL Active Ignition Cut Table'),
                                 rid('AL Active Fuel Cut Table'), rid('Launch Ignition Trim'), rid('Cyclic Idle Limit'),
                                 RPM, MGP, TPS, IGN, LAM, rid('Gear'), ECT], 986, 426, 360, 532),
    digital([RPM, MGP], 1348, 2, 346, 300),
    dial('Boost/Vac', 1348, 304, 346, 346),
    digital([IGN, TPS], 1348, 652, 346, 306),
])

# ---------------------------------------------------------------- Limits: engine protection
pages['Limits'] = (-1, [
    settings('RPM Limit', 2, 2, 338, 400), settings('MAP Limit', 342, 2, 338, 400), settings('Speed Limit', 682, 2, 338, 400),
    settings('GP RPM Limit 1', 1022, 2, 336, 400), settings('GP RPM Limit 2', 1360, 2, 334, 400),
    table('RPM Limit Table 1', 2, 404, 560, 180),
    table('MAP Limit Table 1', 2, 586, 560, 180),
    settings('Sys Voltage Limit', 2, 768, 560, 190),
    values('Engine Protection', [rid('RPM Limit'), rid('MAP Limit'), rid('Speed Limit'), rid('GP RPM Limit 1'),
                                 rid('GP RPM Limit 2'), rid('Anti-lag Cut'), rid('Cyclic Idle Limit'),
                                 rid('Limit Ignition Trim'), rid('Limit Fuel Trim'), rid('Max Eng Speed'), rid('Max MAP'),
                                 rid('Max IAT'), rid('Max ECU Temperature'), RPM, MAP, ECT, rid('Oil Pressure'), BATT],
           564, 404, 248, 554),
    plot('Limits', 814, 404, 880, 554),
])

# ---------------------------------------------------------------- Lambda: targets and closed loop
pages['Lambda'] = (-1, [
    settings('Closed Loop Lambda', 2, 2, 398, 480),
    settings('Lambda 1', 2, 484, 398, 150),
    settings('Long Term Fuel Trims', 2, 636, 398, 322),
    table('AFR/Lambda Target Table', 402, 2, 800, 480),
    values('Lambda', [LAM, TARGET, rid('CL Lambda Target Error 1'), rid('CL Lambda Status 1'), rid('Lambda 1 Status'),
                      rid('Lambda 1 Temperature.'), rid('Lambda 1 Error'), rid('Injection Actual PW'), DUTY, ETH,
                      rid('Charge Temperature'), RPM, MAP, MGP, TPS, ECT, IAT], 1204, 2, 248, 480),
    digital([LAM, TARGET, ETH], 1454, 2, 240, 480),
    plot('Closed Loop Fuel Tuning', 402, 484, 1292, 474),
])

# ---------------------------------------------------------------- Mixture Map and Logging: Link's own pages, resized
pages['Mixture Map'] = (2365, [
    borrow(BIG, 'Mixture Map', 'Mixture Map', 2, 2, 1066, 956),
    table('Fuel Table 1', 1070, 2, 624, 446),
    borrow(BIG, 'Mixture Map', 'XY Plot', 1070, 450, 624, 508),
])
pages['Logging'] = (-1, [
    borrow(BIG, 'General Log', 'Time Plot', 2, 2, 1188, 816),
    borrow(BIG, 'General Log', 'Navigator', 2, 820, 1188, 138),
    borrow(BIG, 'General Log', 'Parameter List', 1192, 2, 250, 956, nth=0),
    borrow(BIG, 'General Log', 'Parameter List', 1444, 2, 250, 956, nth=1),
])

# ---------------------------------------------------------------- checks + write
for name, (_, views) in pages.items():
    boxes = [(v.get('Type'), *[int(v.get(k)) for k in ('Left', 'Top', 'Width', 'Height')]) for v in views]
    for n, (ka, ax, ay, aw, ah) in enumerate(boxes):
        if ax + aw > W or ay + ah > H:
            problems.append(f'{name}: {ka} at {ax},{ay} runs past the {W}x{H} page')
        for kb, bx, by, bw, bh in boxes[n + 1:]:
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                problems.append(f'{name}: {ka} at {ax},{ay} overlaps {kb} at {bx},{by}')
print('\n'.join(sorted(set(notes))))
if problems:
    sys.exit('\n'.join(['NOT WRITTEN:'] + sorted(set(problems))))

root = ET.Element('LinkStorage', Version='100', Type='.llf5')
pgs = ET.SubElement(ET.SubElement(root, 'ViewLayout'), 'Pages', SelectedPage='Basics')
for name, (tbl, views) in pages.items():
    pg = ET.SubElement(pgs, 'Page', Name=name, NameStrId='0', CurrentTableDataID=str(tbl),
                       CurrentSettingsView='{00000000-0000-0000-0000-000000000000}')
    ET.SubElement(pg, 'Views').extend(views)
ET.indent(root, '\t')
out = sys.argv[2]
if os.path.exists(out) and '--force' not in sys.argv:
    sys.exit(f'{out} exists - pass --force to replace it')
with open(out, 'w', encoding='ascii', newline='\n') as f:
    f.write('<?xml version="1.0"?>\n' + ET.tostring(root, encoding='unicode') + '\n')
print('written', out, {n: len(v) for n, (_, v) in pages.items()})
