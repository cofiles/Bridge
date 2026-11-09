"""Local server quality estimates; no geolocation requests or subscription secrets."""
import hashlib
import json
import re
import time

COUNTRIES = set('US GB DE FR NL FI SE NO CH AT PL CZ ES IT PT TR RU UA KZ AZ AM GE AE IL IN SG JP KR HK TW AU CA BR MX AR ZA IS IE BE DK RO BG HU GR CY EE LV LT MD RS HR SK SI TH VN ID MY PH NZ'.split())
ALIASES = {'germany':'DE', 'германия':'DE', 'netherlands':'NL', 'нидерланды':'NL', 'finland':'FI', 'финляндия':'FI', 'turkey':'TR', 'турция':'TR', 'france':'FR', 'франция':'FR', 'usa':'US', 'сша':'US', 'japan':'JP', 'япония':'JP', 'singapore':'SG', 'сингапур':'SG', 'uk':'GB'}


def key(outbound):
    return hashlib.sha256(json.dumps(outbound, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def country(name):
    flag = re.search('[\U0001f1e6-\U0001f1ff]{2}', name)
    if flag:
        return ''.join(chr(ord(c)-0x1f1e6+65) for c in flag.group())
    for token in re.findall(r'[^\W\d_]+', name, re.UNICODE):
        if token in COUNTRIES:
            return token.upper()
        if token.lower() in ALIASES:
            return ALIASES[token.lower()]
    return ''


def score(record):
    successes, failures = record.get('successes',0), record.get('failures',0)
    reliability = (successes+1)/(successes+failures+2)
    latency = record.get('latency_ms', 1500)
    stability = 1/(1+record.get('drops',0)/max(1,record.get('sessions',0)))
    speed = 1/(1+latency/500)
    freshness = .75 if time.time()-record.get('checked_at',0)>3600 else 1
    return round(100*(.55*reliability+.30*stability+.15*speed)*freshness,1)


def result(record, success, latency_ms=None):
    value = dict(record)
    field = 'successes' if success else 'failures'
    value[field] = value.get(field,0)+1
    value['checked_at'] = time.time()
    value['status'] = 'passed' if success else 'failed'
    if success and latency_ms is not None:
        value['latency_ms'] = round(.7*value.get('latency_ms',latency_ms)+.3*latency_ms)
    return value


def describe(name, outbound, provider, record):
    return {'name':name, 'country':country(name), 'protocol':outbound.get('protocol',''),
            'transport':outbound.get('streamSettings',{}).get('network','tcp'), 'provider':provider,
            'status':record.get('status','untested'), 'checked_at':record.get('checked_at'),
            'latency_ms':record.get('latency_ms'), 'score':score(record) if record else None,
            'successes':record.get('successes',0), 'failures':record.get('failures',0), 'drops':record.get('drops',0)}
