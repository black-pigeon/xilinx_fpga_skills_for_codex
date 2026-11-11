# Loaded by hw_debug.py's generated run.tcl, in a fresh Vivado batch process.
# This script never starts/kills hw_server, changes PCIe, or writes flash.
namespace eval rtl_hw {
    variable manager_open 0
    variable target_open 0
    variable armed_ila {}
    variable inventory {}
}
proc rtl_hw::select_exact {objects requested label} {
    set found {}
    foreach object $objects {
        if {[get_property NAME $object] eq $requested} {lappend found $object}
    }
    if {[llength $found] != 1} {error "Expected one exact $label '$requested', found $found"}
    return [lindex $found 0]
}
proc rtl_hw::put_status {status} {
    set f [open [file join [dict get $::hw_cfg out] status.txt] w]
    puts $f $status
    close $f
}
proc rtl_hw::run {} {
    variable manager_open
    variable target_open
    variable inventory
    variable armed_ila
    set action [dict get $::hw_cfg action]
    set inventory [open [file join [dict get $::hw_cfg out] inventory.tsv] w]
    open_hw_manager
    set manager_open 1
    connect_hw_server -url [dict get $::hw_cfg server]
    set targets [get_hw_targets]
    foreach target $targets {puts $inventory "target\t[get_property NAME $target]"}
    flush $inventory
    set requested [dict get $::hw_cfg target]
    if {$action eq "inspect" && $requested eq ""} {
        # Inventory only. Do not open an arbitrary cable, even if only one exists.
        put_status INSPECTED
        return
    }
    set target [select_exact $targets $requested target]
    if {[dict exists $::hw_cfg jtag_hz]} {
        set_property PARAM.FREQUENCY [dict get $::hw_cfg jtag_hz] $target
    }
    open_hw_target $target
    set target_open 1
    set devices [get_hw_devices]
    foreach device $devices {puts $inventory "device\t[get_property NAME $device]\t[get_property PART $device]"}
    flush $inventory
    if {$action eq "inspect" && [dict get $::hw_cfg device] eq ""} {
        put_status INSPECTED
        return
    }
    set device [select_exact $devices [dict get $::hw_cfg device] device]
    set expected_part [dict get $::hw_cfg part]
    set actual_part [get_property PART $device]
    if {$expected_part ne "" && ![string equal -nocase $expected_part $actual_part]} {
        error "Part mismatch: expected $expected_part, actual $actual_part"
    }
    current_hw_device $device
    if {$action eq "program"} {
        set_property PROBES.FILE {} $device
        set_property FULL_PROBES.FILE {} $device
        set_property PROGRAM.FILE [dict get $::hw_cfg bit] $device
        program_hw_devices $device
        # Success here confirms programming API success, not application health.
        put_status PROGRAMMED
        return
    }
    if {$action eq "capture"} {
        set_property PROBES.FILE [dict get $::hw_cfg ltx] $device
        set_property FULL_PROBES.FILE [dict get $::hw_cfg ltx] $device
    }
    refresh_hw_device $device
    set ilas [get_hw_ilas -of_objects $device]
    foreach ila $ilas {puts $inventory "ila\t[get_property NAME $ila]\t[get_property CELL_NAME $ila]"}
    flush $inventory
    if {$action eq "inspect"} {put_status INSPECTED;return}
    set matches {}
    foreach candidate $ilas {
        if {[get_property CELL_NAME $candidate] eq [dict get $::hw_cfg ila]} {lappend matches $candidate}
    }
    if {[llength $matches] != 1} {error "Expected one exact ILA CELL_NAME; found $matches"}
    set ila [lindex $matches 0]
    # Reset trigger/storage qualification left by earlier use of this core.
    reset_hw_ila -reset_compare_values 1 $ila
    set probe_by_name [dict create]
    set mapfile [open [file join [dict get $::hw_cfg out] probe-map.tsv] w]
    puts $mapfile "name\twidth\tmap"
    foreach probe [get_hw_probes -of_objects $ila] {
        set name [get_property NAME $probe]
        if {[dict exists $probe_by_name $name]} {close $mapfile;error "Duplicate probe name $name"}
        dict set probe_by_name $name $probe
        set width [get_property WIDTH $probe]
        puts $mapfile "$name\t$width\t[get_property MAP $probe]"
        # Clear only supported comparator properties. Data-only probes may not have one.
        if {[lsearch -exact [list_property $probe] TRIGGER_COMPARE_VALUE] >= 0} {
            set_property TRIGGER_COMPARE_VALUE "eq${width}'b[string repeat x $width]" $probe
        }
    }
    close $mapfile
    dict for {name width} $::hw_expected {
        if {![dict exists $probe_by_name $name]} {error "Missing expected probe $name"}
        if {[get_property WIDTH [dict get $probe_by_name $name]] != $width} {error "Probe width mismatch: $name"}
    }
    dict for {name compare} $::hw_triggers {
        if {![dict exists $probe_by_name $name]} {error "Missing trigger probe $name"}
        set probe [dict get $probe_by_name $name]
        if {[lsearch -exact [list_property $probe] TRIGGER_COMPARE_VALUE] < 0} {error "Probe is not trigger-capable: $name"}
        regexp {^[a-z]+([0-9]+)'} $compare -> compare_width
        if {[get_property WIDTH $probe] != $compare_width} {error "Trigger width mismatch: $name"}
        set_property TRIGGER_COMPARE_VALUE $compare $probe
    }
    set_property CONTROL.TRIGGER_MODE BASIC_ONLY $ila
    set_property CONTROL.CAPTURE_MODE ALWAYS $ila
    set_property CONTROL.TRIGGER_CONDITION AND $ila
    set_property CONTROL.TRIGGER_POSITION [dict get $::hw_cfg trigger_position] $ila
    if {[dict get $::hw_cfg mode] eq "immediate"} {
        run_hw_ila -trigger_now $ila
    } else {
        run_hw_ila $ila
    }
    set armed_ila $ila
    set armfile [open [file join [dict get $::hw_cfg out] armed.txt] w]
    puts $armfile "ILA armed; mode=[dict get $::hw_cfg mode]"
    close $armfile
    puts "RTL_ILA_ARMED [dict get $::hw_cfg out]"
    flush stdout
    # Poll the hardware property while pumping asynchronous Vivado events.
    # wait_on_hw_ila uses MINUTES; this loop's deadline is explicitly milliseconds.
    set deadline [expr {[clock milliseconds] + int(1000.0 * [dict get $::hw_cfg timeout_seconds])}]
    while {1} {
        update
        set status [get_property STATUS.CORE_STATUS $ila]
        if {$status eq "FULL"} {break}
        if {[clock milliseconds] >= $deadline} {error "Capture not FULL before deadline ($status); no data exported"}
        after 25
    }
    set data [upload_hw_ila_data $ila]
    if {[llength $data] != 1} {error "Expected exactly one captured data object"}
    write_hw_ila_data -csv_file [file join [dict get $::hw_cfg out] capture.csv] $data
    write_hw_ila_data [file join [dict get $::hw_cfg out] capture.ila] $data
    set armed_ila {}
    put_status FULL
}
set rc [catch {rtl_hw::run} message options]
if {$rc} {
    # UG835 documents upload as the way to stop a non-FULL acquisition.
    # This error-path data is discarded, never exported or counted as valid.
    if {$rtl_hw::armed_ila ne ""} {
        if {[catch {upload_hw_ila_data $rtl_hw::armed_ila} stop_error]} {
            puts stderr "RTL_HW_CLEANUP_FAILED: $stop_error"
        }
    }
    catch {rtl_hw::put_status FAILED}
    puts stderr "RTL_HW_FAILED: $message"
}
if {$rtl_hw::inventory ne ""} {catch {close $rtl_hw::inventory}}
if {$rtl_hw::target_open} {catch {close_hw_target}}
if {$rtl_hw::manager_open} {catch {close_hw_manager}}
if {$rc} {exit 1}
