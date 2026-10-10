"""Read macOS Network.framework path cost without extra packages or a compiler.

A single process-lifetime monitor follows interface changes. Apple's expensive flag
covers personal hotspots; constrained covers Low Data Mode. Missing data fails closed.
"""
import ctypes as c
import threading

_lock = threading.Lock()
_ready = threading.Event()
_monitor = None
_cost = "unknown"
_refs = []  # Keep the global block, callback and native objects alive for the monitor.


def _start():
    global _monitor
    nw = c.CDLL("/System/Library/Frameworks/Network.framework/Network")
    dispatch = c.CDLL("/usr/lib/libSystem.B.dylib")
    invoke_type = c.CFUNCTYPE(None, c.c_void_p, c.c_void_p)

    class Descriptor(c.Structure):
        _fields_ = [("reserved", c.c_ulong), ("size", c.c_ulong)]

    class Block(c.Structure):
        _fields_ = [("isa", c.c_void_p), ("flags", c.c_int), ("reserved", c.c_int),
                    ("invoke", invoke_type), ("descriptor", c.POINTER(Descriptor))]

    for name, restype, args in [
        ("nw_path_monitor_create", c.c_void_p, []),
        ("nw_path_monitor_set_update_handler", None, [c.c_void_p, c.c_void_p]),
        ("nw_path_monitor_set_queue", None, [c.c_void_p, c.c_void_p]),
        ("nw_path_monitor_start", None, [c.c_void_p]),
        ("nw_path_get_status", c.c_int, [c.c_void_p]),
        ("nw_path_is_expensive", c.c_bool, [c.c_void_p]),
        ("nw_path_is_constrained", c.c_bool, [c.c_void_p]),
    ]:
        f = getattr(nw, name)
        f.restype, f.argtypes = restype, args
    dispatch.dispatch_queue_create.restype = c.c_void_p
    dispatch.dispatch_queue_create.argtypes = [c.c_char_p, c.c_void_p]

    @invoke_type
    def update(_, path):
        global _cost
        if nw.nw_path_get_status(path) != 1:  # nw_path_status_satisfied
            _cost = "offline"
        elif nw.nw_path_is_expensive(path) or nw.nw_path_is_constrained(path):
            _cost = "metered"
        else:
            _cost = "unrestricted"
        _ready.set()

    descriptor = Descriptor(0, c.sizeof(Block))
    isa = c.addressof(c.c_byte.in_dll(dispatch, "_NSConcreteGlobalBlock"))
    block = Block(isa, 1 << 28, 0, update, c.pointer(descriptor))  # BLOCK_IS_GLOBAL
    queue = dispatch.dispatch_queue_create(b"net.giuseppelupo.aggiornamenti.network", None)
    monitor = nw.nw_path_monitor_create()
    if not queue or not monitor:
        raise RuntimeError("Network monitor unavailable")
    _refs.extend([nw, dispatch, descriptor, block, update, queue, monitor])
    nw.nw_path_monitor_set_queue(monitor, queue)
    nw.nw_path_monitor_set_update_handler(monitor, c.byref(block))
    nw.nw_path_monitor_start(monitor)
    _monitor = monitor


def current_cost():
    try:
        with _lock:
            if _monitor is None:
                _start()
        _ready.wait(3)
        return _cost
    except (OSError, AttributeError, ValueError, RuntimeError):
        return "unknown"
