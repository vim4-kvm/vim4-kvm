// Temporary receiving application for input-check.mjs. Captures only its own
// keyboard/mouse events; pointer polling uses no global keyboard event tap.
import Cocoa
setbuf(stdout, nil)
func emit(_ data: [String: Any]) {
    var record = data
    record["receivedMs"] = Date().timeIntervalSince1970 * 1000
    if let bytes = try? JSONSerialization.data(withJSONObject: record), let s = String(data: bytes, encoding: .utf8) { print(s) }
}
class TargetWindow: NSWindow { override var canBecomeKey: Bool { true } }
class TargetView: NSView {
    override var acceptsFirstResponder: Bool { true }
    override func keyDown(with e: NSEvent) { emit(["kind":"keydown", "key":e.keyCode, "repeat":e.isARepeat]) }
    override func keyUp(with e: NSEvent) { emit(["kind":"keyup", "key":e.keyCode]) }
    override func scrollWheel(with e: NSEvent) { emit(["kind":"wheel", "dy":e.scrollingDeltaY, "inverted":e.isDirectionInvertedFromDevice]) }
    override func mouseDown(with e: NSEvent) { emit(["kind":"mousedown"]) }
    override func mouseUp(with e: NSEvent) { emit(["kind":"mouseup"]) }
    override func draw(_ r: NSRect) {
        NSColor.darkGray.setFill(); bounds.fill()
        ("VIM4 input test — temporary target" as NSString).draw(at:NSPoint(x:40,y:bounds.height/2), withAttributes:[.font:NSFont.systemFont(ofSize:28), .foregroundColor:NSColor.white])
    }
}
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let previousApp = NSWorkspace.shared.frontmostApplication
let pointer = CGEvent(source:nil)!.location
var windows: [NSWindow] = []
for screen in NSScreen.screens {
    let w = TargetWindow(contentRect:screen.frame, styleMask:[.borderless], backing:.buffered, defer:false)
    let view = TargetView(frame:NSRect(origin:.zero, size:screen.frame.size))
    w.contentView = view
    w.makeKeyAndOrderFront(nil)
    w.makeFirstResponder(view)
    windows.append(w)
}
app.activate(ignoringOtherApps:true)
// A local event monitor observes only this test application, never other apps.
let monitor = NSEvent.addLocalMonitorForEvents(matching:[.keyDown,.keyUp]) { e in
    emit(["kind":e.type == .keyDown ? "keydown":"keyup", "key":e.keyCode, "repeat":e.isARepeat]); return nil
}
var last = pointer
let poll = Timer.scheduledTimer(withTimeInterval:0.001, repeats:true) { _ in
    guard let p = CGEvent(source:nil)?.location else { return }
    if p != last { emit(["kind":"move", "x":p.x, "y":p.y]); last = p }
}
emit(["kind":"ready", "repeatDelay":NSEvent.keyRepeatDelay, "repeatInterval":NSEvent.keyRepeatInterval])
func finish() {
    poll.invalidate()
    CGWarpMouseCursorPosition(pointer)
    previousApp?.activate(options:[])
    app.terminate(nil)
}
// The sender closes stdin after releasing input; the timer also restores the
// desktop if the sender crashes. No permanent OS input preferences are changed.
FileHandle.standardInput.readabilityHandler = { handle in
    _ = handle.availableData
    handle.readabilityHandler = nil
    DispatchQueue.main.async { finish() }
}
Timer.scheduledTimer(withTimeInterval:Double(CommandLine.arguments.dropFirst().first ?? "40") ?? 40, repeats:false) { _ in finish() }
app.run()
