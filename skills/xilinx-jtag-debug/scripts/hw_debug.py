#!/usr/bin/env python3
"""Prepare or execute a bounded Vivado Hardware Manager batch session."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def tcl_word(value):
    """Encode data as a Tcl expression without evaluating user metacharacters."""
    encoded = str(value).encode('utf-8').hex()
    return '[encoding convertfrom utf-8 [binary format H* {' + encoded + '}]]'


def prepare(config, out):
    cfg = dict(config)
    allowed = {'action','server','target','device','part','vivado','bit','ltx',
               'bit_sha256','ltx_sha256','ila','mode','timeout_seconds',
               'process_timeout_seconds','jtag_hz','probes','triggers','trigger_position'}
    unknown = set(cfg) - allowed
    if unknown:
        raise ValueError('Unknown config fields: ' + ', '.join(sorted(unknown)))
    cfg.setdefault('server','localhost:3121')
    cfg.setdefault('target','')
    cfg.setdefault('device','')
    cfg.setdefault('part','')
    cfg.setdefault('mode','immediate')
    cfg.setdefault('timeout_seconds',10)
    cfg.setdefault('probes',{})
    cfg.setdefault('triggers',{})
    cfg.setdefault('trigger_position',0)
    action = cfg.get('action')
    if action not in ('inspect','program','capture'):
        raise ValueError('action must be inspect, program, or capture')
    for name in ('server','target','device','part','mode'):
        if not isinstance(cfg[name],str) or any(c in cfg[name] for c in '\r\n\t\0'):
            raise ValueError('Invalid string field: ' + name)
    if not cfg['server']:
        raise ValueError('server must be nonempty')
    if action != 'inspect' and not all(cfg[k] for k in ('target','device','part')):
        raise ValueError('program/capture requires exact target, device, and expected part')
    if cfg['part'] and not re.fullmatch(r'[A-Za-z0-9_-]+',cfg['part']):
        raise ValueError('part must be a part identifier, not a wildcard')
    if cfg['mode'] not in ('immediate','trigger'):
        raise ValueError('mode must be immediate or trigger')
    seconds = float(cfg['timeout_seconds'])
    if not math.isfinite(seconds) or not 0 < seconds <= 3600:
        raise ValueError('timeout_seconds must be finite, positive, and at most 3600')
    cfg['timeout_seconds'] = seconds
    cfg.setdefault('process_timeout_seconds',max(180,seconds+60))
    limit = float(cfg['process_timeout_seconds'])
    if not math.isfinite(limit) or limit <= seconds:
        raise ValueError('process_timeout_seconds must be finite and exceed timeout_seconds')
    for name in ('jtag_hz','trigger_position'):
        if name in cfg and (isinstance(cfg[name],bool) or not isinstance(cfg[name],int) or
                            cfg[name] < (1 if name=='jtag_hz' else 0)):
            raise ValueError('Invalid integer field: ' + name)
    artifacts = {}
    for name in ('bit','ltx'):
        if not cfg.get(name):
            if name+'_sha256' in cfg:
                raise ValueError('Hash supplied without file: ' + name)
            continue
        file = Path(cfg[name]).expanduser().resolve()
        if not file.is_file():
            raise ValueError('Missing artifact: ' + str(file))
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if name+'_sha256' in cfg and cfg[name+'_sha256'].lower()!=digest:
            raise ValueError('Artifact SHA-256 mismatch: ' + name)
        cfg[name] = str(file)
        artifacts[name] = {'path':str(file),'sha256':digest}
    if action == 'program' and not cfg.get('bit'):
        raise ValueError('program requires bit')
    if action == 'capture' and not all(cfg.get(k) for k in ('ltx','ila')):
        raise ValueError('capture requires matching ltx and exact ILA CELL_NAME')
    for field in ('probes','triggers'):
        if not isinstance(cfg[field],dict) or any(not isinstance(k,str) or not k for k in cfg[field]):
            raise ValueError(field + ' must be a name-to-value object')
    for name,width in cfg['probes'].items():
        if isinstance(width,bool) or not isinstance(width,int) or width < 1:
            raise ValueError('Expected probe width must be positive: ' + name)
    for name,value in cfg['triggers'].items():
        match = re.fullmatch(r"(eq|ne)([1-9][0-9]*)'([bh])([0-9a-fA-FxX_]+)",str(value))
        if not match:
            raise ValueError('Use width-qualified eq/ne binary/hex trigger: ' + name)
        width,base,digits=int(match[2]),match[3],match[4].replace('_','')
        if (base=='b' and (len(digits)!=width or re.search('[^01xX]',digits))) or (base=='h' and len(digits)!=(width+3)//4):
            raise ValueError('Trigger value width mismatch: ' + name)
        if name in cfg['probes'] and cfg['probes'][name]!=width:
            raise ValueError('Trigger and expected probe width disagree: ' + name)
    if action=='capture' and cfg['mode']=='trigger' and not cfg['triggers']:
        raise ValueError('trigger mode requires explicit trigger comparisons')
    out = Path(out).expanduser().resolve()
    out.mkdir(parents=True,exist_ok=False)
    cfg['out'] = str(out)
    lines = ['set ::hw_cfg [dict create]','set ::hw_expected [dict create]',
             'set ::hw_triggers [dict create]']
    for key,value in cfg.items():
        if key in ('probes','triggers'): continue
        lines.append('dict set ::hw_cfg ' + tcl_word(key) + ' ' + tcl_word(value))
    for name,width in cfg['probes'].items():
        lines.append('dict set ::hw_expected ' + tcl_word(name) + ' ' + tcl_word(width))
    for name,value in cfg['triggers'].items():
        lines.append('dict set ::hw_triggers ' + tcl_word(name) + ' ' + tcl_word(value))
    lines.append('source ' + tcl_word(str(HERE/'hw_session.tcl')))
    script = out/'run.tcl'
    script.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    record = {'created_at':datetime.now(timezone.utc).isoformat(), 'config':cfg,
              'artifacts':artifacts,'result':'PREPARED_NOT_EXECUTED',
              'validation_scope':'Preparation only; no board operation performed.'}
    (out/'session.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return script


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path,help='New evidence directory; never overwritten')
    parser.add_argument('--execute',action='store_true',help='Actually run Vivado; requires task authorization')
    args=parser.parse_args()
    try:
        cfg=json.loads(args.config.read_text(encoding='utf-8'))
        if not isinstance(cfg,dict): raise ValueError('Config must be a JSON object')
        script=prepare(cfg,args.out)
    except (OSError,ValueError,TypeError) as exc:
        print('Preparation failed: '+str(exc),file=sys.stderr)
        return 1
    print('Prepared: '+str(script),flush=True)
    if not args.execute:
        print('Dry run only. No hardware accessed; add --execute within the authorized task.')
        return 0
    out=script.parent
    record=json.loads((out/'session.json').read_text(encoding='utf-8'))
    effective=record['config']
    cmd=[cfg.get('vivado','vivado'),'-mode','batch','-notrace','-log',str(out/'vivado.log'),
         '-journal',str(out/'vivado.jou'),'-source',str(script)]
    record['command']=cmd
    try:
        with (out/'console.log').open('w',encoding='utf-8') as log:
            result=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT,
                                  timeout=float(effective['process_timeout_seconds']))
        status=(out/'status.txt').read_text().strip() if (out/'status.txt').exists() else ''
        expected={'inspect':'INSPECTED','program':'PROGRAMMED','capture':'FULL'}[effective['action']]
        ok=result.returncode==0 and status==expected
        if ok and expected=='FULL':
            ok=all((out/f).is_file() and (out/f).stat().st_size>0 for f in ('capture.csv','capture.ila','probe-map.tsv'))
        record.update(result=expected if ok else 'FAILED',exit_code=result.returncode,
                      validation_scope='Hardware Manager session only; no application/PCIe/RF signoff.')
    except (OSError,subprocess.TimeoutExpired) as exc:
        ok=False
        record.update(result='FAILED',error=str(exc),validation_scope='Operation failed or timed out; board state must be inspected.')
    (out/'session.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(record['result']+': '+str(out))
    return 0 if ok else 1


if __name__=='__main__':
    sys.exit(main())
