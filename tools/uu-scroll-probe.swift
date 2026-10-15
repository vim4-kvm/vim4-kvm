// Measures only scroll events delivered to this window. It never injects input
// or installs a global event tap. Run the same physical wheel sequence per route.
import Cocoa

setbuf(stdout, nil)
func emit(_ fields: [String: Any]) {
    var record = fields
    record["time"] = Date().timeIntervalSince1970
    if let data = try? JSONSerialization.data(withJSONObject: record),
       let text = String(data: data, encoding: .utf8) { print(text) }
}

class ProbeView: NSView {
    var route = "unselected"
    let routes = ["uu-direct", "uu-kvm", "web-kvm"]
    var count = 0
    var total = 0.0
    let summary = NSTextField(labelWithString: "先选择连接方式，再把鼠标放在此窗口内滚动。")

    override init(frame: NSRect) {
        super.init(frame: frame)
        let instructions = NSTextField(wrappingLabelWithString:
            "同一个鼠标：先慢滚 10 格（每格隔半秒）。\n再次点击对应按钮清零，再快速连续滚 10 格。")
        instructions.frame = NSRect(x: 24, y: 230, width: 590, height: 60)
        addSubview(instructions)
        for (index, title) in ["UU 直连 Mac", "UU 连接 KVM", "KVM 网页"].enumerated() {
            let button = NSButton(title: title, target: self, action: #selector(selectRoute(_:)))
            button.tag = index
            button.frame = NSRect(x: 24 + index * 200, y: 170, width: 190, height: 38)
            addSubview(button)
        }
        summary.frame = NSRect(x: 24, y: 80, width: 590, height: 60)
        summary.maximumNumberOfLines = 3
        addSubview(summary)
    }

    required init?(coder: NSCoder) { fatalError("Not loaded from a storyboard") }
    override var acceptsFirstResponder: Bool { true }

    @objc func selectRoute(_ sender: NSButton) {
        route = routes[sender.tag]
        count = 0
        total = 0
        emit(["kind": "begin", "route": route])
        summary.stringValue = "\(sender.title)：已清零，请滚动 10 格。"
        window?.makeFirstResponder(self)
    }

    override func scrollWheel(with event: NSEvent) {
        guard route != "unselected" else { return }
        count += 1
        var record: [String: Any] = [
            "kind": "scroll", "route": route, "count": count,
            "deltaY": event.deltaY, "scrollingDeltaY": event.scrollingDeltaY,
            "precise": event.hasPreciseScrollingDeltas,
            "inverted": event.isDirectionInvertedFromDevice,
            "phase": event.phase.rawValue, "momentumPhase": event.momentumPhase.rawValue
        ]
        if let cg = event.cgEvent {
            record["lineDeltaY"] = cg.getIntegerValueField(.scrollWheelEventDeltaAxis1)
            record["pointDeltaY"] = cg.getIntegerValueField(.scrollWheelEventPointDeltaAxis1)
            record["fixedDeltaY"] = cg.getDoubleValueField(.scrollWheelEventFixedPtDeltaAxis1)
            total += Double(cg.getIntegerValueField(.scrollWheelEventPointDeltaAxis1))
        }
        emit(record)
        summary.stringValue = "\(route)：收到 \(count) 个事件，累计点增量 = \(total)\n事件数量不一定等于物理滚轮格数。"
    }
}

class Delegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let delegate = Delegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 640, height: 330),
                      styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
window.title = "UU 滚轮对照测试"
window.contentView = ProbeView(frame: NSRect(x: 0, y: 0, width: 640, height: 330))
window.center()
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
emit(["kind": "ready"])
Timer.scheduledTimer(withTimeInterval: 900, repeats: false) { _ in app.terminate(nil) }
app.run()
