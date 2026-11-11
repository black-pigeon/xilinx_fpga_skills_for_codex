"""Offline tests: fake Hardware Manager only; never connect to a board."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/xilinx-jtag-debug/scripts/hw_debug.py'

STUB = r'''
set ::calls {}
set ::status IDLE
set ::targets {cable0}
proc open_hw_manager {} {lappend ::calls manager}
proc connect_hw_server {args} {lappend ::calls connect}
proc close_hw_manager {} {}
proc close_hw_target {} {}
proc get_hw_targets {args} {return $::targets}
proc open_hw_target {args} {lappend ::calls open_target}
proc current_hw_device {args} {}
proc get_hw_devices {args} {return {device0}}
proc refresh_hw_device {args} {lappend ::calls refresh}
proc get_hw_ilas {args} {return {ila0}}
proc get_hw_probes {args} {return {probe0 probe1}}
proc list_property {obj} {return {TRIGGER_COMPARE_VALUE}}
proc set_property {key value obj} {lappend ::calls [list set $key $value $obj]}
proc get_property {key obj} {
 if {$key eq "NAME"} {return $obj}
 if {$key eq "PART"} {return xc7a200t}
 if {$key eq "CELL_NAME"} {return top/ila}
 if {$key eq "WIDTH"} {if {$obj eq "probe0"} {return 8};return 1}
 if {$key eq "MAP"} {if {$obj eq "probe0"} {return {probe0[7:0]}};return {probe1[0:0]}}
 if {$key eq "STATUS.CORE_STATUS"} {return $::status}
 error "unexpected property $key $obj"
}
proc program_hw_devices {args} {lappend ::calls PROGRAM}
proc run_hw_ila {args} {lappend ::calls ARM;set ::armed 1}
proc reset_hw_ila {args} {set ::reset_done 1;lappend ::calls RESET}
proc update {} {if {[info exists ::armed] && ![info exists ::never_full]} {set ::status FULL}}
proc upload_hw_ila_data {args} {return data0}
proc write_hw_ila_data {args} {
 set f [open [lindex $args end-1] w];puts $f "EXPORTED";close $f
 lappend ::calls EXPORT
}
'''


class DebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('jtag_hw_debug', SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # The bracket expression must remain a literal Tcl path, not execute.
        self.bit = self.root / 'design [not_a_command] $x.bit'
        self.bit.write_bytes(b'fixture-bitstream-not-hardware')
        self.ltx = self.root / 'design.ltx'
        self.ltx.write_text('fixture')
        self.config = dict(action='capture', server='localhost:3121',
                           target='cable0', device='device0', part='xc7a200t',
                           ltx=str(self.ltx), ila='top/ila', mode='trigger',
                           timeout_seconds=0.05, probes={'probe0':8,'probe1':1},
                           triggers={'probe1':"eq1'b1"})

    def run_fake(self, overrides=None, prefix=''):
        config = dict(self.config)
        config.update(overrides or {})
        out = self.root / ('evidence-' + str(len(list(self.root.glob('evidence-*')))))
        script = self.module.prepare(config, out)
        fake = self.root / 'fake.tcl'
        fake.write_text(STUB + prefix + '\nsource ' + self.module.tcl_word(str(script)) + '\n')
        result = subprocess.run(['tclsh', str(fake)],capture_output=True,text=True,timeout=5)
        return result,out

    def test_capture_refreshes_status_and_exports_full(self):
        result,out = self.run_fake()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((out/'capture.csv').is_file())
        self.assertTrue((out/'capture.ila').is_file())
        self.assertIn('FULL',(out/'status.txt').read_text())
        self.assertIn('probe0',(out/'probe-map.tsv').read_text())

    def test_capture_clears_stale_controls_and_uses_documented_modes(self):
        guard = r'''
rename run_hw_ila original_run_hw_ila
proc run_hw_ila {args} {
 if {![info exists ::reset_done]} {error "old capture qualifiers not reset"}
 foreach item {{set CONTROL.TRIGGER_MODE BASIC_ONLY ila0} {set CONTROL.CAPTURE_MODE ALWAYS ila0}} {
  if {[lsearch -exact $::calls $item] < 0} {error "missing documented basic trigger/unconditional capture mode: $item"}
 }
 original_run_hw_ila {*}$args
}
'''
        result,out = self.run_fake(prefix=guard)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((out/'capture.csv').exists())

    def test_wrong_part_is_rejected(self):
        result,out=self.run_fake({'part':'xc7k325t'})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Part mismatch',result.stderr)
        self.assertFalse((out/'capture.csv').exists())

    def test_non_full_capture_never_exports(self):
        result,out = self.run_fake(prefix='set ::never_full 1\n')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((out/'capture.csv').exists())
        self.assertIn('not FULL',result.stderr)

    def test_ambiguous_target_is_rejected(self):
        result,out = self.run_fake({'action':'inspect','target':''},'set ::targets {cable0 cable1}\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('cable1',(out/'inventory.tsv').read_text())
        result,out = self.run_fake({'target':'missing'},'set ::targets {cable0 cable1}\n')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((out/'capture.csv').exists())

    def test_expected_probe_width_mismatch_stops_before_capture(self):
        result,out = self.run_fake({'probes':{'probe0':16}})
        self.assertNotEqual(result.returncode,0)
        self.assertIn('width',result.stderr.lower())
        self.assertFalse((out/'capture.csv').exists())

    def test_program_handles_special_path_literally(self):
        result,out = self.run_fake({'action':'program','bit':str(self.bit)})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('PROGRAMMED',(out/'status.txt').read_text())
        self.assertFalse((out/'capture.csv').exists())

    def test_inspect_does_not_program_or_capture(self):
        result,out = self.run_fake({'action':'inspect'})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('INSPECTED',(out/'status.txt').read_text())
        self.assertFalse((out/'capture.csv').exists())

    def test_dry_run_does_not_invoke_vivado(self):
        config=self.root/'config.json'
        config.write_text(json.dumps(dict(self.config,vivado='/not/installed/vivado')))
        out=self.root/'dry-run'
        result=subprocess.run([sys.executable,str(SCRIPT),'--config',str(config),'--out',str(out)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        summary=json.loads((out/'session.json').read_text())
        self.assertEqual(summary['result'],'PREPARED_NOT_EXECUTED')
        self.assertFalse((out/'status.txt').exists())

    def test_execute_with_missing_tool_records_failure_without_success_claim(self):
        config=self.root/'missing-tool.json'
        config.write_text(json.dumps(dict(self.config,vivado=str(self.root/'no-such-vivado'))))
        out=self.root/'missing-tool-evidence'
        result=subprocess.run([sys.executable,str(SCRIPT),'--config',str(config),'--out',str(out),'--execute'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        summary=json.loads((out/'session.json').read_text())
        self.assertEqual(summary['result'],'FAILED')
        self.assertFalse((out/'capture.csv').exists())

    def test_wrong_hash_and_missing_selector_rejected(self):
        for overrides in [{'bit_sha256':'0'*64,'action':'program','bit':str(self.bit)}, {'target':''}]:
            with self.assertRaises(ValueError):
                self.module.prepare(dict(self.config,**overrides),self.root/'invalid')

    def test_refuses_existing_evidence_directory(self):
        out=self.root/'existing';out.mkdir();(out/'keep').write_text('keep')
        with self.assertRaises(FileExistsError): self.module.prepare(self.config,out)
        self.assertEqual((out/'keep').read_text(),'keep')


if __name__ == '__main__':
    unittest.main()
